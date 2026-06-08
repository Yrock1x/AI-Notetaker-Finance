"""Tests for the bot sessions store router — create, list/filter, cancel, scoping."""

from __future__ import annotations

from app.api.v1.store import bot_sessions

ROUTES = [("", bot_sessions.router)]


def test_create_under_own_deal(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.post(
        "/bot-sessions",
        json={
            "deal_id": seed.deal_a,
            "platform": "zoom",
            "meeting_url": "https://zoom.us/j/123",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["org_id"] == seed.org_a
    assert body["deal_id"] == seed.deal_a
    assert body["status"] == "scheduled"
    assert body["created_by"] == seed.user_a


def test_list_is_org_scoped_and_filterable(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    client.post(
        "/bot-sessions",
        json={"deal_id": seed.deal_a, "platform": "zoom", "meeting_url": "https://z/1"},
    )
    # bot session for org B (created by user_b)
    client_b = make_client(ROUTES, seed.user_b)
    client_b.post(
        "/bot-sessions",
        json={"deal_id": seed.deal_b, "platform": "teams", "meeting_url": "https://t/1"},
    )

    items = client.get("/bot-sessions").json()
    assert all(s["org_id"] == seed.org_a for s in items)
    assert len(items) == 1

    by_deal = client.get("/bot-sessions", params={"deal_id": seed.deal_a}).json()
    assert all(s["deal_id"] == seed.deal_a for s in by_deal)

    scheduled = client.get("/bot-sessions", params={"status": "scheduled"}).json()
    assert all(s["status"] == "scheduled" for s in scheduled)
    none = client.get("/bot-sessions", params={"status": "completed"}).json()
    assert none == []


def test_cancel(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    created = client.post(
        "/bot-sessions",
        json={"deal_id": seed.deal_a, "platform": "zoom", "meeting_url": "https://z/1"},
    ).json()
    resp = client.post(f"/bot-sessions/{created['id']}/cancel")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "cancelled"


def test_cross_tenant_create_denied(make_client, seed):
    client_b = make_client(ROUTES, seed.user_b)
    resp = client_b.post(
        "/bot-sessions",
        json={"deal_id": seed.deal_a, "platform": "zoom", "meeting_url": "https://z/1"},
    )
    assert resp.status_code == 404


def test_cross_tenant_list_and_cancel_invisible(make_client, seed):
    # user_a creates a session under org A
    client_a = make_client(ROUTES, seed.user_a)
    created = client_a.post(
        "/bot-sessions",
        json={"deal_id": seed.deal_a, "platform": "zoom", "meeting_url": "https://z/1"},
    ).json()

    # user_b must not see it nor cancel it
    client_b = make_client(ROUTES, seed.user_b)
    assert client_b.get("/bot-sessions").json() == []
    assert client_b.post(f"/bot-sessions/{created['id']}/cancel").status_code == 404
