from typing import AsyncIterator

import anthropic
import structlog

from app.llm.provider import LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)


class ClaudeProvider(LLMProvider):
    """LLM provider backed by Anthropic Claude models."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.api_key = api_key
        self.model = model
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        """Send system + user prompt to Claude and return an LLMResponse.

        Kwargs:
            max_tokens: Maximum tokens to generate (default 4096).
            temperature: Sampling temperature (default 0.0 for deterministic financial analysis).
        """
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.0)

        log = logger.bind(model=self.model, max_tokens=max_tokens, temperature=temperature)
        log.info("claude_complete_start")

        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                **kwargs,
            )

            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

            log.info("claude_complete_success", usage=usage)

            return LLMResponse(
                content=content,
                model=response.model,
                usage=usage,
                raw_response=response.model_dump(),
            )

        except anthropic.AuthenticationError as exc:
            log.error("claude_auth_error", error=str(exc))
            raise
        except anthropic.RateLimitError as exc:
            log.warning("claude_rate_limit", error=str(exc))
            raise
        except anthropic.APIError as exc:
            log.error("claude_api_error", status_code=exc.status_code, error=str(exc))
            raise
        except Exception as exc:
            log.error("claude_unexpected_error", error=str(exc), error_type=type(exc).__name__)
            raise

    async def stream(self, system_prompt: str, user_prompt: str, **kwargs) -> AsyncIterator[str]:
        """Stream Claude responses as an async iterator of text chunks.

        Kwargs:
            max_tokens: Maximum tokens to generate (default 4096).
            temperature: Sampling temperature (default 0.0 for deterministic financial analysis).
        """
        max_tokens = kwargs.pop("max_tokens", 4096)
        temperature = kwargs.pop("temperature", 0.0)

        log = logger.bind(model=self.model, max_tokens=max_tokens, temperature=temperature)
        log.info("claude_stream_start")

        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                **kwargs,
            ) as stream:
                async for text in stream.text_stream:
                    yield text

            log.info("claude_stream_complete")

        except anthropic.AuthenticationError as exc:
            log.error("claude_auth_error", error=str(exc))
            raise
        except anthropic.RateLimitError as exc:
            log.warning("claude_rate_limit", error=str(exc))
            raise
        except anthropic.APIError as exc:
            log.error("claude_api_error", status_code=exc.status_code, error=str(exc))
            raise
        except Exception as exc:
            log.error("claude_stream_unexpected_error", error=str(exc), error_type=type(exc).__name__)
            raise
