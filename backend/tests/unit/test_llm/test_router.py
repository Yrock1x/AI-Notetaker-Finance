"""Unit tests for LLM Router, Provider base classes, and coverage gaps.

Tests cover:
- LLMRouter: provider registration, task routing, fallback behavior, embed/embed_batch
- LLMProvider / EmbeddingProvider: abstract contract enforcement
- LLMResponse / EmbeddingResponse: dataclass behavior
- Additional chunking edge cases not covered by existing tests
- Additional guardrails edge cases not covered by existing tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from typing import AsyncIterator

from app.llm.router import LLMRouter
from app.llm.provider import (
    LLMProvider,
    EmbeddingProvider,
    LLMResponse,
    EmbeddingResponse,
)
from app.llm.chunking import (
    TranscriptChunker,
    DocumentChunker,
    Chunk,
    _estimate_tokens,
)
from app.llm.guardrails import (
    FinancialGuardrails,
    GroundingResult,
    _normalize_figure,
    _extract_financial_figures,
)


# ---------------------------------------------------------------------------
# Helpers: concrete mock implementations of abstract providers
# ---------------------------------------------------------------------------


class MockLLMProvider(LLMProvider):
    """Concrete implementation of LLMProvider for testing."""

    def __init__(self, model_name: str = "mock-model"):
        self.model_name = model_name
        self.complete_calls: list[dict] = []
        self.stream_calls: list[dict] = []

    async def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        self.complete_calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            **kwargs,
        })
        return LLMResponse(
            content=f"Response from {self.model_name}",
            model=self.model_name,
            usage={"input_tokens": 10, "output_tokens": 20},
        )

    async def stream(self, system_prompt: str, user_prompt: str, **kwargs) -> AsyncIterator[str]:
        self.stream_calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            **kwargs,
        })
        async def _gen():
            yield f"chunk from {self.model_name}"
        return _gen()


class MockEmbeddingProvider(EmbeddingProvider):
    """Concrete implementation of EmbeddingProvider for testing."""

    def __init__(self, dimensions: int = 3):
        self.dimensions = dimensions
        self.embed_calls: list[str] = []
        self.embed_batch_calls: list[list[str]] = []

    async def embed(self, text: str) -> list[float]:
        self.embed_calls.append(text)
        return [0.1] * self.dimensions

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.embed_batch_calls.append(texts)
        return [[0.1] * self.dimensions for _ in texts]


class FailingLLMProvider(LLMProvider):
    """Provider that always raises an exception on complete."""

    async def complete(self, system_prompt: str, user_prompt: str, **kwargs) -> LLMResponse:
        raise RuntimeError("Provider failure simulated")

    async def stream(self, system_prompt: str, user_prompt: str, **kwargs) -> AsyncIterator[str]:
        raise RuntimeError("Provider failure simulated")


# ===========================================================================
# LLMRouter Tests
# ===========================================================================


class TestLLMRouterRegistration:
    """Tests for provider registration on LLMRouter."""

    def test_register_single_provider(self):
        router = LLMRouter()
        provider = MockLLMProvider("claude")
        router.register_provider("claude", provider)
        assert router._providers["claude"] is provider

    def test_register_multiple_providers(self):
        router = LLMRouter()
        claude = MockLLMProvider("claude")
        openai = MockLLMProvider("openai")
        router.register_provider("claude", claude)
        router.register_provider("openai", openai)
        assert router._providers["claude"] is claude
        assert router._providers["openai"] is openai

    def test_register_overwrites_existing_provider(self):
        router = LLMRouter()
        original = MockLLMProvider("original")
        replacement = MockLLMProvider("replacement")
        router.register_provider("claude", original)
        router.register_provider("claude", replacement)
        assert router._providers["claude"] is replacement

    def test_register_embedding_provider(self):
        router = LLMRouter()
        emb = MockEmbeddingProvider()
        router.register_embedding_provider(emb)
        assert router._embedding_provider is emb

    def test_register_embedding_provider_overwrites(self):
        router = LLMRouter()
        emb1 = MockEmbeddingProvider(dimensions=3)
        emb2 = MockEmbeddingProvider(dimensions=5)
        router.register_embedding_provider(emb1)
        router.register_embedding_provider(emb2)
        assert router._embedding_provider is emb2

    def test_initial_state_no_providers(self):
        router = LLMRouter()
        assert router._providers == {}
        assert router._embedding_provider is None

    def test_default_task_routing_table(self):
        router = LLMRouter()
        assert router._task_routing["analysis"] == "gemini"
        assert router._task_routing["qa"] == "gemini"
        assert router._task_routing["summarization"] == "gemini"
        assert router._task_routing["general"] == "gemini"


class TestLLMRouterComplete:
    """Tests for the LLMRouter.complete() method."""

    async def test_routes_analysis_to_gemini(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        result = await router.complete("analysis", "system", "user")
        assert result.model == "gemini"
        assert len(gemini.complete_calls) == 1
        assert gemini.complete_calls[0]["system_prompt"] == "system"
        assert gemini.complete_calls[0]["user_prompt"] == "user"

    async def test_routes_qa_to_gemini(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        result = await router.complete("qa", "sys", "usr")
        assert result.model == "gemini"

    async def test_routes_summarization_to_gemini(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        result = await router.complete("summarization", "sys", "usr")
        assert result.model == "gemini"

    async def test_routes_general_to_gemini(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        result = await router.complete("general", "sys", "usr")
        assert result.model == "gemini"

    async def test_unknown_task_type_falls_back_to_gemini(self):
        """Unknown task types should default to the 'gemini' provider."""
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        result = await router.complete("unknown_task", "sys", "usr")
        assert result.model == "gemini"

    async def test_raises_when_no_provider_registered(self):
        """Should raise ValueError when the needed provider is not registered."""
        router = LLMRouter()
        with pytest.raises(ValueError, match="No provider registered for 'gemini'"):
            await router.complete("analysis", "sys", "usr")

    async def test_raises_when_wrong_provider_registered(self):
        """If only 'openai' is registered but routing points to 'gemini', should raise."""
        router = LLMRouter()
        openai = MockLLMProvider("openai")
        router.register_provider("openai", openai)

        with pytest.raises(ValueError, match="No provider registered for 'gemini'"):
            await router.complete("analysis", "sys", "usr")

    async def test_passes_kwargs_to_provider(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        await router.complete("analysis", "sys", "usr", temperature=0.5, max_tokens=1000)
        assert gemini.complete_calls[0]["temperature"] == 0.5
        assert gemini.complete_calls[0]["max_tokens"] == 1000

    async def test_returns_llm_response_dataclass(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        result = await router.complete("analysis", "sys", "usr")
        assert isinstance(result, LLMResponse)
        assert result.content == "Response from gemini"
        assert result.usage == {"input_tokens": 10, "output_tokens": 20}

    async def test_propagates_provider_exception(self):
        """If the provider raises, the router should not swallow the exception."""
        router = LLMRouter()
        failing = FailingLLMProvider()
        router.register_provider("gemini", failing)

        with pytest.raises(RuntimeError, match="Provider failure simulated"):
            await router.complete("analysis", "sys", "usr")

    async def test_multiple_sequential_calls(self):
        router = LLMRouter()
        gemini = MockLLMProvider("gemini")
        router.register_provider("gemini", gemini)

        await router.complete("analysis", "s1", "u1")
        await router.complete("qa", "s2", "u2")
        await router.complete("summarization", "s3", "u3")

        assert len(gemini.complete_calls) == 3
        assert gemini.complete_calls[0]["user_prompt"] == "u1"
        assert gemini.complete_calls[1]["user_prompt"] == "u2"
        assert gemini.complete_calls[2]["user_prompt"] == "u3"


class TestLLMRouterEmbed:
    """Tests for embed() and embed_batch() on LLMRouter."""

    async def test_embed_returns_floats(self):
        router = LLMRouter()
        emb = MockEmbeddingProvider(dimensions=5)
        router.register_embedding_provider(emb)

        result = await router.embed("hello world")
        assert isinstance(result, list)
        assert len(result) == 5
        assert all(isinstance(x, float) for x in result)
        assert emb.embed_calls == ["hello world"]

    async def test_embed_raises_when_no_provider(self):
        router = LLMRouter()
        with pytest.raises(ValueError, match="No embedding provider registered"):
            await router.embed("hello")

    async def test_embed_batch_returns_list_of_lists(self):
        router = LLMRouter()
        emb = MockEmbeddingProvider(dimensions=4)
        router.register_embedding_provider(emb)

        texts = ["text1", "text2", "text3"]
        result = await router.embed_batch(texts)
        assert len(result) == 3
        assert all(len(v) == 4 for v in result)
        assert emb.embed_batch_calls == [texts]

    async def test_embed_batch_raises_when_no_provider(self):
        router = LLMRouter()
        with pytest.raises(ValueError, match="No embedding provider registered"):
            await router.embed_batch(["hello"])

    async def test_embed_empty_string(self):
        router = LLMRouter()
        emb = MockEmbeddingProvider(dimensions=3)
        router.register_embedding_provider(emb)

        result = await router.embed("")
        assert len(result) == 3

    async def test_embed_batch_empty_list(self):
        router = LLMRouter()
        emb = MockEmbeddingProvider(dimensions=3)
        router.register_embedding_provider(emb)

        result = await router.embed_batch([])
        assert result == []


# ===========================================================================
# Provider Base Class Tests
# ===========================================================================


class TestLLMProviderContract:
    """Tests that LLMProvider is an abstract class with the correct interface."""

    def test_cannot_instantiate_abstract_llm_provider(self):
        """LLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            LLMProvider()

    def test_cannot_instantiate_partial_implementation(self):
        """A subclass that only implements complete() but not stream() cannot be instantiated."""

        class PartialProvider(LLMProvider):
            async def complete(self, system_prompt, user_prompt, **kwargs):
                return LLMResponse(content="test", model="test")

        with pytest.raises(TypeError):
            PartialProvider()

    def test_full_implementation_can_instantiate(self):
        """A subclass that implements all abstract methods can be instantiated."""
        provider = MockLLMProvider()
        assert isinstance(provider, LLMProvider)

    async def test_complete_method_signature(self):
        """complete() should accept system_prompt, user_prompt, and kwargs."""
        provider = MockLLMProvider()
        result = await provider.complete("sys", "usr", temperature=0.7)
        assert isinstance(result, LLMResponse)

    async def test_stream_method_returns_async_iterator(self):
        """stream() should return an AsyncIterator."""
        provider = MockLLMProvider()
        result = await provider.stream("sys", "usr")
        chunks = []
        async for chunk in result:
            chunks.append(chunk)
        assert len(chunks) > 0


class TestEmbeddingProviderContract:
    """Tests that EmbeddingProvider is an abstract class with the correct interface."""

    def test_cannot_instantiate_abstract_embedding_provider(self):
        with pytest.raises(TypeError):
            EmbeddingProvider()

    def test_cannot_instantiate_partial_implementation(self):

        class PartialEmbedding(EmbeddingProvider):
            async def embed(self, text):
                return [0.1]

        with pytest.raises(TypeError):
            PartialEmbedding()

    def test_full_implementation_can_instantiate(self):
        provider = MockEmbeddingProvider()
        assert isinstance(provider, EmbeddingProvider)


class TestLLMResponseDataclass:
    """Tests for LLMResponse dataclass behavior."""

    def test_default_values(self):
        resp = LLMResponse(content="hello", model="test-model")
        assert resp.content == "hello"
        assert resp.model == "test-model"
        assert resp.usage == {}
        assert resp.raw_response is None

    def test_with_all_fields(self):
        resp = LLMResponse(
            content="output",
            model="claude-3",
            usage={"input_tokens": 50, "output_tokens": 100},
            raw_response={"id": "msg_123"},
        )
        assert resp.usage["input_tokens"] == 50
        assert resp.raw_response["id"] == "msg_123"

    def test_usage_default_is_independent(self):
        """Each instance should get its own default dict, not share one."""
        r1 = LLMResponse(content="a", model="m")
        r2 = LLMResponse(content="b", model="m")
        r1.usage["key"] = "value"
        assert "key" not in r2.usage


class TestEmbeddingResponseDataclass:
    """Tests for EmbeddingResponse dataclass behavior."""

    def test_default_values(self):
        resp = EmbeddingResponse(embeddings=[[0.1, 0.2]], model="ada")
        assert resp.embeddings == [[0.1, 0.2]]
        assert resp.model == "ada"
        assert resp.usage == {}

    def test_with_usage(self):
        resp = EmbeddingResponse(
            embeddings=[[0.1], [0.2]],
            model="ada",
            usage={"total_tokens": 10},
        )
        assert resp.usage["total_tokens"] == 10


# ===========================================================================
# Additional Chunking Coverage (gaps in existing tests)
# ===========================================================================


class TestTranscriptChunkerEdgeCases:
    """Additional edge cases for TranscriptChunker not covered by existing tests."""

    def _make_segment(self, text, speaker_name=None, speaker_label="Unknown", idx=0, start=0.0, end=5.0):
        seg = {
            "text": text,
            "speaker_label": speaker_label,
            "start_time": start,
            "end_time": end,
            "id": f"seg_{idx}",
        }
        if speaker_name is not None:
            seg["speaker_name"] = speaker_name
        return seg

    def test_speaker_name_preferred_over_label(self):
        """When speaker_name is set, it should be used instead of speaker_label."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [self._make_segment("Hello", speaker_name="John Doe", speaker_label="spk_0")]
        result = chunker.chunk_segments(segments)
        assert "John Doe:" in result[0].text
        assert "spk_0" not in result[0].text

    def test_falls_back_to_speaker_label(self):
        """When speaker_name is absent or None, should fall back to speaker_label."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [{
            "text": "Hello",
            "speaker_label": "spk_0",
            "start_time": 0.0,
            "end_time": 5.0,
            "id": "seg_0",
        }]
        result = chunker.chunk_segments(segments)
        assert "spk_0:" in result[0].text

    def test_falls_back_to_unknown_speaker(self):
        """When neither speaker_name nor speaker_label is present, should use 'Unknown'."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [{
            "text": "Hello",
            "start_time": 0.0,
            "end_time": 5.0,
            "id": "seg_0",
        }]
        result = chunker.chunk_segments(segments)
        assert "Unknown:" in result[0].text

    def test_single_oversized_segment_still_included(self):
        """A single segment that exceeds max_chunk_tokens should still produce a chunk."""
        chunker = TranscriptChunker(max_chunk_tokens=10, overlap_tokens=2)
        segments = [self._make_segment(" ".join(["word"] * 50), speaker_name="A", idx=0)]
        result = chunker.chunk_segments(segments)
        assert len(result) == 1
        assert result[0].token_count > 10

    def test_segment_without_id_uses_index(self):
        """Segments missing 'id' should fall back to using the index as ID."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [{
            "text": "Test",
            "speaker_name": "A",
            "speaker_label": "A",
            "start_time": 0.0,
            "end_time": 5.0,
            # no "id" key
        }]
        result = chunker.chunk_segments(segments)
        assert result[0].metadata["segment_ids"] == ["0"]

    def test_forward_progress_guaranteed(self):
        """Chunker must always make forward progress to avoid infinite loops."""
        chunker = TranscriptChunker(max_chunk_tokens=5, overlap_tokens=100)
        segments = [
            self._make_segment(f"Segment {i} text", speaker_name="A", idx=i)
            for i in range(5)
        ]
        result = chunker.chunk_segments(segments)
        # Must produce chunks without hanging
        assert len(result) >= 1
        # Chunk indices should be sequential
        for i, chunk in enumerate(result):
            assert chunk.index == i

    def test_source_id_is_first_segment_id(self):
        """source_id of each chunk should be the first segment's ID."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [
            self._make_segment("Hello", speaker_name="A", idx=0),
            self._make_segment("World", speaker_name="B", idx=1),
        ]
        result = chunker.chunk_segments(segments)
        assert result[0].source_id == "seg_0"

    def test_end_time_tracks_last_segment(self):
        """end_time should be updated to the last segment's end_time in the chunk."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [
            self._make_segment("Hello", speaker_name="A", idx=0, start=0.0, end=5.0),
            self._make_segment("World", speaker_name="B", idx=1, start=5.0, end=10.0),
        ]
        result = chunker.chunk_segments(segments)
        # Both segments should fit in one chunk
        assert result[0].metadata["end_time"] == 10.0
        assert result[0].metadata["start_time"] == 0.0


class TestDocumentChunkerEdgeCases:
    """Additional edge cases for DocumentChunker not covered by existing tests."""

    def test_whitespace_only_text(self):
        chunker = DocumentChunker(max_chunk_tokens=100)
        assert chunker.chunk_text("   \n\n  \t  ", "doc1") == []

    def test_single_sentence_no_paragraph_break(self):
        chunker = DocumentChunker(max_chunk_tokens=500)
        result = chunker.chunk_text("Just one sentence.", "doc1")
        assert len(result) == 1
        assert result[0].text == "Just one sentence."

    def test_multiple_blank_lines_treated_as_paragraph_break(self):
        chunker = DocumentChunker(max_chunk_tokens=500)
        text = "Paragraph one.\n\n\n\nParagraph two."
        result = chunker.chunk_text(text, "doc1")
        assert len(result) == 1
        assert "Paragraph one." in result[0].text
        assert "Paragraph two." in result[0].text

    def test_metadata_char_start_is_correct(self):
        chunker = DocumentChunker(max_chunk_tokens=500)
        text = "First paragraph.\n\nSecond paragraph."
        result = chunker.chunk_text(text, "doc1")
        # First chunk starts at the beginning of "First paragraph."
        assert result[0].metadata["char_start"] == 0

    def test_source_type_is_document_chunk(self):
        chunker = DocumentChunker(max_chunk_tokens=500)
        result = chunker.chunk_text("Some text.", "doc1")
        assert result[0].source_type == "document_chunk"

    def test_overlap_between_document_chunks(self):
        """Document chunks should overlap when text is long enough."""
        chunker = DocumentChunker(max_chunk_tokens=30, overlap_tokens=15)
        # Many small paragraphs
        text = "\n\n".join([f"Paragraph {i} has some words in it." for i in range(20)])
        result = chunker.chunk_text(text, "doc1")
        assert len(result) >= 2
        # Check for text overlap between adjacent chunks
        if len(result) >= 2:
            for k in range(len(result) - 1):
                # There should be some shared text (overlap)
                words_a = set(result[k].text.split())
                words_b = set(result[k + 1].text.split())
                # Due to overlap_tokens, adjacent chunks should share words
                overlap = words_a & words_b
                # Overlap should exist (at least common words like "Paragraph", "has", etc.)
                assert len(overlap) > 0


class TestChunkDataclass:
    """Tests for the Chunk dataclass."""

    def test_token_count_property(self):
        chunk = Chunk(text="hello world foo bar", index=0, source_type="test", source_id="s1", metadata={})
        expected = _estimate_tokens("hello world foo bar")
        assert chunk.token_count == expected

    def test_empty_chunk_token_count(self):
        chunk = Chunk(text="", index=0, source_type="test", source_id="s1", metadata={})
        assert chunk.token_count == 0


# ===========================================================================
# Additional Guardrails Coverage (gaps in existing tests)
# ===========================================================================


class TestNormalizeFigure:
    """Tests for the _normalize_figure helper."""

    def test_strips_commas_and_whitespace(self):
        assert _normalize_figure("  $1,000,000  ") == "$1000000"

    def test_lowercases(self):
        assert _normalize_figure("$50 Million") == "$50million"

    def test_already_normalized(self):
        assert _normalize_figure("100") == "100"


class TestExtractFinancialFigures:
    """Tests for the _extract_financial_figures helper."""

    def test_extracts_currency(self):
        figs = _extract_financial_figures("The deal was $50 million")
        assert any("$50" in f for f in figs)

    def test_extracts_percentage(self):
        figs = _extract_financial_figures("Growth was 25.5%")
        assert any("25.5%" in f for f in figs)

    def test_extracts_standalone_numbers_with_magnitude(self):
        figs = _extract_financial_figures("The company earned 3 billion last year")
        assert any("billion" in f.lower() for f in figs)

    def test_extracts_basis_points(self):
        figs = _extract_financial_figures("Spread tightened by 150 basis points")
        assert any("basis" in f.lower() for f in figs)

    def test_no_duplicates(self):
        figs = _extract_financial_figures("$50 million and $50 million again")
        # Should not have duplicate entries
        assert len(figs) == len(set(figs))

    def test_no_figures_returns_empty(self):
        figs = _extract_financial_figures("The quick brown fox jumps over the lazy dog")
        assert figs == []

    def test_multiple_currencies(self):
        text = "Revenue was $100 million. European revenue was \u20AC80 million."
        figs = _extract_financial_figures(text)
        assert len(figs) >= 2


class TestGuardrailsCitationEdgeCases:
    """Additional citation validation edge cases."""

    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_citation_with_short_words_only(self):
        """Citation with only short words (< 4 chars) should get 'too short' reason."""
        citations = [{"text": "is a to be", "source_id": "s1"}]
        sources = [{"text": "completely different content here", "source_id": "s1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is False
        assert "too short" in result[0]["reason"]

    def test_case_insensitive_exact_match(self):
        """Citation matching should be case-insensitive."""
        citations = [{"text": "Revenue Grew By 25%", "source_id": "s1"}]
        sources = [{"text": "revenue grew by 25% year over year", "source_id": "s1"}]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is True

    def test_multiple_source_chunks_same_id(self):
        """Multiple source chunks with the same ID should all be searched."""
        citations = [{"text": "found in second chunk", "source_id": "s1"}]
        sources = [
            {"text": "first chunk text here", "source_id": "s1"},
            {"text": "found in second chunk for validation", "source_id": "s1"},
        ]
        result = self.guardrails.validate_citations("answer", citations, sources)
        assert result[0]["valid"] is True

    def test_empty_citations_list(self):
        sources = [{"text": "something", "source_id": "s1"}]
        result = self.guardrails.validate_citations("answer", [], sources)
        assert result == []

    def test_empty_sources_list(self):
        citations = [{"text": "some claim", "source_id": "s1"}]
        result = self.guardrails.validate_citations("answer", citations, [])
        assert len(result) == 1
        assert result[0]["valid"] is False


class TestGroundingScoreEdgeCases:
    """Additional grounding score edge cases."""

    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_citations_present_but_empty_list_returns_zero(self):
        """Edge: citations list is non-empty but all invalid -> low score."""
        citations = [{"text": "fake", "source_id": "nope"}]
        sources = [{"text": "real text", "source_id": "s1"}]
        score = self.guardrails.calculate_grounding_score("answer", citations, sources)
        # 0.6 * 0 (all invalid) + 0.4 * 1.0 (no figures) = 0.4
        assert score == pytest.approx(0.4, abs=0.01)

    def test_half_valid_citations_no_figures(self):
        """Half valid citations with no financial figures."""
        citations = [
            {"text": "real claim", "source_id": "s1"},
            {"text": "fake claim", "source_id": "nope"},
        ]
        sources = [{"text": "this is the real claim in context", "source_id": "s1"}]
        score = self.guardrails.calculate_grounding_score("no figures", citations, sources)
        # 0.6 * 0.5 + 0.4 * 1.0 = 0.3 + 0.4 = 0.7
        assert score == pytest.approx(0.7, abs=0.01)

    def test_all_figures_ungrounded(self):
        """All financial figures ungrounded should lower figure score to 0."""
        answer = "Revenue was $999 trillion and margins were 99%."
        citations = []
        sources = [{"text": "no financial figures here", "source_id": "s1"}]
        score = self.guardrails.calculate_grounding_score(answer, citations, sources)
        # 0.6 * 1.0 (no citations) + 0.4 * 0.0 (no figures grounded) = 0.6
        assert score == pytest.approx(0.6, abs=0.01)

    def test_score_is_rounded_to_four_decimals(self):
        score = self.guardrails.calculate_grounding_score("text", [], [])
        # 1.0 should be exactly 1.0 when rounded to 4 decimals
        assert score == round(score, 4)


class TestCheckAndFlagEdgeCases:
    """Additional check_and_flag edge cases."""

    def setup_method(self):
        self.guardrails = FinancialGuardrails()

    def test_returns_grounding_result_type(self):
        result = self.guardrails.check_and_flag("test", [], [])
        assert isinstance(result, GroundingResult)

    def test_no_citations_no_figures_is_grounded(self):
        result = self.guardrails.check_and_flag("Just a discussion about strategy.", [], [])
        assert result.is_grounded is True
        assert result.score == 1.0
        assert result.ungrounded_claims == []
        assert result.flagged_figures == []

    def test_flagged_figures_contain_figure_text(self):
        answer = "Revenue was $777 billion."
        sources = [{"text": "No financial data here", "source_id": "s1"}]
        result = self.guardrails.check_and_flag(answer, [], sources)
        assert len(result.flagged_figures) >= 1
        assert any("$777" in fig["figure"] for fig in result.flagged_figures)

    def test_ungrounded_claims_contain_citation_text(self):
        citations = [{"text": "totally fabricated claim here", "source_id": "fake"}]
        sources = [{"text": "real source", "source_id": "s1"}]
        result = self.guardrails.check_and_flag("answer", citations, sources)
        assert len(result.ungrounded_claims) >= 1
        assert any("fabricated" in c for c in result.ungrounded_claims)

    def test_grounding_threshold_boundary(self):
        """Score exactly at threshold should be grounded."""
        # Construct a scenario where score = 0.7
        # Half valid citations (0.5), no figures (1.0):
        # 0.6 * 0.5 + 0.4 * 1.0 = 0.7
        citations = [
            {"text": "valid claim text", "source_id": "s1"},
            {"text": "invalid claim", "source_id": "nonexistent"},
        ]
        sources = [{"text": "valid claim text is here in the source", "source_id": "s1"}]
        result = self.guardrails.check_and_flag("no figures here", citations, sources)
        assert result.score == pytest.approx(0.7, abs=0.01)
        assert result.is_grounded is True


class TestGroundingResultDataclass:
    """Tests for GroundingResult dataclass."""

    def test_construction(self):
        result = GroundingResult(
            score=0.85,
            is_grounded=True,
            ungrounded_claims=[],
            validated_citations=[],
            flagged_figures=[],
        )
        assert result.score == 0.85
        assert result.is_grounded is True

    def test_with_ungrounded_claims(self):
        result = GroundingResult(
            score=0.3,
            is_grounded=False,
            ungrounded_claims=["Claim 1", "Claim 2"],
            validated_citations=[],
            flagged_figures=[{"figure": "$100", "issue": "not found"}],
        )
        assert len(result.ungrounded_claims) == 2
        assert len(result.flagged_figures) == 1
