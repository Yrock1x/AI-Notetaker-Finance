"""Tests for the Deals store router — CRUD, scoping, soft-delete, members."""

from __future__ import annotations

from app.api.v1.store import deals

ROUTES = [("/deals", deals.router)]


def test_list_is_org_scoped(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.get("/deals")
    assert resp.status_code == 200
    ids = [d["id"] for d in resp.json()["items"]]
    assert seed.deal_a in ids
    assert seed.deal_b not in ids  # other tenant invisible


def test_get_other_tenant_deal_404s(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    assert client.get(f"/deals/{seed.deal_b}").status_code == 404


def test_create_in_own_org(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.post("/deals", json={"org_id": seed.org_a, "name": "New Deal"})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "New Deal"
    assert body["created_by"] == seed.user_a


def test_create_in_foreign_org_denied(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.post("/deals", json={"org_id": seed.org_b, "name": "Sneaky"})
    assert resp.status_code == 403


def test_update_and_soft_delete(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    assert client.patch(f"/deals/{seed.deal_a}", json={"status": "won"}).json()["status"] == "won"

    assert client.delete(f"/deals/{seed.deal_a}").status_code == 204
    # soft-deleted → no longer listed or fetchable
    assert seed.deal_a not in [d["id"] for d in client.get("/deals").json()["items"]]
    assert client.get(f"/deals/{seed.deal_a}").status_code == 404


def test_cannot_delete_other_tenant_deal(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    assert client.delete(f"/deals/{seed.deal_b}").status_code == 404


def test_members_add_list_remove(make_client, seed):
    # make user_none a member of org A first (required: only org members can
    # be added to a deal)
    from app.db.engine import get_session_factory
    from app.db.models import OrgMembership

    s = get_session_factory()()
    try:
        s.add(OrgMembership(org_id=seed.org_a, user_id=seed.user_none, role="member"))
        s.commit()
    finally:
        s.close()

    client = make_client(ROUTES, seed.user_a)
    r = client.post(
        f"/deals/{seed.deal_a}/members",
        json={"user_id": seed.user_none, "role": "analyst"},
    )
    assert r.status_code == 201, r.text

    members = client.get(f"/deals/{seed.deal_a}/members").json()
    assert {m["user_id"] for m in members} == {seed.user_a, seed.user_none}

    assert client.delete(f"/deals/{seed.deal_a}/members/{seed.user_none}").status_code == 204
    members = client.get(f"/deals/{seed.deal_a}/members").json()
    assert {m["user_id"] for m in members} == {seed.user_a}


def test_cannot_add_foreign_org_user_as_member(make_client, seed):
    # user_b belongs to org B, not org A → must not be addable to deal_a (IDOR)
    client = make_client(ROUTES, seed.user_a)
    r = client.post(f"/deals/{seed.deal_a}/members", json={"user_id": seed.user_b})
    assert r.status_code == 404


def test_filters_and_search(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    client.post("/deals", json={"org_id": seed.org_a, "name": "Acme Buyout", "status": "active"})
    client.post("/deals", json={"org_id": seed.org_a, "name": "Beta Merger", "status": "won"})

    won = client.get("/deals", params={"status": "won"}).json()["items"]
    assert all(d["status"] == "won" for d in won)

    found = client.get("/deals", params={"q": "Acme"}).json()["items"]
    assert any("Acme" in d["name"] for d in found)
