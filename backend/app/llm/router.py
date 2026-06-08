"""Task → model routing for LLM calls.

Every LLM call in the app goes through ``LLMRouter.complete(task_type, ...)``.
The router picks a model based on a task → model table:

    summarization  → fireworks/...glm-5p1                    (cheap, default)
    action_items   → fireworks/...glm-5p1
    qa_rag         → fireworks/...deepseek-v4-pro             (stronger reasoning)
    qa_meeting     → fireworks/...glm-5p1                     (cheap, full transcript)
    ic_memo        → fireworks/...deepseek-v4-pro
    general        → fireworks/...glm-5p1

Each row can be overridden at runtime with an env var, e.g.
``LLM_MODEL_FOR_IC_MEMO=anthropic:claude-sonnet-4-6``.

Claude is off by default. Any task routed to an ``anthropic:*`` model while
``PREMIUM_LLM_ENABLED`` is false raises at call time — keeps you from silently
burning through Anthropic credits when you meant to run on Fireworks.
"""

from __future__ import annotations

import os

from app.llm.provider import EmbeddingProvider, LLMProvider, LLMResponse

# Canonical task names — keep short and stable. Add here when a new call site
# needs its own routing knob.
TASK_SUMMARIZATION = "summarization"
TASK_ACTION_ITEMS = "action_items"
TASK_QA_RAG = "qa_rag"
# Single-meeting Q&A: stuff the whole transcript into a cheap model instead of
# RAG retrieval. No embeddings/chunk-boundary failure modes, and far cheaper.
TASK_QA_MEETING = "qa_meeting"
TASK_IC_MEMO = "ic_memo"
TASK_GENERAL = "general"
TASK_EMBEDDING = "embedding"

# Defaults. Format: "<provider>:<model>" where provider is "fireworks" or
# "anthropic". Everything is Fireworks by default.
_FIREWORKS_GLM = "fireworks:accounts/fireworks/models/glm-5p1"
_FIREWORKS_DEEPSEEK = "fireworks:accounts/fireworks/models/deepseek-v4-pro"
_FIREWORKS_NOMIC = "fireworks:nomic-ai/nomic-embed-text-v1.5"

_DEFAULT_TASK_MODEL_MAP: dict[str, str] = {
    TASK_SUMMARIZATION: _FIREWORKS_GLM,
    TASK_ACTION_ITEMS: _FIREWORKS_GLM,
    TASK_QA_RAG: _FIREWORKS_DEEPSEEK,
    TASK_QA_MEETING: _FIREWORKS_GLM,
    TASK_IC_MEMO: _FIREWORKS_DEEPSEEK,
    TASK_GENERAL: _FIREWORKS_GLM,
    TASK_EMBEDDING: _FIREWORKS_NOMIC,
}

_ENV_OVERRIDE_KEYS: dict[str, str] = {
    TASK_SUMMARIZATION: "LLM_MODEL_FOR_SUMMARIZATION",
    TASK_ACTION_ITEMS: "LLM_MODEL_FOR_ACTION_ITEMS",
    TASK_QA_RAG: "LLM_MODEL_FOR_QA_RAG",
    TASK_QA_MEETING: "LLM_MODEL_FOR_QA_MEETING",
    TASK_IC_MEMO: "LLM_MODEL_FOR_IC_MEMO",
    TASK_GENERAL: "LLM_MODEL_FOR_GENERAL",
    TASK_EMBEDDING: "LLM_MODEL_FOR_EMBEDDING",
}


def _resolve_model(task_type: str) -> tuple[str, str]:
    """Return ``(provider, model)`` for the given task."""
    env_key = _ENV_OVERRIDE_KEYS.get(task_type)
    spec = (os.getenv(env_key) if env_key else None) or _DEFAULT_TASK_MODEL_MAP.get(task_type)
    if not spec:
        spec = _DEFAULT_TASK_MODEL_MAP[TASK_GENERAL]

    if ":" not in spec:
        raise ValueError(
            f"Invalid model spec for {task_type}: {spec!r} "
            "(expected '<provider>:<model>')"
        )
    provider, model = spec.split(":", 1)
    return provider.strip(), model.strip()


def _premium_llm_enabled() -> bool:
    return os.getenv("PREMIUM_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


class LLMRouter:
    """Task-aware router over registered LLM + embedding providers."""

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._embedding_providers: dict[str, EmbeddingProvider] = {}

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider

    def register_embedding_provider(
        self, name: str, provider: EmbeddingProvider
    ) -> None:
        self._embedding_providers[name] = provider

    async def complete(
        self,
        task_type: str,
        system_prompt: str,
        user_prompt: str,
        **kwargs: object,
    ) -> LLMResponse:
        provider_name, model = _resolve_model(task_type)
        if provider_name == "anthropic" and not _premium_llm_enabled():
            raise RuntimeError(
                f"Task '{task_type}' routed to Anthropic but PREMIUM_LLM_ENABLED "
                "is not true. Set PREMIUM_LLM_ENABLED=true or change the model "
                f"override env var ({_ENV_OVERRIDE_KEYS.get(task_type)})."
            )

        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"No LLM provider registered for '{provider_name}'")

        # Pin the specific model on providers that support it. Providers carry
        # a default model; callers who want a different one pass it through.
        kwargs.setdefault("model", model)
        if hasattr(provider, "model"):
            provider.model = model  # type: ignore[attr-defined]

        return await provider.complete(system_prompt, user_prompt, **kwargs)

    async def embed(self, text: str) -> list[float]:
        provider_name, model = _resolve_model(TASK_EMBEDDING)
        provider = self._embedding_providers.get(provider_name)
        if not provider:
            raise ValueError(
                f"No embedding provider registered for '{provider_name}'"
            )
        if hasattr(provider, "model"):
            provider.model = model  # type: ignore[attr-defined]
        return await provider.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        provider_name, model = _resolve_model(TASK_EMBEDDING)
        provider = self._embedding_providers.get(provider_name)
        if not provider:
            raise ValueError(
                f"No embedding provider registered for '{provider_name}'"
            )
        if hasattr(provider, "model"):
            provider.model = model  # type: ignore[attr-defined]
        return await provider.embed_batch(texts)
