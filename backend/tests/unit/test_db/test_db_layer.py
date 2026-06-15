"""Foundation tests for the SQLite data layer (WS1-3).

Covers: schema creation, vec0 KNN search + per-deal scoping, and the app-layer
RLS scoping module (cross-tenant denial).
"""

from __future__ import annotations

import math

import pytest
from sqlalchemy import select

from app.db.base import gen_uuid
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import (
    Deal,
    Embedding,
    Organization,
    OrgMembership,
    Profile,
)
from app.db.schema import init_schema
from app.db.scope import AccessDenied, load_principal, org_scoped, require_org
from app.db.vectors import match_embeddings_for_deal, upsert_vector


@pytest.fixture()
def session(tmp_path):
    engine = create_db_engine(str(tmp_path / "test.db"))
    configure_engine(engine)
    init_schema(engine)
    factory = get_session_factory()
    s = factory()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _unit_vector(dim: int, hot: int) -> list[float]:
    """A unit vector pointing along axis ``hot`` (distinct, normalized)."""
    v = [0.0] * dim
    v[hot] = 1.0
    return v


def _seed_org_user_deal(session, *, slug: str, role: str = "owner"):
    org = Organization(name=slug, slug=slug)
    user = Profile(email=f"{slug}@example.com", full_name=slug)
    session.add_all([org, user])
    session.flush()
    session.add(OrgMembership(org_id=org.id, user_id=user.id, role=role))
    deal = Deal(org_id=org.id, name=f"{slug} deal", created_by=user.id)
    session.add(deal)
    session.flush()
    return org, user, deal


def test_schema_creates_all_tables(session):
    # A representative set of tables should be queryable.
    assert session.scalars(select(Organization)).all() == []
    assert session.scalars(select(Deal)).all() == []


def test_vector_knn_scoped_to_deal(session):
    _, _, deal_a = _seed_org_user_deal(session, slug="orga")
    _, _, deal_b = _seed_org_user_deal(session, slug="orgb")

    # Two embeddings in deal A pointing along axes 0 and 5; one in deal B.
    def add_emb(deal, hot, text):
        emb = Embedding(
            org_id=deal.org_id,
            deal_id=deal.id,
            source_type="transcript_segment",
            source_id=gen_uuid(),
            chunk_text=text,
            metadata_json={"hot": hot},
        )
        session.add(emb)
        session.flush()
        upsert_vector(session, embedding_id=emb.id, deal_id=deal.id, vector=_unit_vector(768, hot))
        return emb

    add_emb(deal_a, 0, "deal A axis0")
    add_emb(deal_a, 5, "deal A axis5")
    add_emb(deal_b, 0, "deal B axis0")
    session.commit()

    # Query along axis 0, scoped to deal A: best match is "deal A axis0",
    # and deal B's axis0 chunk must NOT appear.
    results = match_embeddings_for_deal(
        session, deal_id=deal_a.id, query_vector=_unit_vector(768, 0), top_k=10
    )
    texts = [r["chunk_text"] for r in results]
    assert "deal A axis0" in texts
    assert "deal B axis0" not in texts
    assert results[0]["chunk_text"] == "deal A axis0"
    assert math.isclose(results[0]["similarity"], 1.0, abs_tol=1e-3)


def test_min_similarity_filters_orthogonal(session):
    _, _, deal = _seed_org_user_deal(session, slug="orgc")
    emb = Embedding(
        org_id=deal.org_id,
        deal_id=deal.id,
        source_type="document_chunk",
        source_id=gen_uuid(),
        chunk_text="orthogonal",
        metadata_json={},
    )
    session.add(emb)
    session.flush()
    upsert_vector(session, embedding_id=emb.id, deal_id=deal.id, vector=_unit_vector(768, 1))
    session.commit()

    # Query orthogonal axis → cosine similarity 0 → below default 0.3 floor.
    results = match_embeddings_for_deal(
        session, deal_id=deal.id, query_vector=_unit_vector(768, 9), min_similarity=0.3
    )
    assert results == []


def test_org_scoped_query_isolates_tenants(session):
    _, user_a, deal_a = _seed_org_user_deal(session, slug="t1")
    _, _, deal_b = _seed_org_user_deal(session, slug="t2")
    session.commit()

    principal = load_principal(session, user_a.id)
    visible = session.scalars(org_scoped(select(Deal), Deal, principal)).all()
    visible_ids = {d.id for d in visible}
    assert deal_a.id in visible_ids
    assert deal_b.id not in visible_ids


def test_require_org_denies_outsider(session):
    _, user_a, _ = _seed_org_user_deal(session, slug="t3")
    org_b, _, _ = _seed_org_user_deal(session, slug="t4")
    session.commit()

    principal = load_principal(session, user_a.id)
    require_org(principal, principal.org_ids[0])  # own org: ok
    with pytest.raises(AccessDenied):
        require_org(principal, org_b.id)  # someone else's org: denied
