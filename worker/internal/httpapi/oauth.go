package httpapi

import (
	"context"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/auth"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/model"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// oauth.go ports the OAuth login flow in app/api/v1/auth_native.py (login +
// callback). The browser hits /auth/login/{provider} -> provider consent ->
// /auth/callback/{provider} -> we exchange the code, read the user's profile,
// provision the account, issue a session JWT cookie, and bounce to the frontend.
// The Python worker used Authlib + the Starlette session for CSRF state; here we
// carry the state in a short-lived HMAC-signed cookie instead.

var oauthHTTPClient = &http.Client{Timeout: 30 * time.Second}

const (
	oauthStateCookie = "cogni_oauth_state"
	oauthStateTTL    = 10 * time.Minute
)

// oauthProvider captures the per-provider OAuth endpoints + login scopes
// (a trimmed Go port of app/integrations/oauth_flow.OAuthProvider for the LOGIN
// scopes only — calendar scopes belong to the integrations connect flow).
type oauthProvider struct {
	name             string
	authorizeURL     string
	tokenURL         string
	userinfoURL      string
	scopes           []string
	sendScopeInToken bool // Microsoft echoes scope back in the token request
}

// providerFor returns the provider config + this worker's client credentials.
// ok=false for an unknown provider name (-> 404, matching _client).
func (s *Server) providerFor(name string) (p *oauthProvider, clientID, clientSecret string, ok bool) {
	switch name {
	case "google":
		return &oauthProvider{
			name:         "google",
			authorizeURL: "https://accounts.google.com/o/oauth2/v2/auth",
			tokenURL:     "https://oauth2.googleapis.com/token",
			userinfoURL:  "https://openidconnect.googleapis.com/v1/userinfo",
			scopes:       []string{"openid", "email", "profile"},
		}, s.Cfg.GoogleClientID, s.Cfg.GoogleClientSecret, true
	case "microsoft":
		return &oauthProvider{
			name:             "microsoft",
			authorizeURL:     "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
			tokenURL:         "https://login.microsoftonline.com/common/oauth2/v2.0/token",
			userinfoURL:      "https://graph.microsoft.com/v1.0/me",
			scopes:           []string{"openid", "email", "profile"},
			sendScopeInToken: true,
		}, s.Cfg.MicrosoftClientID, s.Cfg.MicrosoftClientSecret, true
	}
	return nil, "", "", false
}

// ---- CSRF state cookie (HMAC over {state,next,exp}) -------------------------

type oauthStatePayload struct {
	State string `json:"s"`
	Next  string `json:"n"`
	Exp   int64  `json:"e"`
}

func (s *Server) signOAuthState(p oauthStatePayload) (string, error) {
	secret, err := s.Cfg.SessionSigningSecret()
	if err != nil {
		return "", err
	}
	payload, _ := json.Marshal(p)
	b64 := base64.RawURLEncoding.EncodeToString(payload)
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(b64))
	return b64 + "." + base64.RawURLEncoding.EncodeToString(mac.Sum(nil)), nil
}

func (s *Server) verifyOAuthState(token string) (*oauthStatePayload, bool) {
	secret, err := s.Cfg.SessionSigningSecret()
	if err != nil {
		return nil, false
	}
	b64, sig, found := strings.Cut(token, ".")
	if !found {
		return nil, false
	}
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(b64))
	expected := base64.RawURLEncoding.EncodeToString(mac.Sum(nil))
	if subtle.ConstantTimeCompare([]byte(expected), []byte(sig)) != 1 {
		return nil, false
	}
	raw, err := base64.RawURLEncoding.DecodeString(b64)
	if err != nil {
		return nil, false
	}
	var p oauthStatePayload
	if json.Unmarshal(raw, &p) != nil || time.Now().Unix() > p.Exp {
		return nil, false
	}
	return &p, true
}

func randToken(n int) string {
	b := make([]byte, n)
	_, _ = rand.Read(b)
	return base64.RawURLEncoding.EncodeToString(b)
}

// safeNext only allows same-site relative paths (guards open redirect; ports
// _safe_next).
func safeNext(p string) string {
	if p == "" || !strings.HasPrefix(p, "/") || strings.HasPrefix(p, "//") {
		return "/dashboard"
	}
	return p
}

func (s *Server) oauthErrorRedirect(w http.ResponseWriter, r *http.Request, msg string) {
	q := url.Values{"error": {msg}}
	http.Redirect(w, r, strings.TrimRight(s.Cfg.FrontendURL, "/")+"/login?"+q.Encode(), http.StatusFound)
}

// ---- handlers --------------------------------------------------------------

// GET /api/v1/auth/login/{provider} — build the provider authorize URL, stash a
// signed state (+ where to land afterwards) in a short-lived cookie, and redirect.
func (s *Server) oauthLogin(w http.ResponseWriter, r *http.Request) {
	name := chi.URLParam(r, "provider")
	prov, clientID, _, ok := s.providerFor(name)
	if !ok {
		writeError(w, http.StatusNotFound, "Unknown provider")
		return
	}
	if clientID == "" {
		writeError(w, http.StatusServiceUnavailable, name+" OAuth is not configured")
		return
	}

	state := randToken(24)
	stateTok, err := s.signOAuthState(oauthStatePayload{
		State: state, Next: safeNext(r.URL.Query().Get("next")),
		Exp: time.Now().Add(oauthStateTTL).Unix(),
	})
	if err != nil {
		writeError(w, http.StatusInternalServerError, "auth not configured")
		return
	}
	http.SetCookie(w, &http.Cookie{
		Name: oauthStateCookie, Value: stateTok, Path: "/",
		MaxAge: int(oauthStateTTL.Seconds()), HttpOnly: true,
		Secure: s.Cfg.IsProduction(), SameSite: http.SameSiteLaxMode,
	})

	q := url.Values{}
	q.Set("client_id", clientID)
	q.Set("response_type", "code")
	q.Set("redirect_uri", s.oauthRedirectURI(name))
	q.Set("scope", strings.Join(prov.scopes, " "))
	q.Set("state", state)
	http.Redirect(w, r, prov.authorizeURL+"?"+q.Encode(), http.StatusFound)
}

func (s *Server) oauthRedirectURI(provider string) string {
	return strings.TrimRight(s.Cfg.PublicAPIURL, "/") + "/api/v1/auth/callback/" + provider
}

// GET /api/v1/auth/callback/{provider} — verify state, exchange the code, read
// the profile, provision, issue a session, and bounce to the frontend. Every
// failure path returns the user to /login?error=… (a usable page) rather than
// stranding them on the worker domain with a raw error.
func (s *Server) oauthCallback(w http.ResponseWriter, r *http.Request) {
	name := chi.URLParam(r, "provider")
	prov, clientID, clientSecret, ok := s.providerFor(name)
	if !ok || clientID == "" {
		s.oauthErrorRedirect(w, r, "Sign-in isn't available right now. Please try again later.")
		return
	}

	// CSRF: the signed state cookie must be present, valid, and match ?state.
	stateCookie, err := r.Cookie(oauthStateCookie)
	if err != nil {
		s.oauthErrorRedirect(w, r, "Your sign-in session expired. Please try again.")
		return
	}
	// Clear the one-time state cookie regardless of outcome.
	http.SetCookie(w, &http.Cookie{
		Name: oauthStateCookie, Value: "", Path: "/", MaxAge: -1, HttpOnly: true,
		Secure: s.Cfg.IsProduction(), SameSite: http.SameSiteLaxMode,
	})
	st, valid := s.verifyOAuthState(stateCookie.Value)
	if !valid || st.State == "" || subtle.ConstantTimeCompare([]byte(st.State), []byte(r.URL.Query().Get("state"))) != 1 {
		s.oauthErrorRedirect(w, r, "We couldn't verify your sign-in. Please try again.")
		return
	}

	if r.URL.Query().Get("error") != "" || r.URL.Query().Get("code") == "" {
		s.oauthErrorRedirect(w, r, "We couldn't complete sign-in. Please try again.")
		return
	}

	accessToken, err := s.oauthExchangeCode(r.Context(), prov, clientID, clientSecret,
		s.oauthRedirectURI(name), r.URL.Query().Get("code"))
	if err != nil {
		s.oauthErrorRedirect(w, r, "We couldn't complete sign-in. Please try again.")
		return
	}
	info, err := s.oauthUserinfo(r.Context(), prov, accessToken)
	if err != nil || info.Email == "" {
		if err != nil {
			s.oauthErrorRedirect(w, r, "We couldn't read your profile from the provider.")
		} else {
			s.oauthErrorRedirect(w, r, "Your provider didn't share an email address.")
		}
		return
	}

	profile, err := s.provisionOAuthUser(r.Context(), info)
	if err != nil {
		s.oauthErrorRedirect(w, r, "Sign-in failed. Please try again.")
		return
	}

	secret, err := s.Cfg.SessionSigningSecret()
	if err != nil {
		s.oauthErrorRedirect(w, r, "Sign-in failed. Please try again.")
		return
	}
	token, err := auth.IssueSessionToken(secret, profile.ID, profile.Email, auth.DefaultTTL)
	if err != nil {
		s.oauthErrorRedirect(w, r, "Sign-in failed. Please try again.")
		return
	}
	s.setSessionCookie(w, token)
	http.Redirect(w, r, strings.TrimRight(s.Cfg.FrontendURL, "/")+safeNext(st.Next), http.StatusFound)
}

// provisionOAuthUser get-or-creates the profile for an OAuth identity, handling
// the concurrent-first-login race the same way as register (commit; on conflict
// adopt the existing row).
func (s *Server) provisionOAuthUser(ctx context.Context, info oauthUserInfo) (*model.Profile, error) {
	var name, avatar *string
	if info.Name != "" {
		name = &info.Name
	}
	if info.Picture != "" {
		avatar = &info.Picture
	}
	tx, err := s.DB.BeginTx(ctx, nil)
	if err != nil {
		return nil, err
	}
	defer tx.Rollback() //nolint:errcheck
	profile, err := store.GetOrCreateUser(ctx, tx, info.Email, name, avatar)
	if err != nil {
		return nil, err
	}
	if err := tx.Commit(); err != nil {
		// Lost the race for this email — adopt the existing profile.
		if existing, e2 := store.GetProfileByEmail(ctx, s.DB, info.Email); e2 == nil && existing != nil {
			return existing, nil
		}
		return nil, err
	}
	return profile, nil
}

// ---- provider HTTP ---------------------------------------------------------

func (s *Server) oauthExchangeCode(ctx context.Context, prov *oauthProvider, clientID, clientSecret, redirectURI, code string) (string, error) {
	form := url.Values{}
	form.Set("grant_type", "authorization_code")
	form.Set("code", code)
	form.Set("redirect_uri", redirectURI)
	form.Set("client_id", clientID)
	form.Set("client_secret", clientSecret)
	if prov.sendScopeInToken {
		form.Set("scope", strings.Join(prov.scopes, " "))
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, prov.tokenURL, strings.NewReader(form.Encode()))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")
	resp, err := oauthHTTPClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode >= 400 {
		return "", &oauthHTTPError{provider: prov.name, status: resp.StatusCode}
	}
	var tok struct {
		AccessToken string `json:"access_token"`
	}
	if err := json.Unmarshal(body, &tok); err != nil || tok.AccessToken == "" {
		return "", &oauthHTTPError{provider: prov.name, status: resp.StatusCode}
	}
	return tok.AccessToken, nil
}

type oauthUserInfo struct {
	Email   string
	Name    string
	Picture string
}

func (s *Server) oauthUserinfo(ctx context.Context, prov *oauthProvider, accessToken string) (oauthUserInfo, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, prov.userinfoURL, nil)
	if err != nil {
		return oauthUserInfo{}, err
	}
	req.Header.Set("Authorization", "Bearer "+accessToken)
	req.Header.Set("Accept", "application/json")
	resp, err := oauthHTTPClient.Do(req)
	if err != nil {
		return oauthUserInfo{}, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode >= 400 {
		return oauthUserInfo{}, &oauthHTTPError{provider: prov.name, status: resp.StatusCode}
	}
	var raw map[string]any
	if err := json.Unmarshal(body, &raw); err != nil {
		return oauthUserInfo{}, err
	}
	str := func(k string) string {
		if v, ok := raw[k].(string); ok {
			return v
		}
		return ""
	}
	switch prov.name {
	case "microsoft":
		// Graph /me: mail is often null for non-Exchange accounts; the UPN
		// (userPrincipalName) is the user's email in practice.
		email := str("mail")
		if email == "" {
			email = str("userPrincipalName")
		}
		return oauthUserInfo{Email: email, Name: str("displayName")}, nil
	default:
		return oauthUserInfo{Email: str("email"), Name: str("name"), Picture: str("picture")}, nil
	}
}

type oauthHTTPError struct {
	provider string
	status   int
}

func (e *oauthHTTPError) Error() string {
	return e.provider + " oauth http error"
}
