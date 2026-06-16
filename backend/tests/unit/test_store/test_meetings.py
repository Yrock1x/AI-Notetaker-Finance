"""Tests for the Meetings store router — listing, scoping, patch, calendar."""

from __future__ import annotations

from app.api.v1.store import meetings
from app.db.engine import get_session_factory
from app.db.models import Meeting

ROUTES = [("", meetings.router)]


def _make_meeting(seed_attr, **kwargs) -> str:
    """Insert a Meeting row directly and return its id."""
    session = get_session_factory()()
    try:
        m = Meeting(**kwargs)
        session.add(m)
        session.flush()
        mid = m.id
        session.commit()
        return mid
    finally:
        session.close()


def test_list_deal_meetings_is_scoped(make_client, seed):
    m_a = _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=seed.deal_a,
        title="A meeting",
        created_by=seed.user_a,
    )
    # a meeting in deal_b should not leak into deal_a's listing
    _make_meeting(
        seed,
        org_id=seed.org_b,
        deal_id=seed.deal_b,
        title="B meeting",
        created_by=seed.user_b,
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/deals/{seed.deal_a}/meetings")
    assert resp.status_code == 200, resp.text
    ids = [m["id"] for m in resp.json()]
    assert ids == [m_a]


def test_list_other_tenant_deal_404s(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    assert client.get(f"/deals/{seed.deal_b}/meetings").status_code == 404


def test_get_meeting(make_client, seed):
    mid = _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=seed.deal_a,
        title="Hi",
        created_by=seed.user_a,
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/meetings/{mid}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["title"] == "Hi"


def test_get_other_tenant_meeting_404s(make_client, seed):
    mid = _make_meeting(
        seed,
        org_id=seed.org_b,
        deal_id=seed.deal_b,
        title="Secret",
        created_by=seed.user_b,
    )
    client = make_client(ROUTES, seed.user_a)
    assert client.get(f"/meetings/{mid}").status_code == 404


def test_patch_meeting(make_client, seed):
    mid = _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=seed.deal_a,
        title="Old",
        bot_enabled=True,
        created_by=seed.user_a,
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.patch(
        f"/meetings/{mid}", json={"title": "New", "bot_enabled": False}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["title"] == "New"
    assert body["bot_enabled"] is False


def test_patch_other_tenant_meeting_404s(make_client, seed):
    mid = _make_meeting(
        seed,
        org_id=seed.org_b,
        deal_id=seed.deal_b,
        title="Old",
        created_by=seed.user_b,
    )
    client = make_client(ROUTES, seed.user_a)
    assert client.patch(f"/meetings/{mid}", json={"title": "Hax"}).status_code == 404


def test_calendar_returns_deal_name(make_client, seed):
    linked = _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=seed.deal_a,
        title="Linked",
        meeting_date="2026-06-01T10:00:00Z",
        created_by=seed.user_a,
    )
    unlinked = _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=None,
        title="Unlinked",
        meeting_date="2026-06-02T10:00:00Z",
        created_by=seed.user_a,
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.get("/calendar/meetings")
    assert resp.status_code == 200, resp.text
    by_id = {m["id"]: m for m in resp.json()}
    assert by_id[linked]["deal"]["id"] == seed.deal_a
    assert by_id[linked]["deal"]["name"] == "orga deal"
    assert by_id[unlinked]["deal"] is None


def test_calendar_is_cross_tenant_isolated(make_client, seed):
    _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=seed.deal_a,
        title="A",
        created_by=seed.user_a,
    )
    _make_meeting(
        seed,
        org_id=seed.org_b,
        deal_id=seed.deal_b,
        title="B",
        created_by=seed.user_b,
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.get("/calendar/meetings")
    assert resp.status_code == 200, resp.text
    orgs = {m["org_id"] for m in resp.json()}
    assert orgs == {seed.org_a}


def test_upcoming_unassigned_filters(make_client, seed):
    # qualifies: no deal + has external_provider
    good = _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=None,
        title="From calendar",
        external_provider="google",
        external_event_id="evt1",
        created_by=seed.user_a,
    )
    # excluded: assigned to a deal
    _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=seed.deal_a,
        title="Assigned",
        external_provider="google",
        created_by=seed.user_a,
    )
    # excluded: no external_provider
    _make_meeting(
        seed,
        org_id=seed.org_a,
        deal_id=None,
        title="Manual upload",
        external_provider=None,
        created_by=seed.user_a,
    )
    # excluded: other tenant
    _make_meeting(
        seed,
        org_id=seed.org_b,
        deal_id=None,
        title="Other tenant",
        external_provider="google",
        external_event_id="evtb",
        created_by=seed.user_b,
    )
    client = make_client(ROUTES, seed.user_a)
    resp = client.get("/dashboard/upcoming-unassigned")
    assert resp.status_code == 200, resp.text
    ids = [m["id"] for m in resp.json()]
    assert ids == [good]
