"""Startup-validation tests for LLMRouter.validate_routing()."""

from __future__ import annotations

import pytest

from app.llm.provider import EmbeddingProvider, LLMProvider, LLMResponse
from app.llm.router import LLMRouter


class _StubLLM(LLMProvider):
    async def complete(self, *a, **k) -> LLMResponse:  # pragma: no cover - not called
        return LLMResponse(content="", model="stub", usage={})

    async def stream(self, *a, **k):  # pragma: no cover - not called
        yield ""


class _StubEmbed(EmbeddingProvider):
    async def embed(self, text: str):  # pragma: no cover - not called
        return [0.0]

    async def embed_batch(self, texts):  # pragma: no cover - not called
        return [[0.0] for _ in texts]


def test_validate_routing_raises_when_no_providers():
    with pytest.raises(RuntimeError, match="not registered"):
        LLMRouter().validate_routing()


def test_validate_routing_passes_with_fireworks_registered():
    r = LLMRouter()
    r.register_provider("fireworks", _StubLLM())
    r.register_embedding_provider("fireworks", _StubEmbed())
    # All default tasks route to fireworks; none to anthropic → should pass.
    r.validate_routing()


def test_validate_routing_skips_anthropic_when_premium_off(monkeypatch):
    # Route a task to anthropic but leave PREMIUM off → validation skips it.
    monkeypatch.setenv("LLM_MODEL_FOR_IC_MEMO", "anthropic:claude-sonnet-4-6")
    monkeypatch.delenv("PREMIUM_LLM_ENABLED", raising=False)
    r = LLMRouter()
    r.register_provider("fireworks", _StubLLM())
    r.register_embedding_provider("fireworks", _StubEmbed())
    r.validate_routing()  # anthropic ic_memo skipped, no RuntimeError


def test_validate_routing_requires_anthropic_when_premium_on(monkeypatch):
    monkeypatch.setenv("LLM_MODEL_FOR_IC_MEMO", "anthropic:claude-sonnet-4-6")
    monkeypatch.setenv("PREMIUM_LLM_ENABLED", "true")
    r = LLMRouter()
    r.register_provider("fireworks", _StubLLM())
    r.register_embedding_provider("fireworks", _StubEmbed())
    with pytest.raises(RuntimeError, match="anthropic"):
        r.validate_routing()
