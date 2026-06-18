package httpapi

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"strings"
	"testing"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
)

type fakeGraphRT struct{}

func (fakeGraphRT) RoundTrip(req *http.Request) (*http.Response, error) {
	body := `{}`
	far := time.Now().Add(60 * time.Hour).UTC().Format(time.RFC3339)
	switch {
	case strings.Contains(req.URL.Path, "/communications/callRecords/"):
		body = `{"organizer":{"user":{"displayName":"Carol"}},
		  "participants":[{"user":{"displayName":"Dave","id":"u1","userPrincipalName":"dave@x.com"}},
		                  {"user":{"displayName":"Erin","id":"u2"}}],
		  "sessions":[{"startDateTime":"2026-07-01T10:00:00Z"}]}`
	case strings.HasSuffix(req.URL.Path, "/subscriptions") && req.Method == "POST":
		body = `{"id":"sub-1","expirationDateTime":"` + far + `"}`
	case strings.Contains(req.URL.Path, "/subscriptions/") && req.Method == "PATCH":
		body = `{"id":"sub-1","expirationDateTime":"` + far + `"}`
	}
	return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader(body)),
		Header: http.Header{"Content-Type": []string{"application/json"}}}, nil
}

func seedMicrosoftCred(t *testing.T, srv *Server, org, user string) {
	t.Helper()
	fkey, _ := fernet.ParseKey(srv.Cfg.TokenEncryptionKey)
	if err := store.SaveCredentials(context.Background(), srv.DB, fkey, store.CredentialInput{
		OrgID: org, UserID: user, Platform: "microsoft", AccessToken: "ms-acc", ExpiresInSeconds: 3600,
	}); err != nil {
		t.Fatalf("seed cred: %v", err)
	}
}

func TestInternalTeamsIngest(t *testing.T) {
	ts, srv, conn := oauthTestServer(t)
	a, orgA := registerUser(t, ts, conn, "teams-ingest@x.com")
	var userID string
	_ = conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id=? LIMIT 1", orgA).Scan(&userID)
	seedMicrosoftCred(t, srv, orgA, userID)

	prev := graphHTTPClient
	graphHTTPClient = &http.Client{Transport: fakeGraphRT{}}
	t.Cleanup(func() { graphHTTPClient = prev })

	r := postInternal(t, ts, a, "/teams/ingest-call-record", map[string]any{"call_record_id": "cr-1"}, srv.Cfg.WorkerInternalToken)
	if r.StatusCode != 200 {
		t.Fatalf("teams ingest: %d", r.StatusCode)
	}
	var res struct {
		Organizer        string `json:"organizer"`
		ParticipantCount int    `json:"participant_count"`
		Handled          bool   `json:"handled"`
	}
	_ = json.NewDecoder(r.Body).Decode(&res)
	if !res.Handled || res.Organizer != "Carol" || res.ParticipantCount != 2 {
		t.Fatalf("teams ingest result=%+v", res)
	}
	// A teams meeting + 2 participants were persisted.
	var mid string
	if err := conn.QueryRow("SELECT id FROM meetings WHERE external_provider='microsoft' AND external_event_id='cr-1'").Scan(&mid); err != nil {
		t.Fatalf("meeting: %v", err)
	}
	var parts int
	_ = conn.QueryRow("SELECT COUNT(*) FROM meeting_participants WHERE meeting_id=?", mid).Scan(&parts)
	if parts != 2 {
		t.Fatalf("participants=%d, want 2", parts)
	}
}

func TestInternalEnsureSubscription(t *testing.T) {
	ts, srv, conn := oauthTestServer(t)
	a, orgA := registerUser(t, ts, conn, "ensure-sub@x.com")
	var userID string
	_ = conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id=? LIMIT 1", orgA).Scan(&userID)
	seedMicrosoftCred(t, srv, orgA, userID)

	prev := graphHTTPClient
	graphHTTPClient = &http.Client{Transport: fakeGraphRT{}}
	t.Cleanup(func() { graphHTTPClient = prev })

	// First call -> creates a subscription.
	r := postInternal(t, ts, a, "/microsoft/ensure-subscription", map[string]any{"user_id": userID, "org_id": orgA}, srv.Cfg.WorkerInternalToken)
	if r.StatusCode != 200 {
		t.Fatalf("ensure-sub: %d", r.StatusCode)
	}
	var res struct {
		SubscriptionID string `json:"subscription_id"`
		Action         string `json:"action"`
	}
	_ = json.NewDecoder(r.Body).Decode(&res)
	if res.Action != "created" || res.SubscriptionID != "sub-1" {
		t.Fatalf("ensure-sub create=%+v", res)
	}
	var subs int
	_ = conn.QueryRow("SELECT COUNT(*) FROM graph_subscriptions WHERE id='sub-1' AND is_active=1").Scan(&subs)
	if subs != 1 {
		t.Fatalf("subscriptions=%d, want 1", subs)
	}
	// Second call (far-future expiry already stored) -> noop.
	r2 := postInternal(t, ts, a, "/microsoft/ensure-subscription", map[string]any{"user_id": userID, "org_id": orgA}, srv.Cfg.WorkerInternalToken)
	var res2 struct {
		Action string `json:"action"`
	}
	_ = json.NewDecoder(r2.Body).Decode(&res2)
	if res2.Action != "noop" {
		t.Fatalf("ensure-sub re-run action=%q, want noop", res2.Action)
	}
}
