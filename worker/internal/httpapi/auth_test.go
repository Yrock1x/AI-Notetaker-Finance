package httpapi

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"path/filepath"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
)

func testServer(t *testing.T) (*httptest.Server, *http.Client, *sql.DB) {
	t.Helper()
	conn, err := db.Open(filepath.Join(t.TempDir(), "t.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	cfg := &config.Config{
		AppEnv:            "development",
		SessionJWTSecret:  "unit-test-secret-0123456789abcdef",
		SessionCookieName: "cogni_session",
		CORSOrigins:       "http://localhost:3000",
		FrontendURL:       "http://localhost:3000",
		StorageRoot:       t.TempDir(),
		StorageSigningKey: testStorageKey,
	}
	ts := httptest.NewServer((&Server{Cfg: cfg, DB: conn}).Router())
	jar, _ := cookiejar.New(nil)
	t.Cleanup(func() { ts.Close(); conn.Close() })
	return ts, &http.Client{Jar: jar}, conn
}

func postJSON(t *testing.T, c *http.Client, url string, body any) *http.Response {
	t.Helper()
	b, _ := json.Marshal(body)
	resp, err := c.Post(url, "application/json", bytes.NewReader(b))
	if err != nil {
		t.Fatalf("POST %s: %v", url, err)
	}
	return resp
}

func TestAuthFlow(t *testing.T) {
	ts, c, _ := testServer(t)
	base := ts.URL + "/api/v1/auth"

	// register
	resp := postJSON(t, c, base+"/register", map[string]any{
		"email": "User@Example.com", "password": "Sup3rSecret!", "full_name": "A B"})
	if resp.StatusCode != 200 {
		t.Fatalf("register status=%d", resp.StatusCode)
	}
	var sr sessionResponse
	_ = json.NewDecoder(resp.Body).Decode(&sr)
	if sr.Email != "User@Example.com" || sr.ID == "" || sr.FullName != "A B" {
		t.Fatalf("register body=%+v", sr)
	}
	var hasCookie bool
	for _, ck := range resp.Cookies() {
		if ck.Name == "cogni_session" && ck.Value != "" && ck.HttpOnly {
			hasCookie = true
		}
	}
	if !hasCookie {
		t.Fatalf("register did not set httpOnly cogni_session cookie")
	}

	// session (cookie auto-sent by the jar)
	r2, _ := c.Get(base + "/session")
	if r2.StatusCode != 200 {
		t.Fatalf("session status=%d", r2.StatusCode)
	}
	var sr2 sessionResponse
	_ = json.NewDecoder(r2.Body).Decode(&sr2)
	if sr2.ID != sr.ID {
		t.Fatalf("session id mismatch: %s vs %s", sr2.ID, sr.ID)
	}

	// re-register same email -> 409
	if r := postJSON(t, c, base+"/register", map[string]any{"email": "user@example.com", "password": "Sup3rSecret!"}); r.StatusCode != 409 {
		t.Fatalf("re-register status=%d, want 409", r.StatusCode)
	}

	// signout
	if r := postJSON(t, c, base+"/signout", map[string]any{}); r.StatusCode != 200 {
		t.Fatalf("signout status=%d", r.StatusCode)
	}

	// login (case-insensitive email)
	if r := postJSON(t, c, base+"/login", map[string]any{"email": "USER@example.com", "password": "Sup3rSecret!"}); r.StatusCode != 200 {
		t.Fatalf("login status=%d, want 200", r.StatusCode)
	}
	// wrong password -> 401
	if r := postJSON(t, c, base+"/login", map[string]any{"email": "user@example.com", "password": "nope"}); r.StatusCode != 401 {
		t.Fatalf("bad login status=%d, want 401", r.StatusCode)
	}
	// short password on register -> 422
	if r := postJSON(t, c, base+"/register", map[string]any{"email": "new@example.com", "password": "short"}); r.StatusCode != 422 {
		t.Fatalf("short-pw register status=%d, want 422", r.StatusCode)
	}

	// session without a cookie -> 401
	bare := &http.Client{}
	r3, _ := bare.Get(base + "/session")
	if r3.StatusCode != 401 {
		t.Fatalf("unauth session status=%d, want 401", r3.StatusCode)
	}
}
