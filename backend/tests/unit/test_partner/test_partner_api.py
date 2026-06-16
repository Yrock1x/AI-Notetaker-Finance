"""End-to-end tests for the CogniVault partner API.

Covers auth (valid/unknown/inactive keys), scope gating, cross-tenant isolation,
creation, scoped vector search, and audit logging.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.engine import get_session_factory
from app.db.models import AuditLog, Deal, Document

from .conftest import (
    RAW_KEY_FULL,
    RAW_KEY_INACTIVE,
    RAW_KEY_READONLY,
    auth,
)


# ---------------------------------------------------------------------------
# auth
# ---------------------------------------------------------------------------
def test_valid_key_lists_only_shared_deals_in_its_org(client, seed):
    resp = client.get("/partner/v1/deals", headers=auth(RAW_KEY_FULL))
    assert resp.status_code == 200
    ids = {d["id"] for d in resp.json()}
    assert seed.deal_a in ids  # shared (active VDR connection)
    assert seed.deal_a2 not in ids  # org A but NOT shared
    assert seed.deal_b not in ids  # org B is invisible


def test_unknown_key_is_401(client, seed):
    resp = client.get("/partner/v1/deals", headers=auth("totally-bogus-key"))
    assert resp.status_code == 401


def test_inactive_key_is_401(client, seed):
    resp = client.get("/partner/v1/deals", headers=auth(RAW_KEY_INACTIVE))
    assert resp.status_code == 401


def test_missing_auth_header_is_401(client, seed):
    resp = client.get("/partner/v1/deals")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# scope gating
# ---------------------------------------------------------------------------
def test_key_without_write_scope_gets_403_on_create(client, seed):
    resp = client.post(
        "/partner/v1/deals",
        headers=auth(RAW_KEY_READONLY),
        json={"name": "should fail"},
    )
    assert resp.status_code == 403


def test_readonly_key_can_still_read(client, seed):
    resp = client.get("/partner/v1/deals", headers=auth(RAW_KEY_READONLY))
    assert resp.status_code == 200


def test_readonly_key_lacks_search_scope(client, seed):
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_a}/search",
        headers=auth(RAW_KEY_READONLY),
        json={"query_vector": seed.vec_a},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# cross-tenant isolation
# ---------------------------------------------------------------------------
def test_org_a_key_cannot_read_org_b_deal(client, seed):
    resp = client.get(
        f"/partner/v1/deals/{seed.deal_b}", headers=auth(RAW_KEY_FULL)
    )
    assert resp.status_code == 404


def test_org_a_key_cannot_read_org_b_meeting_transcript(client, seed):
    resp = client.get(
        f"/partner/v1/meetings/{seed.meeting_b}/transcript",
        headers=auth(RAW_KEY_FULL),
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# reads
# ---------------------------------------------------------------------------
def test_get_deal_in_org(client, seed):
    resp = client.get(
        f"/partner/v1/deals/{seed.deal_a}", headers=auth(RAW_KEY_FULL)
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == seed.deal_a


def test_get_transcript(client, seed):
    resp = client.get(
        f"/partner/v1/meetings/{seed.meeting_a}/transcript",
        headers=auth(RAW_KEY_FULL),
    )
    assert resp.status_code == 200
    assert resp.json()["meeting_id"] == seed.meeting_a
    assert resp.json()["full_text"] == "hello world"


def test_list_analyses_only_completed(client, seed):
    resp = client.get(
        f"/partner/v1/meetings/{seed.meeting_a}/analyses",
        headers=auth(RAW_KEY_FULL),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == seed.analysis_a
    assert body[0]["status"] == "completed"


# ---------------------------------------------------------------------------
# writes
# ---------------------------------------------------------------------------
def test_create_deal_in_org_a(client, seed):
    resp = client.post(
        "/partner/v1/deals",
        headers=auth(RAW_KEY_FULL),
        json={"name": "partner-made deal", "deal_type": "general"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["org_id"] == seed.org_a
    assert body["created_by"] == seed.user_a  # attributed to the org owner

    session = get_session_factory()()
    try:
        deal = session.get(Deal, body["id"])
        assert deal is not None
        assert deal.org_id == seed.org_a
    finally:
        session.close()


def test_create_document_under_org_a_deal(client, seed):
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_a}/documents",
        headers=auth(RAW_KEY_FULL),
        json={
            "title": "CIM.pdf",
            "document_type": "cim",
            "file_key": "deals/a/cim.pdf",
            "file_size": 1234,
            "extracted_text": "some text",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["deal_id"] == seed.deal_a
    assert body["org_id"] == seed.org_a
    assert body["uploaded_by"] == seed.user_a

    session = get_session_factory()()
    try:
        doc = session.get(Document, body["id"])
        assert doc is not None
        assert doc.deal_id == seed.deal_a
    finally:
        session.close()


def test_list_documents_for_deal(client, seed):
    client.post(
        f"/partner/v1/deals/{seed.deal_a}/documents",
        headers=auth(RAW_KEY_FULL),
        json={"title": "t", "document_type": "other", "file_key": "k"},
    )
    resp = client.get(
        f"/partner/v1/deals/{seed.deal_a}/documents",
        headers=auth(RAW_KEY_FULL),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_create_document_on_org_b_deal_is_404(client, seed):
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_b}/documents",
        headers=auth(RAW_KEY_FULL),
        json={"title": "x", "document_type": "other", "file_key": "k"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# vector search
# ---------------------------------------------------------------------------
def test_search_returns_nearest_scoped_to_deal(client, seed):
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_a}/search",
        headers=auth(RAW_KEY_FULL),
        json={"query_vector": seed.vec_a, "top_k": 5},
    )
    assert resp.status_code == 200
    hits = resp.json()
    assert len(hits) == 1
    assert hits[0]["id"] == seed.emb_a
    # deal_a2's embedding must not leak into deal_a's search
    assert all(h["id"] != seed.emb_a2 for h in hits)


def test_search_other_deals_embedding_not_returned(client, seed):
    # querying deal_a with deal_a2's vector returns nothing from deal_a2
    resp = client.post(
        f"/partner/v1/deals/{seed.deal_a}/search",
        headers=auth(RAW_KEY_FULL),
        json={"query_vector": seed.vec_a2},
    )
    assert resp.status_code == 200
    ids = {h["id"] for h in resp.json()}
    assert seed.emb_a2 not in ids


# ---------------------------------------------------------------------------
# audit logging
# ---------------------------------------------------------------------------
def _audit_count() -> int:
    session = get_session_factory()()
    try:
        return len(
            session.scalars(
                select(AuditLog).where(AuditLog.resource_type == "partner")
            ).all()
        )
    finally:
        session.close()


def test_successful_calls_write_audit_rows(client, seed):
    before = _audit_count()

    assert client.get("/partner/v1/deals", headers=auth(RAW_KEY_FULL)).status_code == 200
    assert (
        client.get(
            f"/partner/v1/deals/{seed.deal_a}", headers=auth(RAW_KEY_FULL)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/partner/v1/deals",
            headers=auth(RAW_KEY_FULL),
            json={"name": "audited deal"},
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/partner/v1/deals/{seed.deal_a}/search",
            headers=auth(RAW_KEY_FULL),
            json={"query_vector": seed.vec_a},
        ).status_code
        == 200
    )

    after = _audit_count()
    assert after == before + 4

    # audit rows for partner calls have no user_id (M2M)
    session = get_session_factory()()
    try:
        rows = session.scalars(
            select(AuditLog).where(AuditLog.resource_type == "partner")
        ).all()
        assert all(r.user_id is None for r in rows)
        assert all(r.org_id == seed.org_a for r in rows)
    finally:
        session.close()
