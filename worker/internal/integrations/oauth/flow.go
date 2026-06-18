// Package oauth ports app/integrations/oauth_flow.py + the per-provider configs
// (google/microsoft/zoom) for the integrations CONNECT flow (calendar/recording
// scopes + refresh tokens) — distinct from the login flow in httpapi/oauth.go,
// which only needs openid email profile.
package oauth

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"
)

// Provider captures the few knobs Zoom/Microsoft/Google differ on (ports
// OAuthProvider). IncludeScopeInAuthorize defaults true; set the negatives.
type Provider struct {
	Name                    string
	AuthorizeURL            string
	TokenURL                string
	Scopes                  []string
	UseBasicAuth            bool // Zoom: HTTP Basic on the token endpoint
	OmitScopeInAuthorize    bool // Zoom omits scope on the authorize URL
	SendScopeInTokenRequest bool // Microsoft echoes scope in token/refresh
	ExtraAuthorizeParams    map[string]string
}

// BuildAuthorizeURL builds the consent URL (ports build_authorize_url).
func (p Provider) BuildAuthorizeURL(clientID, redirectURI, state string) string {
	q := url.Values{}
	q.Set("client_id", clientID)
	q.Set("response_type", "code")
	q.Set("redirect_uri", redirectURI)
	q.Set("state", state)
	if !p.OmitScopeInAuthorize {
		q.Set("scope", strings.Join(p.Scopes, " "))
	}
	for k, v := range p.ExtraAuthorizeParams {
		q.Set(k, v)
	}
	return p.AuthorizeURL + "?" + q.Encode()
}

// Tokens is the normalized token response (ports the dict from _post_token).
type Tokens struct {
	AccessToken  string `json:"access_token"`
	RefreshToken string `json:"refresh_token"`
	ExpiresIn    int    `json:"expires_in"`
	Scope        string `json:"scope"`
	TokenType    string `json:"token_type"`
}

// ExchangeCode swaps an authorization code for tokens (ports exchange_code).
func (p Provider) ExchangeCode(ctx context.Context, hc *http.Client, clientID, clientSecret, redirectURI, code string) (Tokens, error) {
	return p.postToken(ctx, hc, url.Values{
		"grant_type":   {"authorization_code"},
		"code":         {code},
		"redirect_uri": {redirectURI},
	}, clientID, clientSecret)
}

// Refresh exchanges a refresh token for a new access token (ports refresh).
func (p Provider) Refresh(ctx context.Context, hc *http.Client, clientID, clientSecret, refreshToken string) (Tokens, error) {
	return p.postToken(ctx, hc, url.Values{
		"grant_type":    {"refresh_token"},
		"refresh_token": {refreshToken},
	}, clientID, clientSecret)
}

func (p Provider) postToken(ctx context.Context, hc *http.Client, data url.Values, clientID, clientSecret string) (Tokens, error) {
	headers := map[string]string{"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"}
	if p.UseBasicAuth {
		headers["Authorization"] = "Basic " + base64.StdEncoding.EncodeToString([]byte(clientID+":"+clientSecret))
	} else {
		data.Set("client_id", clientID)
		data.Set("client_secret", clientSecret)
	}
	if p.SendScopeInTokenRequest {
		data.Set("scope", strings.Join(p.Scopes, " "))
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, p.TokenURL, strings.NewReader(data.Encode()))
	if err != nil {
		return Tokens{}, err
	}
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := hc.Do(req)
	if err != nil {
		return Tokens{}, err
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if resp.StatusCode >= 400 {
		return Tokens{}, &TokenError{Provider: p.Name, Status: resp.StatusCode}
	}
	var t Tokens
	if err := json.Unmarshal(body, &t); err != nil || t.AccessToken == "" {
		return Tokens{}, &TokenError{Provider: p.Name, Status: resp.StatusCode}
	}
	return t, nil
}

// TokenError marks a provider token-endpoint failure.
type TokenError struct {
	Provider string
	Status   int
}

func (e *TokenError) Error() string { return e.Provider + " token request failed" }

// ---- the three integration providers (port app/integrations/*/oauth.py) ----

var Google = Provider{
	Name:         "google",
	AuthorizeURL: "https://accounts.google.com/o/oauth2/v2/auth",
	TokenURL:     "https://oauth2.googleapis.com/token",
	Scopes: []string{
		"openid", "email", "profile",
		"https://www.googleapis.com/auth/calendar.readonly",
		"https://www.googleapis.com/auth/calendar.events.readonly",
	},
	ExtraAuthorizeParams: map[string]string{
		"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true",
	},
}

var Microsoft = Provider{
	Name:         "microsoft",
	AuthorizeURL: "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
	TokenURL:     "https://login.microsoftonline.com/common/oauth2/v2.0/token",
	Scopes: []string{
		"offline_access", "openid", "profile", "email",
		"User.Read", "Calendars.Read", "OnlineMeetings.Read", "Chat.Read",
	},
	SendScopeInTokenRequest: true,
	ExtraAuthorizeParams:    map[string]string{"response_mode": "query", "prompt": "consent"},
}

var Zoom = Provider{
	Name:                 "zoom",
	AuthorizeURL:         "https://zoom.us/oauth/authorize",
	TokenURL:             "https://zoom.us/oauth/token",
	Scopes:               []string{"user:read", "meeting:read", "recording:read"},
	UseBasicAuth:         true,
	OmitScopeInAuthorize: true,
}

// ByName returns the provider config for a supported platform.
func ByName(platform string) (Provider, bool) {
	switch platform {
	case "google":
		return Google, true
	case "microsoft":
		return Microsoft, true
	case "zoom":
		return Zoom, true
	}
	return Provider{}, false
}
