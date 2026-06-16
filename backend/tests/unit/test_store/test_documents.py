"""Tests for the Documents store router — create/list/get + cross-tenant scoping."""

from __future__ import annotations

from app.api.v1.store import documents

ROUTES = [("", documents.router)]


def _create(client, deal_id, **overrides):
    body = {
        "title": "Pitch Deck",
        "document_type": "pdf",
        "file_key": "deals/x/deck.pdf",
        "file_size": 1234,
    }
    body.update(overrides)
    return client.post(f"/deals/{deal_id}/documents", json=body)


def test_create_then_list_scoped_to_deal(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = _create(client, seed.deal_a, title="Deck A")
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["deal_id"] == seed.deal_a
    assert body["org_id"] == seed.org_a
    assert body["uploaded_by"] == seed.user_a
    assert "extracted_text" not in body  # list/create response excludes it

    listing = client.get(f"/deals/{seed.deal_a}/documents")
    assert listing.status_code == 200
    items = listing.json()
    assert [d["id"] for d in items] == [body["id"]]
    assert "extracted_text" not in items[0]


def test_get_includes_extracted_text(make_client, seed, db):
    from app.db.engine import get_session_factory
    from app.db.models import Document

    session = get_session_factory()()
    try:
        doc = Document(
            org_id=seed.org_a,
            deal_id=seed.deal_a,
            title="Memo",
            document_type="docx",
            file_key="k",
            file_size=10,
            extracted_text="the full body text",
            uploaded_by=seed.user_a,
        )
        session.add(doc)
        session.commit()
        doc_id = doc.id
    finally:
        session.close()

    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/documents/{doc_id}")
    assert resp.status_code == 200, resp.text
    assert resp.json()["extracted_text"] == "the full body text"


def test_org_b_cannot_list_org_a_deal_documents(make_client, seed):
    _create(make_client(ROUTES, seed.user_a), seed.deal_a)
    client_b = make_client(ROUTES, seed.user_b)
    assert client_b.get(f"/deals/{seed.deal_a}/documents").status_code == 404


def test_org_b_cannot_get_org_a_document(make_client, seed):
    resp = _create(make_client(ROUTES, seed.user_a), seed.deal_a)
    doc_id = resp.json()["id"]
    client_b = make_client(ROUTES, seed.user_b)
    assert client_b.get(f"/documents/{doc_id}").status_code == 404


def test_create_under_other_tenant_deal_404s(make_client, seed):
    client_b = make_client(ROUTES, seed.user_b)
    assert _create(client_b, seed.deal_a).status_code == 404
