"""Regression tests for the Q&A history endpoints.

The context-first Q&A feature persisted citation JSON with richer keys than the
``Citation`` response schema (chunk_id, relevance, and spread metadata such as
meeting_id/start_time). Because the schema's base config is ``extra="forbid"``,
``GET /qa/history`` 500'd while re-serializing any interaction that had
citations. These tests lock in that:

  1. newly persisted citations use the canonical (schema-valid) shape, and
  2. legacy rows carrying the richer keys still deserialize (extras dropped)
     instead of raising, so historical prod data keeps working.
"""

from __future__ import annotations

from app.api.v1 import qa
from app.db.engine import get_session_factory
from app.db.models import QAInteraction

ROUTES = [("/deals/{deal_id}/qa", qa.router)]


def _add_interaction(deal_id: str, org_id: str, user_id: str, citations: list[dict]) -> None:
    session = get_session_factory()()
    try:
        session.add(
            QAInteraction(
                org_id=org_id,
                deal_id=deal_id,
                user_id=user_id,
                question="What is the main risk?",
                answer="Customer concentration.",
                citations=citations,
                grounding_score=0.9,
                model_used="llm-router",
            )
        )
        session.commit()
    finally:
        session.close()


def test_history_tolerates_legacy_rich_citations(make_client, seed):
    legacy = [
        {
            "chunk_id": "chunk_0",
            "source_id": seed.deal_a,  # uuid-shaped (a transcript/doc id in prod)
            "source_type": "transcript_segment",
            "text_excerpt": "top three customers are 55 percent of revenue",
            "relevance": "direct",
            "meeting_id": seed.deal_a,
            "start_time": 12.5,
        }
    ]
    _add_interaction(seed.deal_a, seed.org_a, seed.user_a, legacy)

    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/deals/{seed.deal_a}/qa/history")
    assert resp.status_code == 200, resp.text

    items = resp.json()["items"]
    assert len(items) == 1
    cite = items[0]["citations"][0]
    assert cite["source_type"] == "transcript_segment"
    assert cite["text_excerpt"].startswith("top three")
    # The forbidden extras are dropped, not echoed back.
    assert "chunk_id" not in cite
    assert "relevance" not in cite
    assert "meeting_id" not in cite


def test_history_detail_tolerates_legacy_rich_citations(make_client, seed):
    legacy = [
        {
            "chunk_id": "chunk_1",
            "source_id": seed.deal_a,
            "source_type": "document_chunk",
            "text_excerpt": "asking price is 6x EBITDA",
            "relevance": "supporting",
            "page": 3,
        }
    ]
    _add_interaction(seed.deal_a, seed.org_a, seed.user_a, legacy)

    client = make_client(ROUTES, seed.user_a)
    hist = client.get(f"/deals/{seed.deal_a}/qa/history")
    assert hist.status_code == 200, hist.text
    interaction_id = hist.json()["items"][0]["id"]

    detail = client.get(f"/deals/{seed.deal_a}/qa/history/{interaction_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["citations"][0]["text_excerpt"].startswith("asking price")


def test_history_empty_for_deal_without_qa(make_client, seed):
    client = make_client(ROUTES, seed.user_a)
    resp = client.get(f"/deals/{seed.deal_a}/qa/history")
    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []
