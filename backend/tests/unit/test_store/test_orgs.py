"""Tests for the orgs store router — membership listing, cross-tenant denial."""

from __future__ import annotations

from app.api.v1.store import orgs

ROUTES = [("", orgs.router)]


def test_list_orgs_returns_only_own_org(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.get("/orgs")
    assert resp.status_code == 200
    body = resp.json()
    ids = [o["id"] for o in body]
    assert ids == [seed.org_a]
    assert seed.org_b not in ids
    assert body[0]["role"] == "owner"


def test_list_orgs_empty_for_user_without_membership(make_client, seed):
    client = make_client(ROUTES, seed.user_none)
    assert client.get("/orgs").json() == []


def test_members_for_own_org(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/orgs/{seed.org_a}/members")
    assert resp.status_code == 200, resp.text
    members = resp.json()
    assert {m["user_id"] for m in members} == {seed.user_a}
    assert members[0]["role"] == "owner"
    assert members[0]["email"] == "orga@x.com"


def test_members_for_other_org_denied(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    assert client.get(f"/orgs/{seed.org_b}/members").status_code == 403
