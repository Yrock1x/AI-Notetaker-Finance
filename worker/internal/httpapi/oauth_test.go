package httpapi

import (
	"database/sql"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
)

// oauthTestServer builds a server WITH Google/Microsoft client creds + distinct
// frontend/worker URLs, and exposes the *Server so tests can mint a valid state.
func oauthTestServer(t *testing.T) (*httptest.Server, *Server, *sql.DB) {
	t.Helper()
	conn, err := db.Open(filepath.Join(t.TempDir(), "t.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	cfg := &config.Config{
		AppEnv:                "development",
		SessionJWTSecret:      "unit-test-secret-0123456789abcdef",
		SessionCookieName:     "cogni_session",
		StorageRoot:           t.TempDir(),
		StorageSigningKey:     testStorageKey,
		FrontendURL:           "https://frontend.example",
		PublicAPIURL:          "https://worker.example",
		GoogleClientID:        "gcid",
		GoogleClientSecret:    "gsecret",
		MicrosoftClientID:     "mcid",
		MicrosoftClientSecret: "msecret",
		ZoomClientID:          "zcid",
		ZoomClientSecret:      "zsecret",
		WorkerInternalToken:   "internal-token-0123456789abcdef0",
		// Valid Fernet key (the official spec key) for credential encryption.
		TokenEncryptionKey: "cw_0x689RpI-jtRR7oE8h_eQsKImvJapLeSbXpwF4e4=",
	}
	srv := &Server{Cfg: cfg, DB: conn}
	ts := httptest.NewServer(srv.Router())
	t.Cleanup(func() { ts.Close(); conn.Close() })
	return ts, srv, conn
}

// noRedirect returns a client that surfaces 3xx instead of following them.
func noRedirect() *http.Client {
	return &http.Client{CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
}

func TestOAuthLoginUnknownProvider(t *testing.T) {
	ts, _, _ := oauthTestServer(t)
	r, _ := noRedirect().Get(ts.URL + "/api/v1/auth/login/github")
	if r.StatusCode != 404 {
		t.Fatalf("unknown provider: %d, want 404", r.StatusCode)
	}
}

func TestOAuthLoginNotConfigured(t *testing.T) {
	// testServer has no Google creds -> 503.
	ts, _, _ := testServer(t)
	r, _ := noRedirect().Get(ts.URL + "/api/v1/auth/login/google")
	if r.StatusCode != 503 {
		t.Fatalf("not configured: %d, want 503", r.StatusCode)
	}
}

func TestOAuthLoginRedirectsWithState(t *testing.T) {
	ts, _, _ := oauthTestServer(t)
	r, _ := noRedirect().Get(ts.URL + "/api/v1/auth/login/google?next=/deals")
	if r.StatusCode != 302 {
		t.Fatalf("login: %d, want 302", r.StatusCode)
	}
	loc, _ := url.Parse(r.Header.Get("Location"))
	if loc.Host != "accounts.google.com" {
		t.Fatalf("redirect host=%s", loc.Host)
	}
	q := loc.Query()
	if q.Get("client_id") != "gcid" || q.Get("response_type") != "code" || q.Get("state") == "" {
		t.Fatalf("authorize params=%v", q)
	}
	if q.Get("redirect_uri") != "https://worker.example/api/v1/auth/callback/google" {
		t.Fatalf("redirect_uri=%s", q.Get("redirect_uri"))
	}
	// A signed state cookie must be set.
	var hasState bool
	for _, c := range r.Cookies() {
		if c.Name == oauthStateCookie && c.Value != "" {
			hasState = true
		}
	}
	if !hasState {
		t.Fatalf("no %s cookie set", oauthStateCookie)
	}
}

func TestOAuthStateSignVerifyTamper(t *testing.T) {
	_, srv, _ := oauthTestServer(t)
	tok, err := srv.signOAuthState(oauthStatePayload{State: "abc", Next: "/x", Exp: 1 << 40})
	if err != nil {
		t.Fatalf("sign: %v", err)
	}
	got, ok := srv.verifyOAuthState(tok)
	if !ok || got.State != "abc" || got.Next != "/x" {
		t.Fatalf("verify roundtrip: ok=%v got=%+v", ok, got)
	}
	// Tampered signature -> reject.
	if _, ok := srv.verifyOAuthState(tok + "x"); ok {
		t.Fatalf("tampered token accepted")
	}
	// Expired -> reject.
	expired, _ := srv.signOAuthState(oauthStatePayload{State: "abc", Exp: 1})
	if _, ok := srv.verifyOAuthState(expired); ok {
		t.Fatalf("expired token accepted")
	}
}

func TestOAuthCallbackBadState(t *testing.T) {
	ts, _, _ := oauthTestServer(t)
	// No state cookie at all -> error redirect to the frontend login page.
	r, _ := noRedirect().Get(ts.URL + "/api/v1/auth/callback/google?code=abc&state=xyz")
	if r.StatusCode != 302 {
		t.Fatalf("bad state: %d, want 302", r.StatusCode)
	}
	if loc := r.Header.Get("Location"); !strings.HasPrefix(loc, "https://frontend.example/login?error=") {
		t.Fatalf("location=%s, want frontend /login?error", loc)
	}
}

// fakeOAuthRT intercepts the provider token + userinfo calls so the full callback
// flow can be exercised without real network.
type fakeOAuthRT struct{ email, name string }

func (rt fakeOAuthRT) RoundTrip(req *http.Request) (*http.Response, error) {
	body := `{}`
	switch {
	case strings.Contains(req.URL.Host, "oauth2.googleapis.com"): // token
		body = `{"access_token":"at-123","token_type":"Bearer"}`
	case strings.Contains(req.URL.Host, "openidconnect.googleapis.com"): // userinfo
		body = `{"email":"` + rt.email + `","name":"` + rt.name + `","picture":"https://p/x.png"}`
	}
	return &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     http.Header{"Content-Type": []string{"application/json"}},
	}, nil
}

func TestOAuthCallbackFullFlow(t *testing.T) {
	ts, srv, conn := oauthTestServer(t)

	// Intercept the provider HTTP for the duration of the test.
	prev := oauthHTTPClient
	oauthHTTPClient = &http.Client{Transport: fakeOAuthRT{email: "oauth.user@example.com", name: "OAuth User"}}
	t.Cleanup(func() { oauthHTTPClient = prev })

	// Mint a valid state + present it as both the cookie and the ?state param.
	state := "state-token-xyz"
	stateCookie, err := srv.signOAuthState(oauthStatePayload{State: state, Next: "/deals", Exp: 1 << 40})
	if err != nil {
		t.Fatalf("sign state: %v", err)
	}
	req, _ := http.NewRequest("GET", ts.URL+"/api/v1/auth/callback/google?code=auth-code&state="+state, nil)
	req.AddCookie(&http.Cookie{Name: oauthStateCookie, Value: stateCookie})
	r, err := noRedirect().Do(req)
	if err != nil {
		t.Fatalf("callback: %v", err)
	}
	if r.StatusCode != 302 {
		t.Fatalf("callback: %d, want 302", r.StatusCode)
	}
	if loc := r.Header.Get("Location"); loc != "https://frontend.example/deals" {
		t.Fatalf("location=%s, want frontend /deals", loc)
	}
	// A session cookie was issued.
	var sess string
	for _, c := range r.Cookies() {
		if c.Name == "cogni_session" {
			sess = c.Value
		}
	}
	if sess == "" {
		t.Fatalf("no session cookie issued")
	}
	// The user was provisioned (profile + an org membership exist).
	p, err := store.GetProfileByEmail(req.Context(), conn, "oauth.user@example.com")
	if err != nil || p == nil {
		t.Fatalf("user not provisioned: %v", err)
	}
	if p.FullName != "OAuth User" {
		t.Fatalf("full_name=%q, want 'OAuth User'", p.FullName)
	}
	var orgs int
	_ = conn.QueryRow("SELECT COUNT(*) FROM org_memberships WHERE user_id = ?", p.ID).Scan(&orgs)
	if orgs == 0 {
		t.Fatalf("no org membership provisioned")
	}
}
