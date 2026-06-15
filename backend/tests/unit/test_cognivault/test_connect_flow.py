"""Tests for the CogniVault Connect-VDR endpoints (connect / callback / manage)."""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.core.config import settings
from app.db.engine import get_session_factory
from app.db.models import AuditLog, DealVdrConnection
from app.services.oauth_tokens import build_vdr_connect_state


def _active_conn_stmt(deal_id: str):
    return select(DealVdrConnection).where(
        DealVdrConnection.deal_id == deal_id,
        DealVdrConnection.status == "active",
    )


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------
def test_connect_returns_authorize_url_with_deal_context(make_client, seed):
    client = make_client(seed.user_a)
    resp = client.post(f"/api/v1/cognivault/deals/{seed.deal_a}/connect")
    assert resp.status_code == 200
    url = resp.json()["authorization_url"]
    assert url.startswith("https://vault.example.com/oauth/authorize?")
    qs = parse_qs(urlparse(url).query)
    assert qs["client_id"] == ["cogniscribe-client"]
    assert qs["redirect_uri"] == ["https://worker.example.com/api/v1/cognivault/callback"]
    assert qs["deal_ref"] == [seed.deal_a]
    assert qs["state"]  # signed JWT carrying org/user/deal


def test_connect_requires_deal_access(make_client, seed):
    # a user with no membership in the deal's org cannot start a connection
    client = make_client(seed.user_none)
    resp = client.post(f"/api/v1/cognivault/deals/{seed.deal_a}/connect")
    assert resp.status_code == 404


def test_connect_500_when_not_configured(make_client, seed, monkeypatch):
    monkeypatch.setattr(settings, "cognivault_client_id", "")
    client = make_client(seed.user_a)
    resp = client.post(f"/api/v1/cognivault/deals/{seed.deal_a}/connect")
    assert resp.status_code == 500


# ---------------------------------------------------------------------------
# callback → creates the connection
# ---------------------------------------------------------------------------
def _patch_exchange(monkeypatch, *, vdr_id="vdr-xyz", vdr_name="Acme VDR"):
    async def _fake_exchange(**_kwargs):
        return {
            "access_token": None,
            "refresh_token": None,
            "expires_in": None,
            "scope": "vdr.share",
            "vdr_id": vdr_id,
            "vdr_name": vdr_name,
        }

    monkeypatch.setattr(
        "app.integrations.cognivault.oauth.exchange_code", _fake_exchange
    )


def test_callback_creates_active_connection(make_client, seed, monkeypatch):
    _patch_exchange(monkeypatch)
    client = make_client(seed.user_a)
    state = build_vdr_connect_state(seed.org_a, seed.user_a, seed.deal_a)

    resp = client.get(
        "/api/v1/cognivault/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        resp.headers["location"]
        == f"https://app.example.com/deals/{seed.deal_a}/settings?connected=cognivault"
    )

    session = get_session_factory()()
    try:
        conn = session.scalar(_active_conn_stmt(seed.deal_a))
        assert conn is not None
        assert conn.status == "active"
        assert conn.vdr_id == "vdr-xyz"
        assert set(conn.share_scopes) == {
            "documents",
            "transcripts",
            "analyses",
            "search",
        }
        audit = session.scalars(
            select(AuditLog).where(AuditLog.action == "share")
        ).all()
        assert len(audit) == 1
    finally:
        session.close()


def test_callback_missing_vdr_redirects_error(make_client, seed, monkeypatch):
    _patch_exchange(monkeypatch, vdr_id=None)
    client = make_client(seed.user_a)
    state = build_vdr_connect_state(seed.org_a, seed.user_a, seed.deal_a)
    resp = client.get(
        "/api/v1/cognivault/callback",
        params={"code": "auth-code", "state": state},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "error=missing_vdr" in resp.headers["location"]


def test_callback_rejects_tampered_state(make_client, seed):
    client = make_client(seed.user_a)
    resp = client.get(
        "/api/v1/cognivault/callback",
        params={"code": "auth-code", "state": "not-a-valid-jwt"},
        follow_redirects=False,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# manage: get / patch scopes / disconnect
# ---------------------------------------------------------------------------
def _connect(client, seed, monkeypatch):
    _patch_exchange(monkeypatch)
    state = build_vdr_connect_state(seed.org_a, seed.user_a, seed.deal_a)
    client.get(
        "/api/v1/cognivault/callback",
        params={"code": "c", "state": state},
        follow_redirects=False,
    )


def test_get_connection_before_and_after(make_client, seed, monkeypatch):
    client = make_client(seed.user_a)
    # before connecting
    resp = client.get(f"/api/v1/cognivault/deals/{seed.deal_a}/connection")
    assert resp.status_code == 200
    assert resp.json()["connected"] is False

    _connect(client, seed, monkeypatch)
    resp = client.get(f"/api/v1/cognivault/deals/{seed.deal_a}/connection")
    assert resp.status_code == 200
    body = resp.json()
    assert body["connected"] is True
    assert body["vdr_id"] == "vdr-xyz"


def test_patch_share_scopes(make_client, seed, monkeypatch):
    client = make_client(seed.user_a)
    _connect(client, seed, monkeypatch)
    resp = client.patch(
        f"/api/v1/cognivault/deals/{seed.deal_a}/connection",
        json={"share_scopes": ["documents", "search"]},
    )
    assert resp.status_code == 200
    assert resp.json()["share_scopes"] == ["documents", "search"]


def test_patch_rejects_unknown_scope(make_client, seed, monkeypatch):
    client = make_client(seed.user_a)
    _connect(client, seed, monkeypatch)
    resp = client.patch(
        f"/api/v1/cognivault/deals/{seed.deal_a}/connection",
        json={"share_scopes": ["documents", "bogus"]},
    )
    assert resp.status_code == 400


def test_patch_without_connection_is_404(make_client, seed):
    client = make_client(seed.user_a)
    resp = client.patch(
        f"/api/v1/cognivault/deals/{seed.deal_a}/connection",
        json={"share_scopes": ["documents"]},
    )
    assert resp.status_code == 404


def test_disconnect_revokes(make_client, seed, monkeypatch):
    client = make_client(seed.user_a)
    _connect(client, seed, monkeypatch)
    resp = client.delete(f"/api/v1/cognivault/deals/{seed.deal_a}/connection")
    assert resp.status_code == 204
    # connection is no longer active
    resp = client.get(f"/api/v1/cognivault/deals/{seed.deal_a}/connection")
    assert resp.json()["connected"] is False
