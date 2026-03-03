"""Unit tests for the Deepgram DiarizationProcessor.

Tests cover response parsing, segment building, short-segment merging,
and participant extraction. No external dependencies are needed since
DiarizationProcessor is a pure data processor.
"""

import pytest

from app.integrations.deepgram.processor import DiarizationProcessor


@pytest.fixture
def processor() -> DiarizationProcessor:
    """Create a fresh DiarizationProcessor instance."""
    return DiarizationProcessor()


# ---------------------------------------------------------------------------
# Deepgram response helper
# ---------------------------------------------------------------------------


def _make_response(words: list[dict]) -> dict:
    """Wrap a list of word dicts into the nested Deepgram response structure."""
    return {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"words": words}
                    ]
                }
            ]
        }
    }


# ===========================================================================
# process_response
# ===========================================================================


class TestProcessResponse:
    """Tests for DiarizationProcessor.process_response."""

    def test_process_response_empty_words_returns_empty(
        self, processor: DiarizationProcessor
    ):
        """An empty words array should produce an empty segment list."""
        response = _make_response([])
        result = processor.process_response(response)
        assert result == []

    def test_process_response_single_speaker(
        self, processor: DiarizationProcessor
    ):
        """A sequence of words from a single speaker should produce one segment."""
        words = [
            {"word": "hello", "speaker": 0, "start": 0.0, "end": 0.5, "confidence": 0.95},
            {"word": "world", "speaker": 0, "start": 0.5, "end": 1.0, "confidence": 0.90},
        ]
        result = processor.process_response(_make_response(words))

        assert len(result) == 1
        assert result[0]["speaker_label"] == "Speaker 0"
        assert result[0]["text"] == "hello world"
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 1.0
        assert result[0]["segment_index"] == 0

    def test_process_response_multiple_speakers(
        self, processor: DiarizationProcessor
    ):
        """Words from multiple speakers should produce multiple segments."""
        words = [
            {"word": "hello", "speaker": 0, "start": 0.0, "end": 0.5, "confidence": 0.9},
            {"word": "hi", "speaker": 1, "start": 1.0, "end": 1.5, "confidence": 0.85},
            {"word": "thanks", "speaker": 2, "start": 2.0, "end": 2.5, "confidence": 0.92},
        ]
        result = processor.process_response(_make_response(words))

        assert len(result) == 3
        assert result[0]["speaker_label"] == "Speaker 0"
        assert result[1]["speaker_label"] == "Speaker 1"
        assert result[2]["speaker_label"] == "Speaker 2"

    def test_process_response_speaker_changes(
        self, processor: DiarizationProcessor
    ):
        """Speaker changes mid-conversation should split segments correctly."""
        words = [
            {"word": "I", "speaker": 0, "start": 0.0, "end": 0.2, "confidence": 0.95},
            {"word": "think", "speaker": 0, "start": 0.2, "end": 0.5, "confidence": 0.93},
            {"word": "agreed", "speaker": 1, "start": 1.0, "end": 1.3, "confidence": 0.90},
            {"word": "let's", "speaker": 0, "start": 2.0, "end": 2.3, "confidence": 0.88},
            {"word": "proceed", "speaker": 0, "start": 2.3, "end": 2.8, "confidence": 0.91},
        ]
        result = processor.process_response(_make_response(words))

        assert len(result) == 3
        assert result[0]["text"] == "I think"
        assert result[0]["speaker_label"] == "Speaker 0"
        assert result[1]["text"] == "agreed"
        assert result[1]["speaker_label"] == "Speaker 1"
        assert result[2]["text"] == "let's proceed"
        assert result[2]["speaker_label"] == "Speaker 0"
        # Verify sequential indexing
        assert [s["segment_index"] for s in result] == [0, 1, 2]


# ===========================================================================
# _build_segment
# ===========================================================================


class TestBuildSegment:
    """Tests for DiarizationProcessor._build_segment."""

    def test_build_segment_uses_punctuated_word(
        self, processor: DiarizationProcessor
    ):
        """When punctuated_word is available, it should be preferred over raw word."""
        words = [
            {
                "word": "hello",
                "punctuated_word": "Hello,",
                "speaker": 0,
                "start": 0.0,
                "end": 0.5,
                "confidence": 0.95,
            },
            {
                "word": "world",
                "punctuated_word": "world.",
                "speaker": 0,
                "start": 0.5,
                "end": 1.0,
                "confidence": 0.90,
            },
        ]
        segment = DiarizationProcessor._build_segment(words, 0)

        assert segment["text"] == "Hello, world."
        assert segment["speaker_label"] == "Speaker 0"
        assert segment["start_time"] == 0.0
        assert segment["end_time"] == 1.0
        # Average confidence = (0.95 + 0.90) / 2 = 0.925
        assert segment["confidence"] == 0.925


# ===========================================================================
# merge_short_segments
# ===========================================================================


class TestMergeShortSegments:
    """Tests for DiarizationProcessor.merge_short_segments."""

    def test_merge_short_segments_same_speaker_within_threshold(
        self, processor: DiarizationProcessor
    ):
        """Adjacent segments from the same speaker within the gap threshold should be merged."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Hello",
                "start_time": 0.0,
                "end_time": 0.5,
                "confidence": 0.90,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "world",
                "start_time": 1.0,
                "end_time": 1.5,
                "confidence": 0.80,
                "segment_index": 1,
            },
        ]
        result = processor.merge_short_segments(segments, gap_threshold=2.0)

        assert len(result) == 1
        assert result[0]["text"] == "Hello world"
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 1.5

    def test_merge_short_segments_different_speakers_not_merged(
        self, processor: DiarizationProcessor
    ):
        """Segments from different speakers should never be merged, even within threshold."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Hello",
                "start_time": 0.0,
                "end_time": 0.5,
                "confidence": 0.90,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 1",
                "speaker_name": "Speaker 1",
                "text": "Hi there",
                "start_time": 0.6,
                "end_time": 1.5,
                "confidence": 0.85,
                "segment_index": 1,
            },
        ]
        result = processor.merge_short_segments(segments, gap_threshold=2.0)

        assert len(result) == 2
        assert result[0]["speaker_label"] == "Speaker 0"
        assert result[1]["speaker_label"] == "Speaker 1"

    def test_merge_short_segments_same_speaker_beyond_threshold(
        self, processor: DiarizationProcessor
    ):
        """Same-speaker segments beyond the gap threshold should NOT be merged."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "First part",
                "start_time": 0.0,
                "end_time": 1.0,
                "confidence": 0.90,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Second part",
                "start_time": 5.0,
                "end_time": 6.0,
                "confidence": 0.85,
                "segment_index": 1,
            },
        ]
        result = processor.merge_short_segments(segments, gap_threshold=2.0)

        assert len(result) == 2

    def test_merge_short_segments_empty_input(
        self, processor: DiarizationProcessor
    ):
        """Merging an empty segment list should return an empty list."""
        result = processor.merge_short_segments([])
        assert result == []

    def test_merge_short_segments_reindexes(
        self, processor: DiarizationProcessor
    ):
        """After merging, segment_index values should be renumbered from zero."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "A",
                "start_time": 0.0,
                "end_time": 0.5,
                "confidence": 0.90,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "B",
                "start_time": 0.6,
                "end_time": 1.0,
                "confidence": 0.85,
                "segment_index": 1,
            },
            {
                "speaker_label": "Speaker 1",
                "speaker_name": "Speaker 1",
                "text": "C",
                "start_time": 1.5,
                "end_time": 2.0,
                "confidence": 0.88,
                "segment_index": 2,
            },
        ]
        result = processor.merge_short_segments(segments, gap_threshold=2.0)

        # Speaker 0 segments merge into one, Speaker 1 stays separate
        assert len(result) == 2
        assert result[0]["segment_index"] == 0
        assert result[1]["segment_index"] == 1

    def test_merge_short_segments_confidence_weighted_average(
        self, processor: DiarizationProcessor
    ):
        """Merged segments should have confidence as a word-count-weighted average."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Hello",  # 1 word
                "start_time": 0.0,
                "end_time": 0.5,
                "confidence": 1.0,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "beautiful world today",  # 3 words
                "start_time": 0.6,
                "end_time": 1.5,
                "confidence": 0.8,
                "segment_index": 1,
            },
        ]
        result = processor.merge_short_segments(segments, gap_threshold=2.0)

        assert len(result) == 1
        # Weighted: (1.0 * 1 + 0.8 * 3) / (1 + 3) = (1.0 + 2.4) / 4 = 0.85
        assert result[0]["confidence"] == 0.85


# ===========================================================================
# extract_participants
# ===========================================================================


class TestExtractParticipants:
    """Tests for DiarizationProcessor.extract_participants."""

    def test_extract_participants_counts_correctly(
        self, processor: DiarizationProcessor
    ):
        """Participant extraction should correctly count segments and words per speaker."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Hello world",
                "start_time": 0.0,
                "end_time": 1.0,
                "confidence": 0.9,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 1",
                "speaker_name": "Speaker 1",
                "text": "Hi there friend",
                "start_time": 1.5,
                "end_time": 3.0,
                "confidence": 0.85,
                "segment_index": 1,
            },
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Goodbye",
                "start_time": 3.5,
                "end_time": 4.0,
                "confidence": 0.88,
                "segment_index": 2,
            },
        ]
        result = processor.extract_participants(segments)

        assert len(result) == 2

        # Find Speaker 0 and Speaker 1 in results
        sp0 = next(p for p in result if p["speaker_label"] == "Speaker 0")
        sp1 = next(p for p in result if p["speaker_label"] == "Speaker 1")

        assert sp0["segment_count"] == 2
        assert sp0["word_count"] == 3  # "Hello world" + "Goodbye"
        assert sp1["segment_count"] == 1
        assert sp1["word_count"] == 3  # "Hi there friend"

    def test_extract_participants_calculates_duration(
        self, processor: DiarizationProcessor
    ):
        """Participant total_duration should be the sum of each segment's (end - start)."""
        segments = [
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "Hello",
                "start_time": 0.0,
                "end_time": 1.0,
                "confidence": 0.9,
                "segment_index": 0,
            },
            {
                "speaker_label": "Speaker 0",
                "speaker_name": "Speaker 0",
                "text": "World",
                "start_time": 5.0,
                "end_time": 7.5,
                "confidence": 0.85,
                "segment_index": 1,
            },
        ]
        result = processor.extract_participants(segments)

        assert len(result) == 1
        # Duration: (1.0 - 0.0) + (7.5 - 5.0) = 1.0 + 2.5 = 3.5
        assert result[0]["total_duration"] == 3.5

    def test_extract_participants_empty_segments(
        self, processor: DiarizationProcessor
    ):
        """Extracting participants from an empty segment list should return empty."""
        result = processor.extract_participants([])
        assert result == []
