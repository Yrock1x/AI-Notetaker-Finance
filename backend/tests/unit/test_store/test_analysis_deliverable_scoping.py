"""Regression: analysis + deliverable endpoints must enforce org scoping.

These two routers dropped scoping during the Supabase→SQLite migration (caught
by review). A user from another org must get 404, not another tenant's data.
"""

from __future__ import annotations

from app.api.v1 import analysis, deliverables
from app.db.engine import get_session_factory
from app.db.models import Analysis, Meeting

# analysis router is mounted under /meetings/{meeting_id}/analyses;
# deliverables under /deals/{deal_id}/deliverables.
ANALYSIS_ROUTES = [("/meetings/{meeting_id}/analyses", analysis.router)]
DELIVERABLE_ROUTES = [("/deals/{deal_id}/deliverables", deliverables.router)]


def _seed_meeting_with_analysis(org_id, deal_id, user_id):
    s = get_session_factory()()
    try:
        mtg = Meeting(org_id=org_id, deal_id=deal_id, title="M", created_by=user_id)
        s.add(mtg)
        s.flush()
        an = Analysis(
            org_id=org_id, meeting_id=mtg.id, call_type="diligence",
            model_used="x", status="completed", structured_output={"ok": True},
        )
        s.add(an)
        s.commit()
        return mtg.id, an.id
    finally:
        s.close()


def test_analysis_list_cross_tenant_404(make_client, seed):
    mtg_id, _ = _seed_meeting_with_analysis(seed.org_a, seed.deal_a, seed.user_a)
    # owner sees it
    owner = make_client(ANALYSIS_ROUTES, seed.user_a)
    assert owner.get(f"/meetings/{mtg_id}/analyses").status_code == 200
    # outsider (org B) gets 404
    outsider = make_client(ANALYSIS_ROUTES, seed.user_b)
    assert outsider.get(f"/meetings/{mtg_id}/analyses").status_code == 404
    assert outsider.get(f"/meetings/{mtg_id}/analyses/latest").status_code == 404


def test_analysis_get_cross_tenant_404(make_client, seed):
    mtg_id, an_id = _seed_meeting_with_analysis(seed.org_a, seed.deal_a, seed.user_a)
    outsider = make_client(ANALYSIS_ROUTES, seed.user_b)
    assert outsider.get(f"/meetings/{mtg_id}/analyses/{an_id}").status_code == 404


def test_deliverable_generate_cross_tenant_404(make_client, seed):
    # user_b must not generate a deliverable for org A's deal
    outsider = make_client(DELIVERABLE_ROUTES, seed.user_b)
    resp = outsider.post(
        f"/deals/{seed.deal_a}/deliverables/generate", json={"type": "investment_memo"}
    )
    assert resp.status_code == 404


def test_deliverable_chat_cross_tenant_404(make_client, seed):
    outsider = make_client(DELIVERABLE_ROUTES, seed.user_b)
    resp = outsider.post(
        f"/deals/{seed.deal_a}/deliverables/chat", json={"message": "hi"}
    )
    assert resp.status_code == 404
