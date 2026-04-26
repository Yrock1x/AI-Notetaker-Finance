"""Fireworks AI provider — OpenAI-compatible chat completions + embeddings.

Fireworks hosts open-source models (Llama 3.3 70B, DeepSeek V3, Qwen, etc.)
at a fraction of the cost of Claude/GPT, and their API is OpenAI-compatible
so we can call it with any OpenAI-shaped client or httpx directly.

Docs: https://docs.fireworks.ai/api-reference/
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.provider import EmbeddingProvider, LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"

# Module-level concurrency cap on outbound Fireworks calls. Without this, a
# burst of QA requests can hit Fireworks faster than its rate limiter
# allows, producing a stampede of 429s and amplifying the original spike.
# 20 is a sane default for a single worker process; multiplied across
# uvicorn workers (WEB_CONCURRENCY=4) we cap at ~80 in-flight, well under
# Fireworks' per-account RPM ceilings.
_FIREWORKS_SEMAPHORE = asyncio.Semaphore(20)


def _is_retryable_http(exc: BaseException) -> bool:
    """429s and 5xx are transient; everything else is the caller's problem.

    Network/timeout exceptions also retry.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        sc = exc.response.status_code
        return sc == 429 or sc >= 500
    return isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))


class FireworksProvider(LLMProvider):
    """Chat-completion provider backed by Fireworks-hosted OSS models.

    ``model`` is the full Fireworks model slug, e.g.
    ``accounts/fireworks/models/llama-v3p3-70b-instruct``.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "accounts/fireworks/models/llama-v3p3-70b-instruct",
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._timeout = timeout

    async def complete(
        self, system_prompt: str, user_prompt: str, **kwargs: Any
    ) -> LLMResponse:
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.2)

        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        log = logger.bind(provider="fireworks", model=self.model, max_tokens=max_tokens)
        log.info("fireworks_complete_start")

        # Concurrency cap held across the *entire* retry sequence, not per
        # attempt — otherwise a burst can effectively double the in-flight
        # ceiling during retries.
        async with _FIREWORKS_SEMAPHORE:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=1, max=8),
                    retry=retry_if_exception(_is_retryable_http),
                    reraise=True,
                ):
                    with attempt:
                        async with httpx.AsyncClient(timeout=self._timeout) as client:
                            resp = await client.post(
                                f"{FIREWORKS_BASE_URL}/chat/completions",
                                headers={
                                    "Authorization": f"Bearer {self.api_key}",
                                    "Content-Type": "application/json",
                                },
                                json=body,
                            )
                            resp.raise_for_status()
                            data = resp.json()
            except RetryError as exc:
                # Should not happen with reraise=True, but guard anyway.
                log.error("fireworks_complete_retry_exhausted", error=str(exc))
                raise
            except httpx.HTTPStatusError as exc:
                log.error(
                    "fireworks_complete_http_error",
                    status=exc.response.status_code,
                    body=exc.response.text[:500],
                )
                raise
            except httpx.HTTPError as exc:
                log.error("fireworks_complete_network_error", error=str(exc))
                raise

        choice = (data.get("choices") or [{}])[0]
        content = (choice.get("message") or {}).get("content", "")
        usage = data.get("usage") or {}

        log.info("fireworks_complete_success", usage=usage)
        return LLMResponse(
            content=content,
            model=self.model,
            usage={
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
            },
            raw_response=data,
        )

    async def stream(
        self, system_prompt: str, user_prompt: str, **kwargs: Any
    ) -> AsyncIterator[str]:
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.2)

        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        log = logger.bind(provider="fireworks", model=self.model)
        log.info("fireworks_stream_start")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                f"{FIREWORKS_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    payload = line[len("data: ") :].strip()
                    if payload == "[DONE]":
                        break
                    try:
                        import json as _json

                        chunk = _json.loads(payload)
                    except ValueError:
                        continue
                    choice = (chunk.get("choices") or [{}])[0]
                    delta = (choice.get("delta") or {}).get("content")
                    if delta:
                        yield delta

        log.info("fireworks_stream_complete")


class FireworksEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Fireworks-hosted embedding models.

    Default model is nomic-embed-text-v1.5 (768 dims) — matches the pgvector
    column in the schema migration.
    """

    MAX_BATCH_SIZE = 64

    def __init__(
        self,
        api_key: str,
        model: str = "nomic-ai/nomic-embed-text-v1.5",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self._timeout = timeout

    async def embed(self, text: str) -> list[float]:
        batch = await self.embed_batch([text])
        return batch[0] if batch else []

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        log = logger.bind(provider="fireworks", model=self.model, n=len(texts))
        log.info("fireworks_embed_batch_start")

        all_vectors: list[list[float]] = []
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for start in range(0, len(texts), self.MAX_BATCH_SIZE):
                batch = texts[start : start + self.MAX_BATCH_SIZE]
                resp = await client.post(
                    f"{FIREWORKS_BASE_URL}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": batch},
                )
                resp.raise_for_status()
                data = resp.json()
                for row in data.get("data", []):
                    all_vectors.append(row["embedding"])

        log.info("fireworks_embed_batch_success", total=len(all_vectors))
        return all_vectors
