"""Per-deal share-gate tests for the partner API.

The partner API only exposes deals that have an ACTIVE CogniVault VDR connection,
and only the resource categories in that connection's ``share_scopes``. These tests
are the headline authorization checks: an unshared deal (or a withheld resource, or
a revoked connection) must be invisible to a valid, fully-scoped partner key.
"""

from __future__ import annotations

from app.db.engine import get_session_factory
from app.db.models import DealVdrConnection

from .conftest import RAW_KEY_FULL, auth


def _set_connection(
    conn_id: str, *, status: str | None = None, share_scopes: list[str] | None = None
) -> None:
    session = get_session_factory()()
    try:
        conn = session.get(DealVdrConnection, conn_id)
        assert conn is not None
        if status is not None:
            conn.status = status
        if share_scopes is not None:
            conn.share_scopes = share_scopes
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# unconnected deal → invisible (404), even within the key's own org
# ---------------------------------------------------------------------------
def test_unconnected_deal_get_is_404(client, seed):
    resp = client.get(f"/partner/v1/deals/{seed.deal_a2}", headers=auth(RAW_KEY_FULL))
    assert resp.status_code == 404


def test_unconnected_deal_documents_is_404(client, seed):
    resp = client.get(
        f"/partner/v1/deals/{seed.deal_a2}/documents", headers=auth(RAW_KEY_FULL)
    )
    assert resp.status_code == 404


def test_unconnected_deal_search_is_404(client, seed):
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_a2}/search",
        headers=auth(RAW_KEY_FULL),
        json={"query_vector": seed.vec_a2},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# the shared deal carries its VDR routing info
# ---------------------------------------------------------------------------
def test_deal_response_carries_vdr_id_and_scopes(client, seed):
    resp = client.get(f"/partner/v1/deals/{seed.deal_a}", headers=auth(RAW_KEY_FULL))
    assert resp.status_code == 200
    body = resp.json()
    assert body["vdr_id"] == "vdr-a"
    assert set(body["shared_scopes"]) == {
        "documents",
        "transcripts",
        "analyses",
        "search",
    }


# ---------------------------------------------------------------------------
# withheld resource category → 403 (deal is visible, this category isn't)
# ---------------------------------------------------------------------------
def test_withheld_documents_scope_is_403(client, seed):
    _set_connection(seed.conn_a, share_scopes=["transcripts", "analyses", "search"])
    resp = client.get(
        f"/partner/v1/deals/{seed.deal_a}/documents", headers=auth(RAW_KEY_FULL)
    )
    assert resp.status_code == 403


def test_withheld_search_scope_is_403(client, seed):
    _set_connection(seed.conn_a, share_scopes=["documents", "transcripts", "analyses"])
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_a}/search",
        headers=auth(RAW_KEY_FULL),
        json={"query_vector": seed.vec_a},
    )
    assert resp.status_code == 403


def test_withheld_transcripts_scope_is_403(client, seed):
    _set_connection(seed.conn_a, share_scopes=["documents", "analyses", "search"])
    resp = client.get(
        f"/partner/v1/meetings/{seed.meeting_a}/transcript", headers=auth(RAW_KEY_FULL)
    )
    assert resp.status_code == 403


def test_withheld_analyses_scope_is_403(client, seed):
    _set_connection(seed.conn_a, share_scopes=["documents", "transcripts", "search"])
    resp = client.get(
        f"/partner/v1/meetings/{seed.meeting_a}/analyses", headers=auth(RAW_KEY_FULL)
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# revocation is immediate — the next read 404s
# ---------------------------------------------------------------------------
def test_revoked_connection_hides_deal(client, seed):
    _set_connection(seed.conn_a, status="revoked")

    assert (
        client.get(f"/partner/v1/deals/{seed.deal_a}", headers=auth(RAW_KEY_FULL)).status_code
        == 404
    )
    listed = client.get("/partner/v1/deals", headers=auth(RAW_KEY_FULL))
    assert listed.status_code == 200
    assert all(d["id"] != seed.deal_a for d in listed.json())
    # the meeting → deal → connection gate revokes the transcript too
    assert (
        client.get(
            f"/partner/v1/meetings/{seed.meeting_a}/transcript",
            headers=auth(RAW_KEY_FULL),
        ).status_code
        == 404
    )


# ---------------------------------------------------------------------------
# a meeting not attached to a deal can never be shared → 404
# ---------------------------------------------------------------------------
def test_meeting_without_deal_is_404(client, seed):
    resp = client.get(
        f"/partner/v1/meetings/{seed.meeting_nodeal}/transcript",
        headers=auth(RAW_KEY_FULL),
    )
    assert resp.status_code == 404
