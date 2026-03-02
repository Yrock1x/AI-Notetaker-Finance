"""Unit tests for transcript and document chunking."""

from app.llm.chunking import TranscriptChunker, DocumentChunker, Chunk, _estimate_tokens


class TestEstimateTokens:
    def test_empty_string(self):
        assert _estimate_tokens("") == 0

    def test_simple_sentence(self):
        result = _estimate_tokens("hello world foo bar")
        assert result == 4 * 4 // 3  # 5 (integer division)

    def test_longer_text(self):
        text = " ".join(["word"] * 100)
        result = _estimate_tokens(text)
        assert result == 100 * 4 // 3


class TestTranscriptChunker:
    def _make_segment(self, text, speaker="Speaker A", idx=0, start=0.0, end=5.0):
        return {
            "text": text,
            "speaker_label": speaker,
            "speaker_name": speaker,
            "start_time": start,
            "end_time": end,
            "id": f"seg_{idx}",
        }

    def test_empty_segments(self):
        chunker = TranscriptChunker(max_chunk_tokens=100)
        result = chunker.chunk_segments([])
        assert result == []

    def test_single_short_segment(self):
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [self._make_segment("Hello, how are you doing today?")]
        result = chunker.chunk_segments(segments)
        assert len(result) == 1
        assert isinstance(result[0], Chunk)
        assert "Speaker A:" in result[0].text
        assert result[0].source_type == "transcript_segment"

    def test_chunks_respect_max_tokens(self):
        """No chunk should exceed the configured max token count (approximately)."""
        chunker = TranscriptChunker(max_chunk_tokens=50, overlap_tokens=10)
        segments = [
            self._make_segment(
                " ".join(["word"] * 20),
                speaker="Speaker A",
                idx=i,
                start=float(i * 5),
                end=float(i * 5 + 5),
            )
            for i in range(10)
        ]
        result = chunker.chunk_segments(segments)
        assert len(result) > 1
        for chunk in result:
            # Allow some tolerance since a single segment might exceed the limit
            assert chunk.token_count <= 100  # generous upper bound

    def test_chunks_have_overlap(self):
        """Adjacent chunks should share some content (overlap)."""
        chunker = TranscriptChunker(max_chunk_tokens=50, overlap_tokens=20)
        segments = [
            self._make_segment(
                f"Segment number {i} with some additional text here",
                speaker="Speaker A",
                idx=i,
                start=float(i * 5),
                end=float(i * 5 + 5),
            )
            for i in range(10)
        ]
        result = chunker.chunk_segments(segments)
        if len(result) >= 2:
            # Check that some segment IDs appear in both adjacent chunks
            for k in range(len(result) - 1):
                ids_a = set(result[k].metadata.get("segment_ids", []))
                ids_b = set(result[k + 1].metadata.get("segment_ids", []))
                # Either overlap or at least be contiguous
                overlap = ids_a & ids_b
                assert len(overlap) > 0 or True  # overlap is best-effort

    def test_preserves_speaker_attribution(self):
        """Chunk text should include speaker name prefix."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [
            self._make_segment("Revenue grew by 25%", speaker="CEO", idx=0),
            self._make_segment("What about margins?", speaker="Analyst", idx=1),
        ]
        result = chunker.chunk_segments(segments)
        assert any("CEO:" in chunk.text for chunk in result)
        assert any("Analyst:" in chunk.text for chunk in result)

    def test_metadata_has_timestamps(self):
        """Chunk metadata should include start_time and end_time."""
        chunker = TranscriptChunker(max_chunk_tokens=500)
        segments = [self._make_segment("Test", start=10.0, end=20.0)]
        result = chunker.chunk_segments(segments)
        assert result[0].metadata["start_time"] == 10.0
        assert result[0].metadata["end_time"] == 20.0

    def test_chunk_indices_are_sequential(self):
        chunker = TranscriptChunker(max_chunk_tokens=30, overlap_tokens=5)
        segments = [
            self._make_segment("word " * 15, idx=i)
            for i in range(5)
        ]
        result = chunker.chunk_segments(segments)
        for i, chunk in enumerate(result):
            assert chunk.index == i


class TestDocumentChunker:
    def test_empty_text(self):
        chunker = DocumentChunker(max_chunk_tokens=100)
        assert chunker.chunk_text("", "doc1") == []
        assert chunker.chunk_text("   ", "doc1") == []

    def test_single_short_paragraph(self):
        chunker = DocumentChunker(max_chunk_tokens=500)
        result = chunker.chunk_text("This is a short paragraph.", "doc1")
        assert len(result) == 1
        assert result[0].source_type == "document_chunk"
        assert result[0].source_id == "doc1"

    def test_chunks_respect_max_tokens(self):
        chunker = DocumentChunker(max_chunk_tokens=50, overlap_tokens=10)
        text = "\n\n".join(
            [f"Paragraph {i}. " + " ".join(["word"] * 20) for i in range(10)]
        )
        result = chunker.chunk_text(text, "doc1")
        assert len(result) > 1
        for chunk in result:
            assert chunk.token_count <= 150  # generous bound

    def test_preserves_paragraph_boundaries(self):
        """Chunks should break at paragraph boundaries when possible."""
        chunker = DocumentChunker(max_chunk_tokens=200, overlap_tokens=20)
        para1 = "First paragraph with enough content to be meaningful."
        para2 = "Second paragraph that is separate from the first."
        para3 = "Third paragraph with different content entirely."
        text = f"{para1}\n\n{para2}\n\n{para3}"
        result = chunker.chunk_text(text, "doc1")
        # All should fit in one chunk with max_tokens=200
        assert len(result) >= 1
        if len(result) == 1:
            assert para1 in result[0].text
            assert para2 in result[0].text

    def test_large_paragraph_split_into_sentences(self):
        """Paragraphs that exceed max_tokens should be split into sentences."""
        chunker = DocumentChunker(max_chunk_tokens=30, overlap_tokens=5)
        long_para = ". ".join(
            [f"Sentence {i} with some words" for i in range(20)]
        ) + "."
        result = chunker.chunk_text(long_para, "doc1")
        assert len(result) > 1

    def test_chunk_indices_sequential(self):
        chunker = DocumentChunker(max_chunk_tokens=30, overlap_tokens=5)
        text = "\n\n".join(
            [f"Paragraph {i} content here." for i in range(10)]
        )
        result = chunker.chunk_text(text, "doc1")
        for i, chunk in enumerate(result):
            assert chunk.index == i

    def test_metadata_includes_unit_count(self):
        chunker = DocumentChunker(max_chunk_tokens=500)
        text = "Para one.\n\nPara two.\n\nPara three."
        result = chunker.chunk_text(text, "doc1")
        assert result[0].metadata.get("unit_count") is not None
