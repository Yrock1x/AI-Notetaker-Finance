"""Harness for the partner-API tests.

Builds a fresh file-backed SQLite DB per test, points the global engine at it,
and seeds two isolated orgs (A, B) each with an owner profile + membership +
deal, plus a meeting/transcript/analysis under org A and a couple of embeddings
for the search tests. A PartnerApiKey for org A (full scopes) and a second,
read-only key are created with sha256(raw_key) hashes.
"""

from __future__ import annotations

import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.partner.router import router as partner_router
from app.db.engine import configure_engine, create_db_engine, get_session_factory
from app.db.models import (
    Analysis,
    Deal,
    Embedding,
    Meeting,
    Organization,
    OrgMembership,
    PartnerApiKey,
    Profile,
    Transcript,
)
from app.db.schema import init_schema
from app.db.vectors import EMBEDDING_DIM, upsert_vector

# Known raw keys; the DB stores only the sha256 hashes.
RAW_KEY_FULL = "raw-partner-key-org-a-full"
RAW_KEY_READONLY = "raw-partner-key-org-a-readonly"
RAW_KEY_INACTIVE = "raw-partner-key-org-a-inactive"

FULL_SCOPES = [
    "deals:read",
    "deals:write",
    "documents:read",
    "documents:write",
    "transcripts:read",
    "search",
]


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _unit_vector(hot_index: int) -> list[float]:
    """A 768-dim unit vector with a single 1.0 at ``hot_index``."""
    vec = [0.0] * EMBEDDING_DIM
    vec[hot_index] = 1.0
    return vec


class Seed:
    def __init__(self) -> None:
        self.org_a = ""
        self.user_a = ""
        self.deal_a = ""
        self.deal_a2 = ""
        self.meeting_a = ""
        self.transcript_a = ""
        self.analysis_a = ""
        self.emb_a = ""
        self.emb_a2 = ""

        self.org_b = ""
        self.user_b = ""
        self.deal_b = ""
        self.meeting_b = ""

        self.key_full = ""
        self.key_readonly = ""

        # vectors used by the search tests
        self.vec_a = _unit_vector(0)
        self.vec_a2 = _unit_vector(1)


@pytest.fixture()
def db(tmp_path):
    engine = create_db_engine(str(tmp_path / "partner.db"))
    configure_engine(engine)
    init_schema(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def seed(db) -> Seed:
    s = Seed()
    session = get_session_factory()()
    try:
        # --- org A (full tenant) ---
        org_a = Organization(name="orga", slug="orga")
        user_a = Profile(email="orga@x.com", full_name="OrgA Owner")
        session.add_all([org_a, user_a])
        session.flush()
        session.add(OrgMembership(org_id=org_a.id, user_id=user_a.id, role="owner"))
        deal_a = Deal(org_id=org_a.id, name="orga deal", created_by=user_a.id)
        deal_a2 = Deal(org_id=org_a.id, name="orga deal 2", created_by=user_a.id)
        session.add_all([deal_a, deal_a2])
        session.flush()

        meeting_a = Meeting(
            org_id=org_a.id, deal_id=deal_a.id, title="A meeting", created_by=user_a.id
        )
        session.add(meeting_a)
        session.flush()
        transcript_a = Transcript(
            org_id=org_a.id,
            meeting_id=meeting_a.id,
            full_text="hello world",
            word_count=2,
        )
        analysis_done = Analysis(
            org_id=org_a.id,
            meeting_id=meeting_a.id,
            call_type="diligence",
            model_used="test-model",
            status="completed",
        )
        analysis_running = Analysis(
            org_id=org_a.id,
            meeting_id=meeting_a.id,
            call_type="diligence",
            model_used="test-model",
            status="running",
        )
        session.add_all([transcript_a, analysis_done, analysis_running])
        session.flush()

        # embeddings: one under deal_a (hot index 0), one under deal_a2 (index 1)
        emb_a = Embedding(
            org_id=org_a.id,
            deal_id=deal_a.id,
            source_type="document_chunk",
            source_id="src-a",
            chunk_text="deal A chunk",
        )
        emb_a2 = Embedding(
            org_id=org_a.id,
            deal_id=deal_a2.id,
            source_type="document_chunk",
            source_id="src-a2",
            chunk_text="deal A2 chunk",
        )
        session.add_all([emb_a, emb_a2])
        session.flush()
        upsert_vector(
            session, embedding_id=emb_a.id, deal_id=deal_a.id, vector=s.vec_a
        )
        upsert_vector(
            session, embedding_id=emb_a2.id, deal_id=deal_a2.id, vector=s.vec_a2
        )

        # --- org B (isolated tenant) ---
        org_b = Organization(name="orgb", slug="orgb")
        user_b = Profile(email="orgb@x.com", full_name="OrgB Owner")
        session.add_all([org_b, user_b])
        session.flush()
        session.add(OrgMembership(org_id=org_b.id, user_id=user_b.id, role="owner"))
        deal_b = Deal(org_id=org_b.id, name="orgb deal", created_by=user_b.id)
        session.add(deal_b)
        session.flush()
        meeting_b = Meeting(
            org_id=org_b.id, deal_id=deal_b.id, title="B meeting", created_by=user_b.id
        )
        session.add(meeting_b)
        session.flush()

        # --- API keys for org A ---
        key_full = PartnerApiKey(
            org_id=org_a.id,
            name="full key",
            key_hash=_hash(RAW_KEY_FULL),
            scopes=FULL_SCOPES,
            is_active=True,
        )
        key_readonly = PartnerApiKey(
            org_id=org_a.id,
            name="readonly key",
            key_hash=_hash(RAW_KEY_READONLY),
            scopes=["deals:read"],
            is_active=True,
        )
        key_inactive = PartnerApiKey(
            org_id=org_a.id,
            name="inactive key",
            key_hash=_hash(RAW_KEY_INACTIVE),
            scopes=FULL_SCOPES,
            is_active=False,
        )
        session.add_all([key_full, key_readonly, key_inactive])
        session.flush()

        s.org_a, s.user_a = org_a.id, user_a.id
        s.deal_a, s.deal_a2 = deal_a.id, deal_a2.id
        s.meeting_a, s.transcript_a = meeting_a.id, transcript_a.id
        s.analysis_a = analysis_done.id
        s.emb_a, s.emb_a2 = emb_a.id, emb_a2.id
        s.org_b, s.user_b = org_b.id, user_b.id
        s.deal_b, s.meeting_b = deal_b.id, meeting_b.id
        s.key_full, s.key_readonly = key_full.id, key_readonly.id

        session.commit()
    finally:
        session.close()
    return s


@pytest.fixture()
def client(db) -> TestClient:
    app = FastAPI()
    app.include_router(partner_router, prefix="")
    return TestClient(app)


def auth(raw_key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw_key}"}
