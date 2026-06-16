"""End-to-end QA journey across ALL store routers mounted in one app.

Unlike the per-router unit tests, this exercises the routers together as a
black box: a realistic multi-step user journey (orgs -> deal -> meeting ->
document -> bot session -> action item -> dashboard/calendar), followed by a
cross-tenant sweep proving a second tenant can neither see nor mutate the
first tenant's rows.

Reuses the conftest harness in this directory (``db``/``seed``/``make_client``).
Rows that have a create endpoint are created through the API; only rows with no
create endpoint (Analysis, and a document's extracted_text) are seeded directly
via ``get_session_factory``.
"""

from __future__ import annotations

from app.api.v1.store import (
    bot_sessions,
    dashboard,
    deals,
    documents,
    meetings,
    orgs,
    transcripts,
)
from app.db.engine import get_session_factory
from app.db.models import Analysis, Document

# deals mounts at "/deals"; every other router uses full absolute paths, so
# mount them at "".
ROUTES = [
    ("/deals", deals.router),
    ("", meetings.router),
    ("", documents.router),
    ("", transcripts.router),
    ("", bot_sessions.router),
    ("", orgs.router),
    ("", dashboard.router),
]


def _seed_analysis(org_id: str, meeting_id: str) -> str:
    """Insert an Analysis directly (no create endpoint exists for it)."""
    s = get_session_factory()()
    try:
        a = Analysis(
            org_id=org_id,
            meeting_id=meeting_id,
            call_type="management_presentation",
            status="completed",
            model_used="test-model",
            structured_output={"action_items": [{"key": "ai-1", "text": "Follow up"}]},
        )
        s.add(a)
        s.flush()
        analysis_id = a.id
        s.commit()
        return analysis_id
    finally:
        s.close()


def _set_extracted_text(document_id: str, text: str) -> None:
    """Set extracted_text on a document (create endpoint doesn't accept it)."""
    s = get_session_factory()()
    try:
        doc = s.get(Document, document_id)
        doc.extracted_text = text
        s.commit()
    finally:
        s.close()


def test_full_user_journey_and_cross_tenant_isolation(make_client, seed):
    client = make_client(ROUTES, seed.user_a)

    # --- 1. orgs -----------------------------------------------------------
    r = client.get("/orgs")
    assert r.status_code == 200, r.text
    org_ids = {o["id"] for o in r.json()}
    assert seed.org_a in org_ids
    assert seed.org_b not in org_ids

    # --- 2. create + read a deal ------------------------------------------
    r = client.post("/deals", json={"org_id": seed.org_a, "name": "Project Atlas"})
    assert r.status_code == 201, r.text
    deal = r.json()
    deal_id = deal["id"]
    assert deal["name"] == "Project Atlas"
    assert deal["created_by"] == seed.user_a

    listed = client.get("/deals").json()["items"]
    assert deal_id in {d["id"] for d in listed}

    r = client.get(f"/deals/{deal_id}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == deal_id

    # --- 3. create + update a meeting -------------------------------------
    r = client.post(
        f"/deals/{deal_id}/meetings",
        json={"title": "Kickoff", "source": "upload"},
    )
    assert r.status_code == 201, r.text
    meeting = r.json()
    meeting_id = meeting["id"]
    assert meeting["deal_id"] == deal_id
    assert meeting["org_id"] == seed.org_a

    mtgs = client.get(f"/deals/{deal_id}/meetings").json()
    assert meeting_id in {m["id"] for m in mtgs}

    r = client.patch(f"/meetings/{meeting_id}", json={"title": "Kickoff (revised)"})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Kickoff (revised)"

    r = client.get(f"/meetings/{meeting_id}")
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Kickoff (revised)"

    # --- 4. create + read a document --------------------------------------
    r = client.post(
        f"/deals/{deal_id}/documents",
        json={
            "title": "CIM",
            "document_type": "cim",
            "file_key": "orga/cim.pdf",
            "file_size": 1024,
        },
    )
    assert r.status_code == 201, r.text
    document = r.json()
    document_id = document["id"]
    assert document["deal_id"] == deal_id

    docs = client.get(f"/deals/{deal_id}/documents").json()
    assert document_id in {d["id"] for d in docs}

    # extracted_text has no create endpoint -> seed it, then read it back
    _set_extracted_text(document_id, "Confidential information memorandum text.")
    r = client.get(f"/documents/{document_id}")
    assert r.status_code == 200, r.text
    assert r.json()["extracted_text"] == "Confidential information memorandum text."

    # --- 5. bot session lifecycle -----------------------------------------
    r = client.post(
        "/bot-sessions",
        json={
            "deal_id": deal_id,
            "platform": "zoom",
            "meeting_url": "https://zoom.us/j/123",
        },
    )
    assert r.status_code == 201, r.text
    bot_session = r.json()
    bot_session_id = bot_session["id"]
    assert bot_session["status"] == "scheduled"

    sessions = client.get("/bot-sessions", params={"deal_id": deal_id}).json()
    assert bot_session_id in {b["id"] for b in sessions}

    r = client.post(f"/bot-sessions/{bot_session_id}/cancel")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"

    # --- 6. action items (analysis has no create endpoint -> seed) --------
    analysis_id = _seed_analysis(seed.org_a, meeting_id)
    r = client.post(
        f"/deals/{deal_id}/action-items",
        json={
            "analysis_id": analysis_id,
            "action_key": "ai-1",
            "action_text": "Follow up with management",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["action_key"] == "ai-1"

    items = client.get(f"/deals/{deal_id}/action-items").json()
    assert "ai-1" in {i["action_key"] for i in items}

    r = client.delete(f"/deals/{deal_id}/action-items/ai-1")
    assert r.status_code == 204, r.text
    items = client.get(f"/deals/{deal_id}/action-items").json()
    assert "ai-1" not in {i["action_key"] for i in items}

    # --- 7. dashboard activity includes the deal-creation audit entry -----
    activity = client.get("/dashboard/activity").json()
    create_entries = [
        a
        for a in activity
        if a["resource_type"] == "deal"
        and a["action"] == "create"
        and a["resource_id"] == deal_id
    ]
    assert create_entries, "deal-creation audit entry missing from activity feed"
    assert create_entries[0]["deal_name"] == "Project Atlas"

    # --- 8. calendar includes the meeting with its deal name --------------
    calendar = client.get("/calendar/meetings").json()
    entry = next((m for m in calendar if m["id"] == meeting_id), None)
    assert entry is not None, "created meeting missing from calendar feed"
    assert entry["deal"] is not None
    assert entry["deal"]["name"] == "Project Atlas"

    # ======================================================================
    # CROSS-TENANT SWEEP as user_b (org_b) — must not see or touch org_a rows
    # ======================================================================
    other = make_client(ROUTES, seed.user_b)

    # reads of user_a's rows -> 404
    assert other.get(f"/deals/{deal_id}").status_code == 404
    assert other.get(f"/meetings/{meeting_id}").status_code == 404
    assert other.get(f"/documents/{document_id}").status_code == 404

    # mutations of user_a's rows -> 404
    assert other.patch(f"/deals/{deal_id}", json={"name": "Hijacked"}).status_code == 404
    assert (
        other.patch(f"/meetings/{meeting_id}", json={"title": "Hijacked"}).status_code
        == 404
    )

    # creates under user_a's deal -> 404 (deal invisible to user_b)
    assert (
        other.post(
            f"/deals/{deal_id}/meetings", json={"title": "Sneaky"}
        ).status_code
        == 404
    )
    assert (
        other.post(
            f"/deals/{deal_id}/action-items",
            json={"analysis_id": analysis_id, "action_key": "x"},
        ).status_code
        == 404
    )

    # user_b's own listings never leak org_a rows
    b_deals = other.get("/deals").json()["items"]
    b_deal_ids = {d["id"] for d in b_deals}
    assert deal_id not in b_deal_ids
    assert seed.deal_a not in b_deal_ids

    b_activity = other.get("/dashboard/activity").json()
    for a in b_activity:
        assert a["deal_id"] != deal_id
        assert a["resource_id"] != deal_id
