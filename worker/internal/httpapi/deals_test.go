package httpapi

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/cookiejar"
	"net/http/httptest"
	"testing"
)

func jsonBody(v any) *bytes.Reader {
	b, _ := json.Marshal(v)
	return bytes.NewReader(b)
}

// registerUser registers a fresh user on its own client and returns the client
// (cookie set) plus the user's auto-provisioned org id.
func registerUser(t *testing.T, ts *httptest.Server, conn *sql.DB, email string) (*http.Client, string) {
	t.Helper()
	jar, _ := cookiejar.New(nil)
	c := &http.Client{Jar: jar}
	resp := postJSON(t, c, ts.URL+"/api/v1/auth/register",
		map[string]any{"email": email, "password": "Sup3rSecret!", "full_name": email})
	if resp.StatusCode != 200 {
		t.Fatalf("register %s: %d", email, resp.StatusCode)
	}
	var sr sessionResponse
	_ = json.NewDecoder(resp.Body).Decode(&sr)
	var orgID string
	if err := conn.QueryRow("SELECT org_id FROM org_memberships WHERE user_id = ?", sr.ID).Scan(&orgID); err != nil {
		t.Fatalf("lookup org: %v", err)
	}
	return c, orgID
}

func TestDealsCRUDAndIsolation(t *testing.T) {
	ts, _, conn := testServer(t)
	a, orgA := registerUser(t, ts, conn, "a@x.com")
	b, _ := registerUser(t, ts, conn, "b@x.com")

	// A creates a deal
	resp := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "Helios"})
	if resp.StatusCode != 201 {
		t.Fatalf("create deal: %d", resp.StatusCode)
	}
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)
	if d.ID == "" || d.Name != "Helios" || d.Status != "active" || d.CreatedBy == "" {
		t.Fatalf("deal=%+v", d)
	}

	// A lists -> sees it
	lr, _ := a.Get(ts.URL + "/api/v1/deals")
	var page struct {
		Items   []dealJSON `json:"items"`
		HasMore bool       `json:"has_more"`
	}
	_ = json.NewDecoder(lr.Body).Decode(&page)
	if len(page.Items) != 1 || page.Items[0].ID != d.ID {
		t.Fatalf("list=%+v", page)
	}

	// A gets + patches
	if r, _ := a.Get(ts.URL + "/api/v1/deals/" + d.ID); r.StatusCode != 200 {
		t.Fatalf("get deal: %d", r.StatusCode)
	}
	preq, _ := http.NewRequest("PATCH", ts.URL+"/api/v1/deals/"+d.ID,
		jsonBody(map[string]any{"status": "won"}))
	preq.Header.Set("Content-Type", "application/json")
	pr, _ := a.Do(preq)
	var pd dealJSON
	_ = json.NewDecoder(pr.Body).Decode(&pd)
	if pr.StatusCode != 200 || pd.Status != "won" {
		t.Fatalf("patch: %d status=%s", pr.StatusCode, pd.Status)
	}

	// B cannot create in A's org (403) nor read A's deal (404)
	if r := postJSON(t, b, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "sneaky"}); r.StatusCode != 403 {
		t.Fatalf("B create in A org: %d, want 403", r.StatusCode)
	}
	if r, _ := b.Get(ts.URL + "/api/v1/deals/" + d.ID); r.StatusCode != 404 {
		t.Fatalf("B read A deal: %d, want 404", r.StatusCode)
	}
	// B's deal list is empty (tenant isolation)
	lrb, _ := b.Get(ts.URL + "/api/v1/deals")
	var pageB struct {
		Items []dealJSON `json:"items"`
	}
	_ = json.NewDecoder(lrb.Body).Decode(&pageB)
	if len(pageB.Items) != 0 {
		t.Fatalf("B sees %d deals, want 0", len(pageB.Items))
	}

	// A soft-deletes -> gone
	dreq, _ := http.NewRequest("DELETE", ts.URL+"/api/v1/deals/"+d.ID, nil)
	if dr, _ := a.Do(dreq); dr.StatusCode != 204 {
		t.Fatalf("delete: %d, want 204", dr.StatusCode)
	}
	if r, _ := a.Get(ts.URL + "/api/v1/deals/" + d.ID); r.StatusCode != 404 {
		t.Fatalf("get after delete: %d, want 404", r.StatusCode)
	}
}
