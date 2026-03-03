from app.llm.provider import EmbeddingProvider, LLMProvider, LLMResponse


class LLMRouter:
    """Routes LLM requests to the appropriate provider based on task type.

    Task routing:
    - analysis -> Gemini (deep financial analysis)
    - qa -> Gemini (deal-scoped Q&A)
    - summarization -> Gemini
    - embeddings -> Gemini
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProvider] = {}
        self._embedding_provider: EmbeddingProvider | None = None
        self._task_routing: dict[str, str] = {
            "analysis": "gemini",
            "qa": "gemini",
            "summarization": "gemini",
            "general": "gemini",
        }

    def register_provider(self, name: str, provider: LLMProvider) -> None:
        self._providers[name] = provider

    def register_embedding_provider(self, provider: EmbeddingProvider) -> None:
        self._embedding_provider = provider

    async def complete(
        self, task_type: str, system_prompt: str,
        user_prompt: str, **kwargs,
    ) -> LLMResponse:
        provider_name = self._task_routing.get(task_type, "gemini")
        provider = self._providers.get(provider_name)
        if not provider:
            raise ValueError(f"No provider registered for '{provider_name}'")
        return await provider.complete(system_prompt, user_prompt, **kwargs)

    async def embed(self, text: str) -> list[float]:
        if not self._embedding_provider:
            raise ValueError("No embedding provider registered")
        return await self._embedding_provider.embed(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not self._embedding_provider:
            raise ValueError("No embedding provider registered")
        return await self._embedding_provider.embed_batch(texts)
