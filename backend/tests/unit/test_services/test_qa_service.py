"""Unit tests for QAService on the SQLite + sqlite-vec layer.

ask_meeting feeds a meeting's full transcript to a cheap model when it fits, and
falls back to deal-scoped RAG (QAService.ask) when the transcript is empty or too
large. These tests pin that decision boundary and the full-transcript prompt path,
plus the deal RAG path (embed + sqlite-vec KNN + citation of a retrieved chunk).
"""

from __future__ import annotations

import json

import pytest

from app.db.engine import (
    configure_engine,
    create_db_engine,
    get_session_factory,
)
from app.db.models import (
    Deal,
    Embedding,
    Meeting,
    Organization,
    Profile,
    TranscriptSegment,
)
from app.db.schema import init_schema
from app.db.vectors import upsert_vector
from app.llm.router import TASK_QA_MEETING
from app.services.qa_service import QAService

EMBEDDING_DIM = 768
# A fixed query vector that exactly matches the seeded RAG chunk vector below,
# so cosine similarity is 1.0 and the chunk is returned above MIN_SIMILARITY.
QUERY_VECTOR = [1.0] + [0.0] * (EMBEDDING_DIM - 1)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRouter:
    def __init__(self) -> None:
        self.complete_calls: list[dict] = []
        self.embed_calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return list(QUERY_VECTOR)

    async def complete(self, *, task_type, system_prompt, user_prompt, **kwargs):
        self.complete_calls.append(
            {"task_type": task_type, "user_prompt": user_prompt, **kwargs}
        )
        payload = {
            "answer": "John said revenue grew. [Source:chunk_0]",
            "citations_used": [{"chunk_id": "chunk_0", "relevance": "direct"}],
            "confidence": "high",
            "source_coverage": "Covered.",
        }
        return type("Resp", (), {"content": json.dumps(payload)})()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class Seed:
    org_id: str
    user_id: str
    deal_id: str
    meeting_id: str


@pytest.fixture()
def db(tmp_path):
    engine = create_db_engine(str(tmp_path / "qa.db"))
    configure_engine(engine)
    init_schema(engine)
    yield engine
    engine.dispose()


def _seed_base(session) -> Seed:
    s = Seed()
    org = Organization(name="Org", slug="org")
    user = Profile(email="u@x.com", full_name="U")
    session.add_all([org, user])
    session.flush()
    deal = Deal(org_id=org.id, name="Deal", created_by=user.id)
    session.add(deal)
    session.flush()
    meeting = Meeting(
        org_id=org.id, deal_id=deal.id, title="M", created_by=user.id
    )
    session.add(meeting)
    session.flush()
    s.org_id, s.user_id, s.deal_id, s.meeting_id = (
        org.id,
        user.id,
        deal.id,
        meeting.id,
    )
    return s


def _add_segment(session, meeting_id, *, text, speaker="John", start=0.0,
                 index=0, is_partial=False):
    seg = TranscriptSegment(
        meeting_id=meeting_id,
        speaker_label="spk_0",
        speaker_name=speaker,
        text=text,
        start_time=start,
        end_time=start + 1.0,
        segment_index=index,
        is_partial=is_partial,
    )
    session.add(seg)
    session.flush()
    return seg


def _add_embedding(session, *, org_id, deal_id, chunk_text, source_type,
                   source_id, vector):
    emb = Embedding(
        org_id=org_id,
        deal_id=deal_id,
        source_type=source_type,
        source_id=source_id,
        chunk_text=chunk_text,
        chunk_index=0,
        metadata_json={},
    )
    session.add(emb)
    session.flush()
    upsert_vector(
        session, embedding_id=emb.id, deal_id=deal_id, vector=vector
    )
    return emb


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_small_transcript_uses_cheap_model_with_full_transcript(db):
    session = get_session_factory()()
    try:
        s = _seed_base(session)
        _add_segment(
            session, s.meeting_id,
            text="Revenue grew 15% to fifty million.", speaker="John",
            start=1.0, index=0,
        )
        _add_segment(
            session, s.meeting_id, text="That's strong.", speaker="Mary",
            start=5.0, index=1,
        )
        session.commit()

        router = _FakeRouter()
        qa = QAService(session=session, llm_router=router)

        from uuid import UUID

        result = await qa.ask_meeting(
            deal_id=UUID(s.deal_id),
            meeting_id=UUID(s.meeting_id),
            question="What did John say?",
        )

        # Routed to the cheap meeting model, not RAG, and not via embeddings.
        assert router.embed_calls == []
        assert len(router.complete_calls) == 1
        call = router.complete_calls[0]
        assert call["task_type"] == TASK_QA_MEETING
        # The whole transcript (both speakers) is in the prompt context.
        assert "John: Revenue grew 15% to fifty million." in call["user_prompt"]
        assert "Mary: That's strong." in call["user_prompt"]
        assert result.answer.startswith("John said revenue grew")
    finally:
        session.close()


@pytest.mark.asyncio
async def test_empty_transcript_falls_back_to_rag(db):
    session = get_session_factory()()
    try:
        s = _seed_base(session)  # no segments, no embeddings
        session.commit()

        router = _FakeRouter()
        qa = QAService(session=session, llm_router=router)

        from uuid import UUID

        await qa.ask_meeting(
            deal_id=UUID(s.deal_id),
            meeting_id=UUID(s.meeting_id),
            question="What did John say?",
        )

        # Fallback went through the RAG path: it embedded the question and ran
        # the sqlite-vec KNN (which returned nothing here).
        assert router.embed_calls == ["What did John say?"]
    finally:
        session.close()


@pytest.mark.asyncio
async def test_oversized_transcript_falls_back_to_rag(db, monkeypatch):
    # Force the budget low so any non-empty transcript trips the fallback.
    monkeypatch.setattr(QAService, "MEETING_FULL_MAX_TOKENS", 1)
    session = get_session_factory()()
    try:
        s = _seed_base(session)
        _add_segment(
            session, s.meeting_id, text="word word word word word",
            speaker="John", start=0.0, index=0,
        )
        session.commit()

        router = _FakeRouter()
        qa = QAService(session=session, llm_router=router)

        from uuid import UUID

        await qa.ask_meeting(
            deal_id=UUID(s.deal_id),
            meeting_id=UUID(s.meeting_id),
            question="What did John say?",
        )

        assert router.embed_calls == ["What did John say?"]
    finally:
        session.close()


@pytest.mark.asyncio
async def test_deal_rag_ask_cites_retrieved_chunk(db):
    session = get_session_factory()()
    try:
        s = _seed_base(session)
        seg = _add_segment(
            session, s.meeting_id,
            text="Revenue grew 15% to fifty million.", speaker="John",
            start=2.0, index=0,
        )
        _add_embedding(
            session,
            org_id=s.org_id,
            deal_id=s.deal_id,
            chunk_text="John: Revenue grew 15% to fifty million.",
            source_type="transcript_segment",
            source_id=seg.id,
            vector=list(QUERY_VECTOR),
        )
        session.commit()

        router = _FakeRouter()
        qa = QAService(session=session, llm_router=router)

        from uuid import UUID

        result = await qa.ask(
            deal_id=UUID(s.deal_id), question="What did John say?"
        )

        # Embedded the question and retrieved the chunk via sqlite-vec KNN.
        assert router.embed_calls == ["What did John say?"]
        assert len(router.complete_calls) == 1
        assert result.answer.startswith("John said revenue grew")
        # The retrieved chunk was cited and enriched with meeting_id.
        assert len(result.citations) == 1
        cit = result.citations[0]
        assert cit.chunk_id == "chunk_0"
        assert cit.source_type == "transcript_segment"
        assert cit.metadata.get("meeting_id") == s.meeting_id
        assert cit.metadata.get("start_time") == 2.0
    finally:
        session.close()
