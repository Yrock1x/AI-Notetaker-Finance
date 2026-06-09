from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)
    raw_response: dict | None = None


@dataclass
class EmbeddingResponse:
    embeddings: list[list[float]]
    model: str
    usage: dict = field(default_factory=dict)


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        ...

    # Plain ``def`` returning an AsyncIterator (not ``async def``):
    # implementations are async generators (``async def`` + ``yield``), whose
    # inferred type is AsyncIterator[str]. Annotating this as ``async def``
    # would make mypy expect a coroutine and flag every override.
    @abstractmethod
    def stream(self, system_prompt: str, user_prompt: str, **kwargs) -> AsyncIterator[str]:
        ...


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...
