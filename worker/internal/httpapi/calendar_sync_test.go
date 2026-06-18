package httpapi

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
)

// fakeCalendarRT serves a Google Calendar events response (2 timed events + 1
// all-day event with no dateTime, which sync must skip).
type fakeCalendarRT struct{}

func (fakeCalendarRT) RoundTrip(req *http.Request) (*http.Response, error) {
	body := `{}`
	if strings.Contains(req.URL.Host, "www.googleapis.com") {
		body = `{"items":[
		  {"id":"ev1","summary":"Standup","start":{"dateTime":"2026-07-01T10:00:00Z"},
		   "conferenceData":{"entryPoints":[{"entryPointType":"video","uri":"https://meet.google.com/abc-defg-hij"}]}},
		  {"id":"ev2","summary":"Review","start":{"dateTime":"2026-07-02T10:00:00Z"},"htmlLink":"https://cal.example/ev2"},
		  {"id":"ev3-allday","summary":"Holiday","start":{"date":"2026-07-03"}}
		]}`
	}
	return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)),
		Header: http.Header{"Content-Type": []string{"application/json"}}}, nil
}

func TestInternalCalendarSyncGoogle(t *testing.T) {
	ts, srv, conn := oauthTestServer(t)
	a, orgA := registerUser(t, ts, conn, "cal-sync@x.com")
	var userID string
	if err := conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id=? LIMIT 1", orgA).Scan(&userID); err != nil {
		t.Fatalf("user: %v", err)
	}
	token := srv.Cfg.WorkerInternalToken

	// Seed an active google credential with a far-future expiry (no refresh).
	fkey, _ := fernet.ParseKey(srv.Cfg.TokenEncryptionKey)
	if err := store.SaveCredentials(context.Background(), conn, fkey, store.CredentialInput{
		OrgID: orgA, UserID: userID, Platform: "google",
		AccessToken: "acc-token", RefreshToken: "ref-token", ExpiresInSeconds: 3600,
		Scopes: "calendar.readonly",
	}); err != nil {
		t.Fatalf("seed cred: %v", err)
	}

	prev := oauthHTTPClient
	oauthHTTPClient = &http.Client{Transport: fakeCalendarRT{}}
	t.Cleanup(func() { oauthHTTPClient = prev })

	// list-active-integrations sees the google tuple.
	lreq, _ := http.NewRequest("GET", ts.URL+"/api/v1/internal/calendar/list-active-integrations", nil)
	lreq.Header.Set("X-Internal-Token", token)
	lr, _ := a.Do(lreq)
	var active struct {
		Integrations []store.ActiveCalendarIntegration `json:"integrations"`
	}
	_ = json.NewDecoder(lr.Body).Decode(&active)
	if len(active.Integrations) != 1 || active.Integrations[0].Platform != "google" {
		t.Fatalf("active integrations=%+v", active.Integrations)
	}

	// Sync: 3 events seen, 2 timed -> upserted.
	r := postInternal(t, ts, a, "/calendar/sync", map[string]any{"user_id": userID, "org_id": orgA, "platform": "google"}, token)
	if r.StatusCode != 200 {
		t.Fatalf("sync: %d, want 200", r.StatusCode)
	}
	var res struct {
		Platform         string `json:"platform"`
		EventsSeen       int    `json:"events_seen"`
		MeetingsUpserted int    `json:"meetings_upserted"`
	}
	_ = json.NewDecoder(r.Body).Decode(&res)
	if res.EventsSeen != 3 || res.MeetingsUpserted != 2 {
		t.Fatalf("sync result=%+v, want seen=3 upserted=2", res)
	}

	// Two unassigned, externally-synced meetings now exist (deal_id NULL).
	var count int
	_ = conn.QueryRow("SELECT COUNT(*) FROM meetings WHERE org_id=? AND external_provider='google' AND deal_id IS NULL", orgA).Scan(&count)
	if count != 2 {
		t.Fatalf("meetings=%d, want 2", count)
	}
	// The Meet event mapped to source=meet w/ bot_enabled; the plain event to upload.
	var meetSrc, uploadSrc string
	_ = conn.QueryRow("SELECT source FROM meetings WHERE external_event_id='ev1'").Scan(&meetSrc)
	_ = conn.QueryRow("SELECT source FROM meetings WHERE external_event_id='ev2'").Scan(&uploadSrc)
	if meetSrc != "meet" || uploadSrc != "upload" {
		t.Fatalf("sources: ev1=%q ev2=%q", meetSrc, uploadSrc)
	}

	// Re-sync is idempotent (upsert, not duplicate).
	r2 := postInternal(t, ts, a, "/calendar/sync", map[string]any{"user_id": userID, "org_id": orgA, "platform": "google"}, token)
	if r2.StatusCode != 200 {
		t.Fatalf("re-sync: %d", r2.StatusCode)
	}
	var count2 int
	_ = conn.QueryRow("SELECT COUNT(*) FROM meetings WHERE org_id=? AND external_provider='google'", orgA).Scan(&count2)
	if count2 != 2 {
		t.Fatalf("after re-sync meetings=%d, want 2 (idempotent)", count2)
	}
}
