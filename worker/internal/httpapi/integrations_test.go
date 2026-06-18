package httpapi

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
)

func TestIntegrationsConnect(t *testing.T) {
	ts, _, conn := oauthTestServer(t)
	a, _ := registerUser(t, ts, conn, "int-connect@x.com")

	// Unsupported platform -> 400.
	if r := postJSON(t, a, ts.URL+"/api/v1/integrations/slack/connect", nil); r.StatusCode != 400 {
		t.Fatalf("unsupported: %d, want 400", r.StatusCode)
	}
	// google -> 200 {authorization_url} to accounts.google.com w/ state + calendar scope.
	r := postJSON(t, a, ts.URL+"/api/v1/integrations/google/connect", nil)
	if r.StatusCode != 200 {
		t.Fatalf("connect: %d, want 200", r.StatusCode)
	}
	var body struct {
		AuthorizationURL string `json:"authorization_url"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body)
	u, _ := url.Parse(body.AuthorizationURL)
	if u.Host != "accounts.google.com" {
		t.Fatalf("authorize host=%s", u.Host)
	}
	q := u.Query()
	if q.Get("state") == "" || q.Get("access_type") != "offline" {
		t.Fatalf("authorize params=%v", q)
	}
	if !strings.Contains(q.Get("scope"), "calendar.readonly") {
		t.Fatalf("scope missing calendar: %s", q.Get("scope"))
	}
}

func TestIntegrationsConnectNotConfigured(t *testing.T) {
	ts, _, conn := testServer(t) // no Google creds
	a, _ := registerUser(t, ts, conn, "int-noconf@x.com")
	if r := postJSON(t, a, ts.URL+"/api/v1/integrations/google/connect", nil); r.StatusCode != 500 {
		t.Fatalf("not configured: %d, want 500", r.StatusCode)
	}
}

// fakeIntegrationRT returns a full token set (incl. refresh + expiry) for the
// provider token endpoint.
type fakeIntegrationRT struct{}

func (fakeIntegrationRT) RoundTrip(req *http.Request) (*http.Response, error) {
	body := `{}`
	if strings.Contains(req.URL.Host, "oauth2.googleapis.com") {
		body = `{"access_token":"acc-tok-123","refresh_token":"ref-tok-456","expires_in":3600,"scope":"openid email calendar.readonly","token_type":"Bearer"}`
	}
	return &http.Response{
		StatusCode: 200,
		Body:       io.NopCloser(strings.NewReader(body)),
		Header:     http.Header{"Content-Type": []string{"application/json"}},
	}, nil
}

func TestIntegrationsCallbackStoresEncryptedCredentials(t *testing.T) {
	ts, srv, conn := oauthTestServer(t)
	a, orgA := registerUser(t, ts, conn, "int-cb@x.com")

	// Resolve the user id for the state token.
	var userID string
	if err := conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id=? LIMIT 1", orgA).Scan(&userID); err != nil {
		t.Fatalf("lookup user: %v", err)
	}
	state, err := store.BuildOAuthState(srv.Cfg.OAuthStateSecret(), orgA, userID, "google")
	if err != nil {
		t.Fatalf("build state: %v", err)
	}

	prev := oauthHTTPClient
	oauthHTTPClient = &http.Client{Transport: fakeIntegrationRT{}}
	t.Cleanup(func() { oauthHTTPClient = prev })

	// Callback is public (no auth cookie).
	r, _ := noRedirect().Get(ts.URL + "/api/v1/integrations/google/callback?code=auth-code&state=" + url.QueryEscape(state))
	if r.StatusCode != 302 {
		t.Fatalf("callback: %d, want 302", r.StatusCode)
	}
	if loc := r.Header.Get("Location"); loc != "https://frontend.example/integrations?connected=google" {
		t.Fatalf("location=%s", loc)
	}

	// The credential row exists, is active, and the tokens decrypt to the originals.
	var accessEnc string
	var refreshEnc *string
	var active bool
	err = conn.QueryRow(
		"SELECT access_token_encrypted, refresh_token_encrypted, is_active FROM integration_credentials WHERE org_id=? AND user_id=? AND platform='google'",
		orgA, userID).Scan(&accessEnc, &refreshEnc, &active)
	if err != nil {
		t.Fatalf("credential row: %v", err)
	}
	if !active {
		t.Fatalf("credential not active")
	}
	fkey, _ := fernet.ParseKey(srv.Cfg.TokenEncryptionKey)
	acc, err := fkey.Decrypt(accessEnc)
	if err != nil || string(acc) != "acc-tok-123" {
		t.Fatalf("access token decrypt=%q err=%v", acc, err)
	}
	if refreshEnc == nil {
		t.Fatalf("refresh token not stored")
	}
	ref, err := fkey.Decrypt(*refreshEnc)
	if err != nil || string(ref) != "ref-tok-456" {
		t.Fatalf("refresh token decrypt=%q err=%v", ref, err)
	}

	// It shows in the authed list with is_active=true.
	lr, _ := a.Get(ts.URL + "/api/v1/integrations")
	var list []store.IntegrationRow
	_ = json.NewDecoder(lr.Body).Decode(&list)
	if len(list) != 1 || list[0].Platform != "google" || !list[0].IsActive {
		t.Fatalf("list=%+v", list)
	}

	// Disconnect -> 204, list goes empty.
	del, _ := http.NewRequest("DELETE", ts.URL+"/api/v1/integrations/google/disconnect", nil)
	if dr, _ := a.Do(del); dr.StatusCode != 204 {
		t.Fatalf("disconnect: %d, want 204", dr.StatusCode)
	}
	lr2, _ := a.Get(ts.URL + "/api/v1/integrations")
	var list2 []store.IntegrationRow
	_ = json.NewDecoder(lr2.Body).Decode(&list2)
	if len(list2) != 0 {
		t.Fatalf("after disconnect list=%+v, want empty", list2)
	}
}

func TestIntegrationsCallbackBadState(t *testing.T) {
	ts, _, _ := oauthTestServer(t)
	// Garbage state -> 400.
	r, _ := noRedirect().Get(ts.URL + "/api/v1/integrations/google/callback?code=x&state=not-a-jwt")
	if r.StatusCode != 400 {
		t.Fatalf("bad state: %d, want 400", r.StatusCode)
	}
}
