package httpapi

import (
	"errors"
	"net/http"
	"net/url"
	"strings"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/integrations/oauth"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
	"github.com/go-chi/chi/v5"
)

// integrations.go ports app/api/v1/integrations.py: the OAuth connect / callback
// / disconnect flow for the calendar/recording providers (Google, Microsoft,
// Zoom). connect returns an authorization_url the SPA redirects to; the provider
// then hits the PUBLIC callback (no session) which exchanges the code, stores the
// Fernet-encrypted tokens, and 302s back to the frontend integrations page.

var supportedIntegrationPlatforms = map[string]bool{"zoom": true, "microsoft": true, "google": true}

// RegisterIntegrations mounts the authed list/connect/disconnect routes.
func (s *Server) RegisterIntegrations(r chi.Router) {
	r.Get("/integrations", s.integrationsList)
	r.Post("/integrations/{platform}/connect", s.integrationsConnect)
	r.Delete("/integrations/{platform}/disconnect", s.integrationsDisconnect)
}

// RegisterIntegrationsCallback mounts the PUBLIC OAuth callback (the provider
// redirects the browser here with no session cookie). Wired outside requireAuth.
func (s *Server) RegisterIntegrationsCallback(r chi.Router) {
	r.Get("/integrations/{platform}/callback", s.integrationsCallback)
}

func titleCase(s string) string {
	if s == "" {
		return s
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

func (s *Server) integrationClientCreds(platform string) (id, secret string) {
	switch platform {
	case "google":
		return s.Cfg.GoogleClientID, s.Cfg.GoogleClientSecret
	case "microsoft":
		return s.Cfg.MicrosoftClientID, s.Cfg.MicrosoftClientSecret
	case "zoom":
		return s.Cfg.ZoomClientID, s.Cfg.ZoomClientSecret
	}
	return "", ""
}

func (s *Server) integrationRedirectURI(platform string) string {
	return strings.TrimRight(s.Cfg.PublicAPIURL, "/") + "/api/v1/integrations/" + platform + "/callback"
}

// GET /api/v1/integrations — the user's active integrations (is_active filtered
// by the frontend, so the shape must carry is_active).
func (s *Server) integrationsList(w http.ResponseWriter, r *http.Request) {
	u := authUserFromCtx(r.Context())
	rows, err := store.ListUserIntegrations(r.Context(), s.DB, u.ID)
	if storeError(w, err) {
		return
	}
	writeJSON(w, http.StatusOK, rows)
}

// POST /api/v1/integrations/{platform}/connect — return the authorize URL.
func (s *Server) integrationsConnect(w http.ResponseWriter, r *http.Request) {
	platform := chi.URLParam(r, "platform")
	if !supportedIntegrationPlatforms[platform] {
		writeError(w, http.StatusBadRequest, "Unsupported platform '"+platform+"'")
		return
	}
	u := authUserFromCtx(r.Context())
	orgID, err := store.DefaultOrgForUser(r.Context(), s.DB, u.ID)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusBadRequest, "User has no org membership; cannot connect integration")
		return
	}
	if storeError(w, err) {
		return
	}
	clientID, _ := s.integrationClientCreds(platform)
	if clientID == "" {
		writeError(w, http.StatusInternalServerError, titleCase(platform)+" OAuth is not configured")
		return
	}
	state, err := store.BuildOAuthState(s.Cfg.OAuthStateSecret(), orgID, u.ID, platform)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "internal error")
		return
	}
	prov, _ := oauth.ByName(platform)
	authURL := prov.BuildAuthorizeURL(clientID, s.integrationRedirectURI(platform), state)
	writeJSON(w, http.StatusOK, map[string]string{"authorization_url": authURL})
}

// GET /api/v1/integrations/{platform}/callback — PUBLIC. Exchange + store + 302.
func (s *Server) integrationsCallback(w http.ResponseWriter, r *http.Request) {
	platform := chi.URLParam(r, "platform")
	returnTo := strings.TrimRight(s.Cfg.FrontendURL, "/") + "/integrations"
	if !supportedIntegrationPlatforms[platform] {
		writeError(w, http.StatusBadRequest, "Unsupported platform '"+platform+"'")
		return
	}
	q := r.URL.Query()
	if e := q.Get("error"); e != "" {
		http.Redirect(w, r, returnTo+"?error="+url.QueryEscape(e), http.StatusFound)
		return
	}
	code, state := q.Get("code"), q.Get("state")
	if code == "" || state == "" {
		writeError(w, http.StatusBadRequest, "Missing code or state in OAuth callback")
		return
	}
	claims, err := store.VerifyOAuthState(s.Cfg.OAuthStateSecret(), state)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid OAuth state")
		return
	}
	if claims.Platform != platform {
		writeError(w, http.StatusBadRequest, "OAuth state platform mismatch")
		return
	}

	clientID, clientSecret := s.integrationClientCreds(platform)
	prov, _ := oauth.ByName(platform)
	tokens, err := prov.ExchangeCode(r.Context(), oauthHTTPClient, clientID, clientSecret, s.integrationRedirectURI(platform), code)
	if err != nil {
		http.Redirect(w, r, returnTo+"?error=exchange_failed", http.StatusFound)
		return
	}
	fkey, err := fernet.ParseKey(s.Cfg.TokenEncryptionKey)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "token encryption is not configured")
		return
	}
	if err := store.SaveCredentials(r.Context(), s.DB, fkey, store.CredentialInput{
		OrgID: claims.OrgID, UserID: claims.UserID, Platform: platform,
		AccessToken: tokens.AccessToken, RefreshToken: tokens.RefreshToken,
		ExpiresInSeconds: tokens.ExpiresIn, Scopes: tokens.Scope,
	}); err != nil {
		writeError(w, http.StatusInternalServerError, "failed to save credentials")
		return
	}
	http.Redirect(w, r, returnTo+"?connected="+platform, http.StatusFound)
}

// DELETE /api/v1/integrations/{platform}/disconnect — soft-delete the credential.
func (s *Server) integrationsDisconnect(w http.ResponseWriter, r *http.Request) {
	platform := chi.URLParam(r, "platform")
	if !supportedIntegrationPlatforms[platform] {
		writeError(w, http.StatusBadRequest, "Unsupported platform '"+platform+"'")
		return
	}
	u := authUserFromCtx(r.Context())
	orgID, err := store.DefaultOrgForUser(r.Context(), s.DB, u.ID)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusBadRequest, "User has no org membership; cannot connect integration")
		return
	}
	if storeError(w, err) {
		return
	}
	if storeError(w, store.DeactivateCredentials(r.Context(), s.DB, orgID, u.ID, platform)) {
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
