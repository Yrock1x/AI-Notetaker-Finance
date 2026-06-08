"""Tests for the Dashboard store router — activity feed, extractions, action items.

Covers cross-tenant isolation on every endpoint plus the action-item toggle
(POST creates, GET shows, POST again updates not duplicates, DELETE removes).
"""

from __future__ import annotations

from app.api.v1.store import dashboard
from app.db.engine import get_session_factory
from app.db.models import Analysis, AuditLog, Meeting

ROUTES = [("", dashboard.router)]


def _make_meeting(session, org_id, deal_id, user_id, title="Mtg"):
    m = Meeting(org_id=org_id, deal_id=deal_id, title=title, created_by=user_id)
    session.add(m)
    session.flush()
    return m.id


def _make_analysis(session, org_id, meeting_id, status="completed", call_type="diligence"):
    a = Analysis(
        org_id=org_id,
        meeting_id=meeting_id,
        call_type=call_type,
        structured_output={"action_items": ["do x"]},
        model_used="test-model",
        status=status,
    )
    session.add(a)
    session.flush()
    return a.id


# ---- activity feed --------------------------------------------------------
def test_activity_is_org_scoped(make_client, seed):
    session = get_session_factory()()
    try:
        session.add(
            AuditLog(
                org_id=seed.org_a,
                user_id=seed.user_a,
                deal_id=seed.deal_a,
                action="create",
                resource_type="deal",
                resource_id=seed.deal_a,
                details={"k": "v"},
            )
        )
        session.add(
            AuditLog(
                org_id=seed.org_b,
                user_id=seed.user_b,
                deal_id=seed.deal_b,
                action="create",
                resource_type="deal",
                resource_id=seed.deal_b,
            )
        )
        session.commit()
    finally:
        session.close()

    client = make_client(ROUTES, seed.user_a)
    resp = client.get("/dashboard/activity")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    # only org A's row is visible
    assert all(r["resource_id"] != seed.deal_b for r in rows)
    own = [r for r in rows if r["resource_id"] == seed.deal_a]
    assert len(own) == 1
    row = own[0]
    assert row["deal_name"] == "orga deal"
    assert row["actor_name"] == "ORGA"
    assert row["details"] == {"k": "v"}


# ---- extractions ----------------------------------------------------------
def test_extractions_only_completed_for_deal(make_client, seed):
    session = get_session_factory()()
    try:
        meeting_id = _make_meeting(session, seed.org_a, seed.deal_a, seed.user_a)
        done_id = _make_analysis(session, seed.org_a, meeting_id, status="completed")
        # a non-completed analysis on the same deal must be excluded
        _make_analysis(session, seed.org_a, meeting_id, status="running")
        session.commit()
    finally:
        session.close()

    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/deals/{seed.deal_a}/extractions")
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    ids = [r["id"] for r in rows]
    assert done_id in ids
    assert all(r["call_type"] == "diligence" for r in rows)
    # only the completed one
    assert len(rows) == 1
    assert rows[0]["structured_output"] == {"action_items": ["do x"]}


def test_extractions_cross_tenant_404(make_client, seed):
    client = make_client(ROUTES, seed.user_b)
    assert client.get(f"/deals/{seed.deal_a}/extractions").status_code == 404


# ---- action items ---------------------------------------------------------
def test_action_item_toggle(make_client, seed):
    session = get_session_factory()()
    try:
        meeting_id = _make_meeting(session, seed.org_a, seed.deal_a, seed.user_a)
        analysis_id = _make_analysis(session, seed.org_a, meeting_id)
        session.commit()
    finally:
        session.close()

    client = make_client(ROUTES, seed.user_a)

    # POST creates
    r = client.post(
        f"/deals/{seed.deal_a}/action-items",
        json={"analysis_id": analysis_id, "action_key": "k1", "action_text": "Do the thing"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["action_key"] == "k1"
    assert body["action_text"] == "Do the thing"
    assert body["completed_by"] == seed.user_a

    # GET shows it
    rows = client.get(f"/deals/{seed.deal_a}/action-items").json()
    assert len(rows) == 1
    assert rows[0]["action_key"] == "k1"

    # POST again with same action_key updates, no duplicate
    r2 = client.post(
        f"/deals/{seed.deal_a}/action-items",
        json={"analysis_id": analysis_id, "action_key": "k1", "action_text": "Updated"},
    )
    assert r2.status_code == 201, r2.text
    rows = client.get(f"/deals/{seed.deal_a}/action-items").json()
    assert len(rows) == 1
    assert rows[0]["action_text"] == "Updated"

    # DELETE removes it
    assert client.delete(f"/deals/{seed.deal_a}/action-items/k1").status_code == 204
    rows = client.get(f"/deals/{seed.deal_a}/action-items").json()
    assert rows == []


def test_action_items_cross_tenant_404(make_client, seed):
    client = make_client(ROUTES, seed.user_b)
    assert client.get(f"/deals/{seed.deal_a}/action-items").status_code == 404
    assert (
        client.post(
            f"/deals/{seed.deal_a}/action-items",
            json={"analysis_id": "x", "action_key": "k1"},
        ).status_code
        == 404
    )
    assert client.delete(f"/deals/{seed.deal_a}/action-items/k1").status_code == 404
