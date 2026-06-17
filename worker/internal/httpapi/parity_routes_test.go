package httpapi

import (
	"encoding/json"
	"net/http"
	"testing"
)

// TestCalendarAndUpcomingUnassigned covers the two meeting-list endpoints the
// frontend calendar page + dashboard widget call, which were missing from the
// first Go cut (404 parity gap). calendar/meetings returns every org meeting with
// its deal ref; upcoming-unassigned returns only externally-synced, deal-less
// meetings.
func TestCalendarAndUpcomingUnassigned(t *testing.T) {
	ts, _, conn := testServer(t)
	a, orgA := registerUser(t, ts, conn, "cal-a@x.com")
	b, _ := registerUser(t, ts, conn, "cal-b@x.com")

	// A creates a deal + an assigned meeting under it.
	resp := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "Calendar Co"})
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)
	mr := postJSON(t, a, ts.URL+"/api/v1/deals/"+d.ID+"/meetings",
		map[string]any{"title": "Kickoff", "source": "upload"})
	if mr.StatusCode != 201 {
		t.Fatalf("create meeting: %d", mr.StatusCode)
	}

	// An unassigned, externally-synced meeting (deal_id NULL, external_provider set)
	// — inserted directly since the create endpoint always attaches a deal.
	// created_by must reference a real profile, so reuse the registered user.
	var uidA string
	if err := conn.QueryRow("SELECT user_id FROM org_memberships WHERE org_id = ? LIMIT 1", orgA).Scan(&uidA); err != nil {
		t.Fatalf("lookup user: %v", err)
	}
	if _, err := conn.Exec(
		`INSERT INTO meetings(id, org_id, deal_id, title, source, status, bot_enabled,
		    external_provider, created_by, created_at, updated_at)
		 VALUES ('m-unassigned', ?, NULL, 'Synced Sync', 'google_meet', 'scheduled', 1,
		    'google', ?, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')`, orgA, uidA); err != nil {
		t.Fatalf("seed unassigned meeting: %v", err)
	}

	// calendar/meetings: A sees both meetings; the assigned one carries its deal ref.
	cr, _ := a.Get(ts.URL + "/api/v1/calendar/meetings")
	if cr.StatusCode != 200 {
		t.Fatalf("calendar/meetings: %d", cr.StatusCode)
	}
	var cal []calendarMeetingJSON
	_ = json.NewDecoder(cr.Body).Decode(&cal)
	if len(cal) != 2 {
		t.Fatalf("calendar: got %d meetings, want 2", len(cal))
	}
	var sawDealRef bool
	for i := range cal {
		if cal[i].Deal != nil && cal[i].Deal.ID == d.ID && cal[i].Deal.Name == "Calendar Co" {
			sawDealRef = true
		}
	}
	if !sawDealRef {
		t.Fatalf("calendar: assigned meeting missing its deal ref: %+v", cal)
	}

	// upcoming-unassigned: only the externally-synced deal-less meeting.
	ur, _ := a.Get(ts.URL + "/api/v1/dashboard/upcoming-unassigned")
	if ur.StatusCode != 200 {
		t.Fatalf("upcoming-unassigned: %d", ur.StatusCode)
	}
	var up []meetingJSON
	_ = json.NewDecoder(ur.Body).Decode(&up)
	if len(up) != 1 || up[0].ID != "m-unassigned" {
		t.Fatalf("upcoming-unassigned: got %+v, want only m-unassigned", up)
	}

	// Tenant isolation: B sees neither.
	br, _ := b.Get(ts.URL + "/api/v1/calendar/meetings")
	var calB []calendarMeetingJSON
	_ = json.NewDecoder(br.Body).Decode(&calB)
	if len(calB) != 0 {
		t.Fatalf("B sees %d calendar meetings, want 0", len(calB))
	}
}

// TestActionItemDelete covers DELETE /deals/{id}/action-items/{key} — the
// uncheck path the frontend uses, missing from the first Go cut. Delete is a 204
// no-op whether or not the row existed (matching the Python handler).
func TestActionItemDelete(t *testing.T) {
	ts, _, conn := testServer(t)
	a, orgA := registerUser(t, ts, conn, "ai-a@x.com")

	resp := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "AI Co"})
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)

	// A meeting under the deal (analyses.meeting_id is NOT NULL), then an analysis
	// in the same org to satisfy the upsert's same-org analysis check.
	mr := postJSON(t, a, ts.URL+"/api/v1/deals/"+d.ID+"/meetings",
		map[string]any{"title": "Call", "source": "upload"})
	var m meetingJSON
	_ = json.NewDecoder(mr.Body).Decode(&m)
	if _, err := conn.Exec(
		`INSERT INTO analyses(id, org_id, meeting_id, call_type, model_used, prompt_version, status, version, created_at, updated_at)
		 VALUES ('an-1', ?, ?, 'summary', 'test-model', 'v1', 'completed', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')`,
		orgA, m.ID); err != nil {
		t.Fatalf("seed analysis: %v", err)
	}

	// Complete an action item, then delete it.
	cr := postJSON(t, a, ts.URL+"/api/v1/deals/"+d.ID+"/action-items",
		map[string]any{"analysis_id": "an-1", "action_key": "k1", "action_text": "do the thing"})
	if cr.StatusCode != 201 {
		t.Fatalf("upsert action item: %d", cr.StatusCode)
	}

	del, _ := http.NewRequest("DELETE", ts.URL+"/api/v1/deals/"+d.ID+"/action-items/k1", nil)
	dr, _ := a.Do(del)
	if dr.StatusCode != 204 {
		t.Fatalf("delete action item: %d, want 204", dr.StatusCode)
	}

	// Gone from the list.
	lr, _ := a.Get(ts.URL + "/api/v1/deals/" + d.ID + "/action-items")
	var items []actionItemJSON
	_ = json.NewDecoder(lr.Body).Decode(&items)
	if len(items) != 0 {
		t.Fatalf("after delete: %d items, want 0", len(items))
	}

	// Deleting a non-existent key is still a 204 no-op.
	del2, _ := http.NewRequest("DELETE", ts.URL+"/api/v1/deals/"+d.ID+"/action-items/missing", nil)
	if dr2, _ := a.Do(del2); dr2.StatusCode != 204 {
		t.Fatalf("delete missing: %d, want 204", dr2.StatusCode)
	}
}

// TestQAHistoryRouteRegistered guards the route path the frontend calls
// (/deals/{id}/qa/history). It was originally registered at /qa and 404'd the
// frontend history fetch. An empty deal has an empty history (200, []), which is
// enough to prove the route is mounted.
func TestQAHistoryRouteRegistered(t *testing.T) {
	ts, _, conn := testServer(t)
	a, orgA := registerUser(t, ts, conn, "qa-a@x.com")
	resp := postJSON(t, a, ts.URL+"/api/v1/deals", map[string]any{"org_id": orgA, "name": "QA Co"})
	var d dealJSON
	_ = json.NewDecoder(resp.Body).Decode(&d)

	hr, _ := a.Get(ts.URL + "/api/v1/deals/" + d.ID + "/qa/history")
	if hr.StatusCode != 200 {
		t.Fatalf("qa/history: %d, want 200 (route must be mounted at /qa/history)", hr.StatusCode)
	}
}
