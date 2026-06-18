package httpapi

import (
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

const testInternalToken = "internal-test-token-0123456789abcdef"

// internalTestServer is testServer + a WORKER_INTERNAL_TOKEN so the /internal/*
// surface authenticates instead of 500ing on an unset token.
func internalTestServer(t *testing.T) (*httptest.Server, *http.Client, *sql.DB) {
	t.Helper()
	conn, err := db.Open(filepath.Join(t.TempDir(), "t.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	cfg := &config.Config{
		AppEnv:              "development",
		SessionJWTSecret:    "unit-test-secret-0123456789abcdef",
		SessionCookieName:   "cogni_session",
		CORSOrigins:         "http://localhost:3000",
		FrontendURL:         "http://localhost:3000",
		StorageRoot:         t.TempDir(),
		StorageSigningKey:   testStorageKey,
		WorkerInternalToken: testInternalToken,
	}
	ts := httptest.NewServer((&Server{Cfg: cfg, DB: conn}).Router())
	jar, _ := cookiejar.New(nil)
	t.Cleanup(func() { ts.Close(); conn.Close() })
	return ts, &http.Client{Jar: jar}, conn
}

func postInternal(t *testing.T, ts *httptest.Server, c *http.Client, path string, body any, token string) *http.Response {
	t.Helper()
	req, _ := http.NewRequest("POST", ts.URL+"/api/v1/internal"+path, jsonBody(body))
	req.Header.Set("Content-Type", "application/json")
	if token != "" {
		req.Header.Set("X-Internal-Token", token)
	}
	resp, err := c.Do(req)
	if err != nil {
		t.Fatalf("POST %s: %v", path, err)
	}
	return resp
}

// TestInternalMeetingStatus covers /internal/meeting-status: the Inngest pipeline
// flips a meeting's status (and records errors) as it progresses. Missing token
// is 401; a real update is reflected on the meeting.
func TestInternalMeetingStatus(t *testing.T) {
	ts, _, conn := internalTestServer(t)
	a, orgA := registerUser(t, ts, conn, "instatus@x.com")
	resp := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "Status Co"})
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)
	mr := postJSON(t, a, ts.URL+"/api/v1/deals/"+d.ID+"/meetings", map[string]any{"title": "M", "source": "upload"})
	var m meetingJSON
	_ = json.NewDecoder(mr.Body).Decode(&m)

	// No token -> 401.
	if r := postInternal(t, ts, a, "/meeting-status", map[string]any{"meeting_id": m.ID, "status": "analyzing"}, ""); r.StatusCode != 401 {
		t.Fatalf("no token: %d, want 401", r.StatusCode)
	}
	// With token -> 200 {ok:true}.
	r := postInternal(t, ts, a, "/meeting-status", map[string]any{"meeting_id": m.ID, "status": "analyzed"}, testInternalToken)
	if r.StatusCode != 200 {
		t.Fatalf("meeting-status: %d, want 200", r.StatusCode)
	}
	var ok struct {
		OK bool `json:"ok"`
	}
	_ = json.NewDecoder(r.Body).Decode(&ok)
	if !ok.OK {
		t.Fatalf("ok=false")
	}
	// The meeting now reads back as analyzed.
	gr, _ := a.Get(ts.URL + "/api/v1/meetings/" + m.ID)
	var got meetingJSON
	_ = json.NewDecoder(gr.Body).Decode(&got)
	if got.Status != "analyzed" {
		t.Fatalf("status=%q, want analyzed", got.Status)
	}
	// Unknown meeting -> 404.
	if r := postInternal(t, ts, a, "/meeting-status", map[string]any{"meeting_id": "nope", "status": "x"}, testInternalToken); r.StatusCode != 404 {
		t.Fatalf("unknown meeting: %d, want 404", r.StatusCode)
	}
}

// TestInternalAnalyzeUnstubbed proves /internal/analyze is wired to the analysis
// service (not the old 501 stub): an unknown meeting now 404s (the meeting lookup
// runs) instead of returning 501 NotImplemented.
func TestInternalAnalyzeUnstubbed(t *testing.T) {
	ts, _, conn := internalTestServer(t)
	a, _ := registerUser(t, ts, conn, "inanalyze@x.com")
	r := postInternal(t, ts, a, "/analyze", map[string]any{"meeting_id": "does-not-exist", "call_type": "summarization"}, testInternalToken)
	if r.StatusCode == http.StatusNotImplemented {
		t.Fatalf("analyze still returns 501 (stub not removed)")
	}
	if r.StatusCode != 404 {
		t.Fatalf("analyze unknown meeting: %d, want 404", r.StatusCode)
	}
}

// TestInternalTranscribeReachable proves /internal/transcribe is mounted and
// reaches its handler: a meeting with no file_key returns 400 (not 404-route or
// 501). Full Deepgram transcription needs real audio + a key, so it's exercised
// live, not here.
func TestInternalTranscribeReachable(t *testing.T) {
	ts, _, conn := internalTestServer(t)
	a, orgA := registerUser(t, ts, conn, "intranscribe@x.com")
	resp := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "TR Co"})
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)
	mr := postJSON(t, a, ts.URL+"/api/v1/deals/"+d.ID+"/meetings", map[string]any{"title": "M", "source": "upload"})
	var m meetingJSON
	_ = json.NewDecoder(mr.Body).Decode(&m)

	r := postInternal(t, ts, a, "/transcribe", map[string]any{"meeting_id": m.ID}, testInternalToken)
	if r.StatusCode != 400 {
		t.Fatalf("transcribe no-file_key: %d, want 400", r.StatusCode)
	}
}
