import asyncio
from typing import AsyncIterator

import google.generativeai as genai
import structlog

from app.llm.provider import EmbeddingProvider, LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider backed by Google Gemini models."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self.model = model
        genai.configure(api_key=api_key)

    async def complete(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> LLMResponse:
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.0)

        log = logger.bind(model=self.model, max_tokens=max_tokens)
        log.info("gemini_complete_start")

        try:
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            model = genai.GenerativeModel(
                self.model,
                system_instruction=system_prompt,
            )

            response = await model.generate_content_async(
                user_prompt,
                generation_config=generation_config,
            )

            content = response.text

            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                    "completion_tokens": getattr(
                        response.usage_metadata, "candidates_token_count", 0
                    ),
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
                }

            log.info("gemini_complete_success", usage=usage)

            return LLMResponse(
                content=content,
                model=self.model,
                usage=usage,
                raw_response=None,
            )

        except Exception as exc:
            log.error("gemini_complete_error", error=str(exc), error_type=type(exc).__name__)
            raise

    async def stream(
        self, system_prompt: str, user_prompt: str, **kwargs
    ) -> AsyncIterator[str]:
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.0)

        log = logger.bind(model=self.model)
        log.info("gemini_stream_start")

        try:
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            )

            model = genai.GenerativeModel(
                self.model,
                system_instruction=system_prompt,
            )

            response = await model.generate_content_async(
                user_prompt,
                generation_config=generation_config,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text

            log.info("gemini_stream_complete")

        except Exception as exc:
            log.error("gemini_stream_error", error=str(exc), error_type=type(exc).__name__)
            raise


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Embedding provider backed by Google Gemini embedding models."""

    MAX_BATCH_SIZE = 100

    def __init__(self, api_key: str, model: str = "models/gemini-embedding-001") -> None:
        self.model = model
        self._api_key = api_key
        genai.configure(api_key=api_key)

    async def embed(self, text: str) -> list[float]:
        log = logger.bind(model=self.model, text_length=len(text))
        log.info("gemini_embed_start")

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: genai.embed_content(
                    model=self.model,
                    content=text,
                    task_type="retrieval_document",
                    output_dimensionality=1536,
                ),
            )

            embedding = result["embedding"]
            log.info("gemini_embed_success", dimensions=len(embedding))
            return embedding

        except Exception as exc:
            log.error("gemini_embed_error", error=str(exc), error_type=type(exc).__name__)
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        log = logger.bind(model=self.model, total_texts=len(texts))
        log.info("gemini_embed_batch_start")

        all_embeddings: list[list[float]] = []

        try:
            loop = asyncio.get_event_loop()

            for batch_start in range(0, len(texts), self.MAX_BATCH_SIZE):
                batch = texts[batch_start : batch_start + self.MAX_BATCH_SIZE]

                result = await loop.run_in_executor(
                    None,
                    lambda b=batch: genai.embed_content(
                        model=self.model,
                        content=b,
                        task_type="retrieval_document",
                        output_dimensionality=1536,
                    ),
                )

                batch_embeddings = result["embedding"]
                all_embeddings.extend(batch_embeddings)

            log.info("gemini_embed_batch_success", total_embeddings=len(all_embeddings))
            return all_embeddings

        except Exception as exc:
            log.error("gemini_embed_batch_error", error=str(exc), error_type=type(exc).__name__)
            raise
