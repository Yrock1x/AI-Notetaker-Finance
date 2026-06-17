package httpapi

import (
	"bytes"
	"encoding/json"
	"io"
	"net/http"
	"testing"
	"time"

	"github.com/Yrock1x/AI-Notetaker-Finance/worker/internal/storage"
)

const testStorageKey = "storage-test-key-0123456789abcdef"

func TestSignedUploadDownloadRoundTrip(t *testing.T) {
	ts, _, conn := testServer(t)
	a, orgA := registerUser(t, ts, conn, "f@x.com")

	// create a deal to scope the upload to
	dr := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "D"})
	var d dealJSON
	_ = json.NewDecoder(dr.Body).Decode(&d)

	// upload ticket
	tr := postJSON(t, a, ts.URL+"/api/v1/storage/upload-ticket",
		map[string]any{"bucket": "deal-documents", "deal_id": d.ID, "filename": "report.txt"})
	if tr.StatusCode != 200 {
		t.Fatalf("upload-ticket: %d", tr.StatusCode)
	}
	var ticket struct {
		Bucket    string `json:"bucket"`
		Key       string `json:"key"`
		UploadURL string `json:"upload_url"`
		Method    string `json:"method"`
	}
	_ = json.NewDecoder(tr.Body).Decode(&ticket)
	if ticket.Method != "PUT" || ticket.Key == "" || ticket.UploadURL == "" {
		t.Fatalf("ticket=%+v", ticket)
	}

	content := []byte("hello signed storage")

	// PUT to the signed upload URL (no session cookie needed)
	req, _ := http.NewRequest("PUT", ts.URL+ticket.UploadURL, bytes.NewReader(content))
	pr, err := http.DefaultClient.Do(req)
	if err != nil || pr.StatusCode != 200 {
		t.Fatalf("PUT signed: %v status=%d", err, pr.StatusCode)
	}

	// tampered signature -> 403
	bad := ts.URL + ticket.UploadURL + "tampered"
	breq, _ := http.NewRequest("PUT", bad, bytes.NewReader(content))
	if br, _ := http.DefaultClient.Do(breq); br.StatusCode != 403 {
		t.Fatalf("tampered PUT status=%d, want 403", br.StatusCode)
	}

	// GET via a freshly-signed download URL (same signing key the server uses)
	getURL := storage.MakeSignedURL(testStorageKey, ticket.Bucket, ticket.Key, "GET", time.Hour)
	gr, err := http.Get(ts.URL + getURL)
	if err != nil || gr.StatusCode != 200 {
		t.Fatalf("GET signed: %v status=%d", err, gr.StatusCode)
	}
	got, _ := io.ReadAll(gr.Body)
	if !bytes.Equal(got, content) {
		t.Fatalf("downloaded %q, want %q", got, content)
	}

	// unsigned GET -> 403
	if ur, _ := http.Get(ts.URL + "/api/v1/storage/deal-documents/" + ticket.Key); ur.StatusCode != 403 {
		t.Fatalf("unsigned GET status=%d, want 403", ur.StatusCode)
	}
}
