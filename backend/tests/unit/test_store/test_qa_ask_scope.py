"""Endpoint-level tests for meeting-scoped Q&A on the deal /ask route.

Covers the HTTP path the service-level QAService tests don't:
  1. a meeting from ANOTHER deal cannot be used to scope a deal's ask (tenant
     safety — _require_meetings_in_deal returns 404), and
  2. scoping to the caller's own meeting that has no transcript short-circuits
     to a 200 "no transcript" answer without ever touching the LLM.
"""

from __future__ import annotations

import pytest

from app.api.v1 import qa
from app.core.rate_limit import limiter
from app.db.engine import get_session_factory
from app.db.models import Meeting
from app.dependencies import get_llm_router

ROUTES = [("/deals/{deal_id}/qa", qa.router)]


class _NoLLM:
    """A router that fails loudly if any LLM call is attempted — proves the
    short-circuit path never spends tokens."""

    async def embed(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("LLM embed must not be called on the no-transcript path")

    async def complete(self, *a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("LLM complete must not be called on the no-transcript path")


@pytest.fixture(autouse=True)
def _no_rate_limit():
    # The /ask route is @limiter.limit(...)-decorated; the bare test app has no
    # limiter state, so disable limiting for these tests.
    prev = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = prev


def _add_meeting(org_id: str, deal_id: str, user_id: str, title: str) -> str:
    session = get_session_factory()()
    try:
        m = Meeting(org_id=org_id, deal_id=deal_id, title=title, created_by=user_id)
        session.add(m)
        session.commit()
        return m.id
    finally:
        session.close()


def test_ask_rejects_meeting_from_another_deal(make_client, seed):
    foreign = _add_meeting(seed.org_b, seed.deal_b, seed.user_b, "Foreign call")
    client = make_client(ROUTES, seed.user_a)
    client.app.dependency_overrides[get_llm_router] = lambda: _NoLLM()

    resp = client.post(
        f"/deals/{seed.deal_a}/qa/ask",
        json={"question": "What was said?", "meeting_ids": [foreign]},
    )
    # The cross-deal meeting must not be addressable from deal_a.
    assert resp.status_code == 404, resp.text


def test_ask_scoped_to_own_meeting_without_transcript_short_circuits(make_client, seed):
    mine = _add_meeting(seed.org_a, seed.deal_a, seed.user_a, "My call")
    client = make_client(ROUTES, seed.user_a)
    client.app.dependency_overrides[get_llm_router] = lambda: _NoLLM()

    resp = client.post(
        f"/deals/{seed.deal_a}/qa/ask",
        json={"question": "What was said?", "meeting_ids": [mine]},
    )
    assert resp.status_code == 200, resp.text
    # Validation passed; the no-transcript short-circuit answered without an LLM call.
    assert resp.json()["answer"]
