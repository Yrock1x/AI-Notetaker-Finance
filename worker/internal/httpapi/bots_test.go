package httpapi

import (
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/config"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/db"
)

// botTestServer is an internal-token server with a Recall key + public API URL.
func botTestServer(t *testing.T) (*httptest.Server, *http.Client, *sql.DB) {
	t.Helper()
	conn, err := db.Open(filepath.Join(t.TempDir(), "t.db"))
	if err != nil {
		t.Fatalf("open: %v", err)
	}
	if err := db.Migrate(conn); err != nil {
		t.Fatalf("migrate: %v", err)
	}
	cfg := &config.Config{
		AppEnv: "development", SessionJWTSecret: "unit-test-secret-0123456789abcdef",
		SessionCookieName: "cogni_session", StorageRoot: t.TempDir(), StorageSigningKey: testStorageKey,
		WorkerInternalToken: testInternalToken, RecallAPIKey: "recall-key", RecallRegion: "us-west-2",
		PublicAPIURL: "https://worker.example",
	}
	ts := httptest.NewServer((&Server{Cfg: cfg, DB: conn}).Router())
	t.Cleanup(func() { ts.Close(); conn.Close() })
	return ts, &http.Client{}, conn
}

// seedUserOrgDeal provisions a real user+org (via register) and a deal (via the
// API) so we don't have to hand-seed every NOT NULL column.
func seedUserOrgDeal(t *testing.T, ts *httptest.Server, conn *sql.DB, email string) (org, user, deal string, client *http.Client) {
	t.Helper()
	client, org = registerUser(t, ts, conn, email)
	if err := conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id=? LIMIT 1", org).Scan(&user); err != nil {
		t.Fatalf("user lookup: %v", err)
	}
	resp := postJSON(t, client, ts.URL+"/api/v1/deals", map[string]any{"org_id": org, "name": "Deal"})
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)
	deal = d.ID
	return
}

func mustExec(t *testing.T, conn *sql.DB, q string, args ...any) {
	t.Helper()
	if _, err := conn.Exec(q, args...); err != nil {
		t.Fatalf("seed exec: %v\n%s", err, q)
	}
}

func TestBotAutoScheduleDue(t *testing.T) {
	ts, _, conn := botTestServer(t)
	org, user, deal, a := seedUserOrgDeal(t, ts, conn, "bot-asd@x.com")
	now := time.Now().UTC()
	soon := now.Add(5 * time.Minute).Format(time.RFC3339)
	// A due, bot-enabled, deal-assigned zoom meeting in the window.
	mustExec(t, conn, `INSERT INTO meetings(id,org_id,deal_id,title,meeting_date,source,source_url,status,bot_enabled,created_by,created_at,updated_at)
	  VALUES('m-due',?,?,?,?,?,?,?,?,?,?,?)`, org, deal, "Due", soon, "zoom", "https://zoom.us/j/1", "uploading", true, user, "x", "x")

	r := postInternal(t, ts, a, "/bot/auto-schedule-due", map[string]any{}, testInternalToken)
	if r.StatusCode != 200 {
		t.Fatalf("auto-schedule: %d", r.StatusCode)
	}
	var res struct {
		Scheduled []map[string]any `json:"scheduled"`
	}
	_ = json.NewDecoder(r.Body).Decode(&res)
	if len(res.Scheduled) != 1 || res.Scheduled[0]["meeting_id"] != "m-due" {
		t.Fatalf("scheduled=%+v, want 1 for m-due", res.Scheduled)
	}
	var sessions int
	_ = conn.QueryRow("SELECT COUNT(*) FROM meeting_bot_sessions WHERE meeting_id='m-due' AND platform='zoom'").Scan(&sessions)
	if sessions != 1 {
		t.Fatalf("bot sessions=%d, want 1", sessions)
	}
	// Idempotent: re-run creates nothing new (dedupe on active session).
	r2 := postInternal(t, ts, a, "/bot/auto-schedule-due", map[string]any{}, testInternalToken)
	var res2 struct {
		Scheduled []map[string]any `json:"scheduled"`
	}
	_ = json.NewDecoder(r2.Body).Decode(&res2)
	if len(res2.Scheduled) != 0 {
		t.Fatalf("re-run scheduled=%d, want 0 (dedupe)", len(res2.Scheduled))
	}
}

// TestRecallBotStatusChange covers the bot.* lifecycle handling on the recall
// webhook (the adversarial-review gap): in_call_recording -> session+meeting
// recording; done -> session completed (and would fire meeting/bot-completed).
func TestRecallBotStatusChange(t *testing.T) {
	ts, _, conn := botTestServer(t) // no RecallWebhookSecret -> unsigned webhooks accepted
	org, user, deal, _ := seedUserOrgDeal(t, ts, conn, "bot-status@x.com")
	mustExec(t, conn, `INSERT INTO meetings(id,org_id,deal_id,title,source,status,bot_enabled,created_by,created_at,updated_at)
	  VALUES('m-s',?,?,?,?,?,?,?,?,?)`, org, deal, "M", "zoom", "scheduled", true, user, "x", "x")
	mustExec(t, conn, `INSERT INTO meeting_bot_sessions(id,org_id,deal_id,meeting_id,platform,meeting_url,status,recall_bot_id,consent_obtained,created_by,created_at,updated_at)
	  VALUES('bs-s',?,?,?,?,?,?,?,?,?,?,?)`, org, deal, "m-s", "zoom", "https://zoom.us/j/1", "joining", "rb-1", false, user, "x", "x")

	post := func(body string) int {
		resp, err := http.Post(ts.URL+"/api/v1/webhooks/recall", "application/json", strings.NewReader(body))
		if err != nil {
			t.Fatalf("webhook: %v", err)
		}
		resp.Body.Close()
		return resp.StatusCode
	}

	// in_call_recording -> session 'recording', meeting 'recording'.
	if c := post(`{"event":"bot.in_call_recording","data":{"bot":{"id":"rb-1"},"data":{"code":"in_call_recording"}}}`); c != 200 {
		t.Fatalf("recording event: %d", c)
	}
	var ss, ms string
	_ = conn.QueryRow("SELECT status FROM meeting_bot_sessions WHERE id='bs-s'").Scan(&ss)
	_ = conn.QueryRow("SELECT status FROM meetings WHERE id='m-s'").Scan(&ms)
	if ss != "recording" || ms != "recording" {
		t.Fatalf("after recording: session=%q meeting=%q", ss, ms)
	}

	// done -> session 'completed' (and fires meeting/bot-completed, no-op w/o key).
	if c := post(`{"event":"bot.done","data":{"bot":{"id":"rb-1"},"data":{"code":"done"}}}`); c != 200 {
		t.Fatalf("done event: %d", c)
	}
	_ = conn.QueryRow("SELECT status FROM meeting_bot_sessions WHERE id='bs-s'").Scan(&ss)
	if ss != "completed" {
		t.Fatalf("after done: session=%q, want completed", ss)
	}

	// Unknown bot -> handled:false, still 200.
	if c := post(`{"event":"bot.fatal","data":{"bot":{"id":"nope"},"data":{"code":"fatal"}}}`); c != 200 {
		t.Fatalf("unknown bot: %d", c)
	}
}

// fakeRecallRT serves the Recall create_bot + get_bot + the transcript download.
type fakeRecallRT struct{}

func (fakeRecallRT) RoundTrip(req *http.Request) (*http.Response, error) {
	body := `{}`
	switch {
	case strings.Contains(req.URL.Host, "recall.ai") && strings.HasSuffix(req.URL.Path, "/bot") && req.Method == "POST":
		body = `{"id":"bot-xyz"}`
	case strings.Contains(req.URL.Host, "recall.ai") && strings.Contains(req.URL.Path, "/bot/bot-xyz") && req.Method == "GET":
		body = `{"id":"bot-xyz","recordings":[{"media_shortcuts":{"transcript":{"data":{"download_url":"https://s3.example/transcript"}},"meeting_metadata":{"data":{"download_url":"https://s3.example/meta"}}}}]}`
	case strings.Contains(req.URL.Host, "s3.example") && strings.HasSuffix(req.URL.Path, "/transcript"):
		body = `[{"participant":{"id":1,"name":"Alice"},"words":[{"text":"Hello","start_timestamp":{"relative":0.0},"end_timestamp":{"relative":0.5}},{"text":"team","start_timestamp":{"relative":0.5},"end_timestamp":{"relative":1.0}}]},
		         {"participant":{"id":2,"name":"Bob"},"words":[{"text":"Hi","start_timestamp":{"relative":1.2},"end_timestamp":{"relative":1.5}}]}]`
	case strings.Contains(req.URL.Host, "s3.example") && strings.HasSuffix(req.URL.Path, "/meta"):
		body = `{"title":"Real Meeting Title"}`
	}
	return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)),
		Header: http.Header{"Content-Type": []string{"application/json"}}}, nil
}

func TestBotStartAndFinalize(t *testing.T) {
	ts, _, conn := botTestServer(t)
	org, user, deal, a := seedUserOrgDeal(t, ts, conn, "bot-sf@x.com")
	mustExec(t, conn, `INSERT INTO meeting_bot_sessions(id,org_id,deal_id,platform,meeting_url,status,consent_obtained,created_by,created_at,updated_at)
	  VALUES('bs-1',?,?,?,?,?,?,?,?,?)`, org, deal, "zoom", "https://zoom.us/j/9", "scheduled", false, user, "x", "x")

	prevRecall := recallHTTPClient
	prevOAuth := oauthHTTPClient
	recallHTTPClient = &http.Client{Transport: fakeRecallRT{}}
	oauthHTTPClient = &http.Client{Transport: fakeRecallRT{}} // botFetchJSON uses oauthHTTPClient for the S3 download
	t.Cleanup(func() { recallHTTPClient = prevRecall; oauthHTTPClient = prevOAuth })

	// start: creates the meeting, calls Recall, marks joining.
	r := postInternal(t, ts, a, "/bot/start", map[string]any{"session_id": "bs-1"}, testInternalToken)
	if r.StatusCode != 200 {
		t.Fatalf("start: %d", r.StatusCode)
	}
	var st struct {
		Status      string `json:"status"`
		RecallBotID string `json:"recall_bot_id"`
	}
	_ = json.NewDecoder(r.Body).Decode(&st)
	if st.Status != "joining" || st.RecallBotID != "bot-xyz" {
		t.Fatalf("start result=%+v", st)
	}
	var meetingID, sessStatus string
	_ = conn.QueryRow("SELECT meeting_id, status FROM meeting_bot_sessions WHERE id='bs-1'").Scan(&meetingID, &sessStatus)
	if meetingID == "" || sessStatus != "joining" {
		t.Fatalf("session after start: meeting=%q status=%q", meetingID, sessStatus)
	}

	// finalize: pulls transcript + participants, flips meeting to uploaded, sets title.
	rf := postInternal(t, ts, a, "/bot/finalize", map[string]any{"session_id": "bs-1"}, testInternalToken)
	if rf.StatusCode != 200 {
		t.Fatalf("finalize: %d", rf.StatusCode)
	}
	var fin struct {
		SegmentCount     int `json:"segment_count"`
		ParticipantCount int `json:"participant_count"`
	}
	_ = json.NewDecoder(rf.Body).Decode(&fin)
	if fin.SegmentCount != 2 || fin.ParticipantCount != 2 {
		t.Fatalf("finalize result=%+v, want 2 segments / 2 participants", fin)
	}
	var segs, parts int
	_ = conn.QueryRow("SELECT COUNT(*) FROM transcript_segments WHERE meeting_id=? AND is_partial=0", meetingID).Scan(&segs)
	_ = conn.QueryRow("SELECT COUNT(*) FROM meeting_participants WHERE meeting_id=?", meetingID).Scan(&parts)
	if segs != 2 || parts != 2 {
		t.Fatalf("db: segments=%d participants=%d", segs, parts)
	}
	var status, title string
	_ = conn.QueryRow("SELECT status, title FROM meetings WHERE id=?", meetingID).Scan(&status, &title)
	if status != "uploaded" {
		t.Fatalf("meeting status=%q, want uploaded", status)
	}
	if title != "Real Meeting Title" {
		t.Fatalf("title=%q, want replaced placeholder", title)
	}
}
