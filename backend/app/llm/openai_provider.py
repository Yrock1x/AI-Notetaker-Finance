from typing import AsyncIterator

import openai
import structlog

from app.llm.provider import EmbeddingProvider, LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """LLM provider backed by OpenAI models."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        self.api_key = api_key
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """Send system + user prompt to OpenAI and return an LLMResponse.

        Kwargs:
            max_tokens: Maximum tokens to generate (default 4096).
            temperature: Sampling temperature (default 0.0 for deterministic financial analysis).
        """
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.0)

        log = logger.bind(model=self.model, max_tokens=max_tokens, temperature=temperature)
        log.info("openai_complete_start")

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                **kwargs,
            )

            content = response.choices[0].message.content or ""

            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }

            log.info("openai_complete_success", usage=usage)

            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                raw_response=response.model_dump(),
            )

        except openai.AuthenticationError as exc:
            log.error("openai_auth_error", error=str(exc))
            raise
        except openai.RateLimitError as exc:
            log.warning("openai_rate_limit", error=str(exc))
            raise
        except openai.APIError as exc:
            log.error("openai_api_error", error=str(exc))
            raise
        except Exception as exc:
            log.error("openai_unexpected_error", error=str(exc), error_type=type(exc).__name__)
            raise

    async def stream(self, system_prompt: str, user_prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream OpenAI responses as an async iterator of text chunks.

        Kwargs:
            max_tokens: Maximum tokens to generate (default 4096).
            temperature: Sampling temperature (default 0.0 for deterministic financial analysis).
        """
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.0)

        log = logger.bind(model=self.model, max_tokens=max_tokens, temperature=temperature)
        log.info("openai_stream_start")

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
                **kwargs,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

            log.info("openai_stream_complete")

        except openai.AuthenticationError as exc:
            log.error("openai_auth_error", error=str(exc))
            raise
        except openai.RateLimitError as exc:
            log.warning("openai_rate_limit", error=str(exc))
            raise
        except openai.APIError as exc:
            log.error("openai_api_error", error=str(exc))
            raise
        except Exception as exc:
            log.error("openai_stream_unexpected_error", error=str(exc), error_type=type(exc).__name__)
            raise


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by OpenAI embedding models."""

    MAX_BATCH_SIZE = 2048  # Maximum texts per API call

    def __init__(self, api_key: str, model: str = "text-embedding-3-small") -> None:
        self.api_key = api_key
        self.model = model
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        """Embed a single text and return the embedding vector."""
        log = logger.bind(model=self.model, text_length=len(text))
        log.info("openai_embed_start")

        try:
            response = await self._client.embeddings.create(
                model=self.model,
                input=text,
            )

            embedding = response.data[0].embedding
            log.info("openai_embed_success", dimensions=len(embedding))
            return embedding

        except openai.AuthenticationError as exc:
            log.error("openai_embed_auth_error", error=str(exc))
            raise
        except openai.RateLimitError as exc:
            log.warning("openai_embed_rate_limit", error=str(exc))
            raise
        except openai.APIError as exc:
            log.error("openai_embed_api_error", error=str(exc))
            raise
        except Exception as exc:
            log.error("openai_embed_unexpected_error", error=str(exc), error_type=type(exc).__name__)
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently, handling rate limits with batching.

        Splits the input into batches of MAX_BATCH_SIZE to respect API limits.
        Returns embeddings in the same order as the input texts.
        """
        if not texts:
            return []

        log = logger.bind(model=self.model, total_texts=len(texts))
        log.info("openai_embed_batch_start")

        all_embeddings: list[list[float]] = []

        try:
            for batch_start in range(0, len(texts), self.MAX_BATCH_SIZE):
                batch = texts[batch_start : batch_start + self.MAX_BATCH_SIZE]
                batch_num = batch_start // self.MAX_BATCH_SIZE + 1

                log.info(
                    "openai_embed_batch_processing",
                    batch_num=batch_num,
                    batch_size=len(batch),
                )

                response = await self._client.embeddings.create(
                    model=self.model,
                    input=batch,
                )

                # Sort by index to guarantee order matches input order
                sorted_data = sorted(response.data, key=lambda x: x.index)
                batch_embeddings = [item.embedding for item in sorted_data]
                all_embeddings.extend(batch_embeddings)

            log.info("openai_embed_batch_success", total_embeddings=len(all_embeddings))
            return all_embeddings

        except openai.AuthenticationError as exc:
            log.error("openai_embed_batch_auth_error", error=str(exc))
            raise
        except openai.RateLimitError as exc:
            log.warning("openai_embed_batch_rate_limit", error=str(exc))
            raise
        except openai.APIError as exc:
            log.error("openai_embed_batch_api_error", error=str(exc))
            raise
        except Exception as exc:
            log.error("openai_embed_batch_unexpected_error", error=str(exc), error_type=type(exc).__name__)
            raise
