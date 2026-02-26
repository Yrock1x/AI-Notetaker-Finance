from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator


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

    @abstractmethod
    async def stream(self, system_prompt: str, user_prompt: str, **kwargs) -> AsyncIterator[str]:
        ...


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...
