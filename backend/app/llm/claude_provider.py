from collections.abc import AsyncIterator

import anthropic
import structlog

from app.llm.provider import LLMProvider, LLMResponse

logger = structlog.get_logger(__name__)

# Opus 4.7+ removed the sampling parameters (temperature / top_p / top_k):
# sending any of them returns HTTP 400. Strip temperature for those models so a
# premium-task override to an Opus model doesn't hard-fail. (Sonnet 4.6 still
# accepts temperature.) See the claude-api skill.
_NO_SAMPLING_PREFIXES = ("claude-opus-4-7", "claude-opus-4-8")


def _accepts_temperature(model: str) -> bool:
    return not model.startswith(_NO_SAMPLING_PREFIXES)


class ClaudeProvider(LLMProvider):
    """LLM provider backed by Anthropic Claude models."""

    # claude-sonnet-4-20250514 (Sonnet 4) is deprecated; claude-sonnet-4-6 is
    # the current drop-in. Override per task via LLM_MODEL_FOR_<TASK>.
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6") -> None:
        self.model = model
        # Anthropic SDK has built-in retry on 429/5xx with exponential backoff;
        # set the values explicitly so they don't drift on SDK upgrades. 3
        # retries matches the Fireworks provider; a 5-min request timeout
        # bounds tail latency well under typical Inngest step timeouts.
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key,
            max_retries=3,
            timeout=300.0,
        )

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

        sampling: dict = (
            {"temperature": temperature} if _accepts_temperature(self.model) else {}
        )
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                **sampling,
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
            log.error(
                "claude_api_error",
                status_code=getattr(exc, "status_code", None),
                error=str(exc),
            )
            raise
        except Exception as exc:
            log.error(
                "claude_unexpected_error", error=str(exc), error_type=type(exc).__name__
            )
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

        sampling: dict = (
            {"temperature": temperature} if _accepts_temperature(self.model) else {}
        )
        try:
            async with self._client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                **sampling,
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
            log.error(
                "claude_api_error",
                status_code=getattr(exc, "status_code", None),
                error=str(exc),
            )
            raise
        except Exception as exc:
            log.error(
                "claude_stream_unexpected_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
