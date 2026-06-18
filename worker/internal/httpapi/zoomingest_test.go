package httpapi

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/crypto/fernet"
	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/store"
)

type fakeDownloadRT struct{}

func (fakeDownloadRT) RoundTrip(req *http.Request) (*http.Response, error) {
	return &http.Response{StatusCode: 200, Body: io.NopCloser(strings.NewReader("FAKE-MP4-BYTES")),
		Header: http.Header{"Content-Type": []string{"video/mp4"}}}, nil
}

func TestInternalZoomIngest(t *testing.T) {
	ts, srv, conn := oauthTestServer(t)
	a, orgA := registerUser(t, ts, conn, "zoom-ingest@x.com")
	var userID string
	if err := conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id=? LIMIT 1", orgA).Scan(&userID); err != nil {
		t.Fatalf("user: %v", err)
	}
	fkey, _ := fernet.ParseKey(srv.Cfg.TokenEncryptionKey)
	if err := store.SaveCredentials(context.Background(), conn, fkey, store.CredentialInput{
		OrgID: orgA, UserID: userID, Platform: "zoom", AccessToken: "zoom-acc", ExpiresInSeconds: 3600,
	}); err != nil {
		t.Fatalf("seed cred: %v", err)
	}

	prev := recordingHTTPClient
	recordingHTTPClient = &http.Client{Transport: fakeDownloadRT{}}
	t.Cleanup(func() { recordingHTTPClient = prev })

	r := postInternal(t, ts, a, "/zoom/ingest", map[string]any{
		"zoom_meeting_id": "zm-1", "download_url": "https://zoom.us/rec/download/abc", "topic": "Q3 Review",
	}, srv.Cfg.WorkerInternalToken)
	if r.StatusCode != 200 {
		t.Fatalf("ingest: %d", r.StatusCode)
	}
	var res struct {
		MeetingID string `json:"meeting_id"`
		Status    string `json:"status"`
	}
	_ = json.NewDecoder(r.Body).Decode(&res)
	if res.Status != "uploaded" || res.MeetingID == "" {
		t.Fatalf("ingest result=%+v", res)
	}

	// An unassigned zoom meeting was created + flipped to uploaded with a file_key.
	var provider, status, fileKey string
	if err := conn.QueryRow("SELECT external_provider, status, file_key FROM meetings WHERE id=?", res.MeetingID).
		Scan(&provider, &status, &fileKey); err != nil {
		t.Fatalf("meeting row: %v", err)
	}
	if provider != "zoom" || status != "uploaded" || fileKey != "zoom/"+res.MeetingID+".mp4" {
		t.Fatalf("meeting: provider=%q status=%q file_key=%q", provider, status, fileKey)
	}
	// The recording bytes landed in storage.
	path, _ := filepath.Abs(filepath.Join(srv.Cfg.StorageRoot, "meeting-recordings", fileKey))
	if b, err := os.ReadFile(path); err != nil || string(b) != "FAKE-MP4-BYTES" {
		t.Fatalf("stored file: err=%v bytes=%q", err, b)
	}

	// Re-ingest the same zoom_meeting_id attributes to the SAME meeting (no dup).
	r2 := postInternal(t, ts, a, "/zoom/ingest", map[string]any{
		"zoom_meeting_id": "zm-1", "download_url": "https://zoom.us/rec/download/abc",
	}, srv.Cfg.WorkerInternalToken)
	var res2 struct {
		MeetingID string `json:"meeting_id"`
	}
	_ = json.NewDecoder(r2.Body).Decode(&res2)
	if res2.MeetingID != res.MeetingID {
		t.Fatalf("re-ingest created a new meeting: %s vs %s", res2.MeetingID, res.MeetingID)
	}
}
