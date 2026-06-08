"""Regression tests for the write-side IDOR fixes from the security review."""

from __future__ import annotations

from app.api.v1.store import dashboard, deals, meetings
from app.db.base import gen_uuid
from app.db.engine import get_session_factory
from app.db.models import Analysis, Meeting

ROUTES = [("/deals", deals.router), ("", meetings.router), ("", dashboard.router)]


def _add(*objs):
    s = get_session_factory()()
    try:
        s.add_all(objs)
        s.commit()
        return [o.id for o in objs]
    finally:
        s.close()


def test_create_meeting_scoped(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    # own deal → 201
    ok = client.post(f"/deals/{seed.deal_a}/meetings", json={"title": "Kickoff"})
    assert ok.status_code == 201, ok.text
    assert ok.json()["deal_id"] == seed.deal_a
    # foreign deal → 404
    bad = client.post(f"/deals/{seed.deal_b}/meetings", json={"title": "Sneak"})
    assert bad.status_code == 404


def test_update_meeting_rejects_cross_org_deal(make_client, seed):
    (mtg_id,) = _add(
        Meeting(org_id=seed.org_a, deal_id=seed.deal_a, title="M", created_by=seed.user_a)
    )
    client = make_client(ROUTES, seed.user_a)
    # reassigning to a deal in another org must be rejected (IDOR)
    resp = client.patch(f"/meetings/{mtg_id}", json={"deal_id": seed.deal_b})
    assert resp.status_code in (400, 404)
    # the meeting still belongs to its original deal
    assert client.get(f"/meetings/{mtg_id}").json()["deal_id"] == seed.deal_a


def test_action_item_rejects_foreign_analysis(make_client, seed):
    # an analysis that lives in org B
    (mtg_b,) = _add(
        Meeting(org_id=seed.org_b, deal_id=seed.deal_b, title="MB", created_by=seed.user_b)
    )
    (analysis_b,) = _add(
        Analysis(org_id=seed.org_b, meeting_id=mtg_b, call_type="diligence", model_used="x")
    )
    client = make_client(ROUTES, seed.user_a)
    # attaching org B's analysis to an org A deal's action item must 404
    resp = client.post(
        f"/deals/{seed.deal_a}/action-items",
        json={"analysis_id": analysis_b, "action_key": "act-1", "action_text": "do"},
    )
    assert resp.status_code == 404


def test_action_item_accepts_same_org_analysis(make_client, seed):
    (mtg_a,) = _add(
        Meeting(org_id=seed.org_a, deal_id=seed.deal_a, title="MA", created_by=seed.user_a)
    )
    (analysis_a,) = _add(
        Analysis(org_id=seed.org_a, meeting_id=mtg_a, call_type="diligence", model_used="x")
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.post(
        f"/deals/{seed.deal_a}/action-items",
        json={"analysis_id": analysis_a, "action_key": "act-1", "action_text": "do"},
    )
    assert resp.status_code == 201, resp.text
