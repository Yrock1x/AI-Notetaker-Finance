package httpapi

import (
	"crypto/hmac"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
)

const (
	testZoomSecret  = "zoom-webhook-secret-token"
	testSlackSecret = "slack-signing-secret-value"
	testTeamsSecret = "teams-client-state-secret-0"
)

func webhooksTestServer(t *testing.T) (*httptest.Server, *sql.DB) {
	t.Helper()
	conn, err := db.Open(filepath.Join(t.TempDir(), "t.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	cfg := &config.Config{
		AppEnv:                 "development",
		SessionJWTSecret:       "unit-test-secret-0123456789abcdef",
		SessionCookieName:      "cogni_session",
		StorageRoot:            t.TempDir(),
		StorageSigningKey:      testStorageKey,
		ZoomWebhookSecretToken: testZoomSecret,
		SlackSigningSecret:     testSlackSecret,
		MicrosoftWebhookSecret: testTeamsSecret,
	}
	ts := httptest.NewServer((&Server{Cfg: cfg, DB: conn}).Router())
	t.Cleanup(func() { ts.Close(); conn.Close() })
	return ts, conn
}

func sign(secret, ts, body string) string {
	m := hmac.New(sha256.New, []byte(secret))
	m.Write([]byte("v0:" + ts + ":" + body))
	return "v0=" + hex.EncodeToString(m.Sum(nil))
}

func postRaw(url, body string, headers map[string]string) (*http.Response, []byte) {
	req, _ := http.NewRequest("POST", url, strings.NewReader(body))
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, nil
	}
	b, _ := io.ReadAll(resp.Body)
	resp.Body.Close()
	return resp, b
}

func TestZoomWebhookValidationAndAuth(t *testing.T) {
	ts, _ := webhooksTestServer(t)
	now := strconv.FormatInt(time.Now().Unix(), 10)
	body := `{"event":"endpoint.url_validation","payload":{"plainToken":"plaintok123"}}`

	// Valid signature -> url_validation challenge with encryptedToken = HMAC(plainToken).
	r, b := postRaw(ts.URL+"/api/v1/webhooks/zoom", body, map[string]string{
		"x-zm-request-timestamp": now,
		"x-zm-signature":         sign(testZoomSecret, now, body),
	})
	if r.StatusCode != 200 {
		t.Fatalf("zoom valid: %d", r.StatusCode)
	}
	var ch struct{ PlainToken, EncryptedToken string }
	_ = json.Unmarshal(b, &ch)
	m := hmac.New(sha256.New, []byte(testZoomSecret))
	m.Write([]byte("plaintok123"))
	if ch.PlainToken != "plaintok123" || ch.EncryptedToken != hex.EncodeToString(m.Sum(nil)) {
		t.Fatalf("challenge wrong: %+v", ch)
	}

	// Bad signature -> 401.
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/zoom", body, map[string]string{
		"x-zm-request-timestamp": now, "x-zm-signature": "v0=deadbeef",
	}); r.StatusCode != 401 {
		t.Fatalf("zoom bad sig: %d, want 401", r.StatusCode)
	}
	// Missing headers -> 401.
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/zoom", body, nil); r.StatusCode != 401 {
		t.Fatalf("zoom no headers: %d, want 401", r.StatusCode)
	}
	// Expired timestamp -> 401.
	old := strconv.FormatInt(time.Now().Unix()-1000, 10)
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/zoom", body, map[string]string{
		"x-zm-request-timestamp": old, "x-zm-signature": sign(testZoomSecret, old, body),
	}); r.StatusCode != 401 {
		t.Fatalf("zoom expired: %d, want 401", r.StatusCode)
	}
}

func TestZoomWebhookReplay(t *testing.T) {
	ts, _ := webhooksTestServer(t)
	now := strconv.FormatInt(time.Now().Unix(), 10)
	body := `{"event":"meeting.ended"}`
	h := map[string]string{"x-zm-request-timestamp": now, "x-zm-signature": sign(testZoomSecret, now, body)}
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/zoom", body, h); r.StatusCode != 200 {
		t.Fatalf("zoom first: %d", r.StatusCode)
	}
	// Exact replay (same ts+sig) -> 409.
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/zoom", body, h); r.StatusCode != 409 {
		t.Fatalf("zoom replay: %d, want 409", r.StatusCode)
	}
}

func TestSlackWebhook(t *testing.T) {
	ts, _ := webhooksTestServer(t)
	now := strconv.FormatInt(time.Now().Unix(), 10)
	body := `{"type":"url_verification","challenge":"challenge-xyz"}`
	r, b := postRaw(ts.URL+"/api/v1/webhooks/slack/events", body, map[string]string{
		"X-Slack-Request-Timestamp": now, "X-Slack-Signature": sign(testSlackSecret, now, body),
	})
	if r.StatusCode != 200 {
		t.Fatalf("slack valid: %d", r.StatusCode)
	}
	var ch struct{ Challenge string }
	_ = json.Unmarshal(b, &ch)
	if ch.Challenge != "challenge-xyz" {
		t.Fatalf("challenge=%q", ch.Challenge)
	}
	// Bad signature -> 401.
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/slack/events", body, map[string]string{
		"X-Slack-Request-Timestamp": now, "X-Slack-Signature": "v0=nope",
	}); r.StatusCode != 401 {
		t.Fatalf("slack bad sig: %d, want 401", r.StatusCode)
	}

	// Slash command (form body) -> ephemeral help.
	cmd := "command=%2Fcognisuite&text=help&user_id=U1&channel_id=C1"
	rc, bc := postRaw(ts.URL+"/api/v1/webhooks/slack/commands", cmd, map[string]string{
		"X-Slack-Request-Timestamp": now, "X-Slack-Signature": sign(testSlackSecret, now, cmd),
		"Content-Type": "application/x-www-form-urlencoded",
	})
	if rc.StatusCode != 200 || !strings.Contains(string(bc), "CogniSuite Commands") {
		t.Fatalf("slack command: %d body=%s", rc.StatusCode, bc)
	}
}

func TestTeamsWebhook(t *testing.T) {
	ts, _ := webhooksTestServer(t)
	// validationToken handshake -> plain-text echo.
	r, b := postRaw(ts.URL+"/api/v1/webhooks/teams?validationToken=echo-me", "", nil)
	if r.StatusCode != 200 || string(b) != "echo-me" {
		t.Fatalf("teams validation: %d body=%q", r.StatusCode, b)
	}
	// Valid clientState notification -> 200.
	good := `{"value":[{"clientState":"` + testTeamsSecret + `","resource":"communications/callRecords('rec-1')","changeType":"created","tenantId":"t1"}]}`
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/teams", good, map[string]string{"Content-Type": "application/json"}); r.StatusCode != 200 {
		t.Fatalf("teams valid: %d", r.StatusCode)
	}
	// Wrong clientState -> 401.
	bad := `{"value":[{"clientState":"wrong","resource":"communications/callRecords('rec-1')"}]}`
	if r, _ := postRaw(ts.URL+"/api/v1/webhooks/teams", bad, map[string]string{"Content-Type": "application/json"}); r.StatusCode != 401 {
		t.Fatalf("teams bad clientState: %d, want 401", r.StatusCode)
	}
}

func TestExtractCallRecordID(t *testing.T) {
	cases := map[string]string{
		"communications/callRecords('abc-123')": "abc-123",
		"communications/callRecords/xyz-999":    "xyz-999",
		"communications/callRecords":            "callRecords",
	}
	for in, want := range cases {
		if got := extractCallRecordID(in); got != want {
			t.Fatalf("extractCallRecordID(%q)=%q, want %q", in, got, want)
		}
	}
}
