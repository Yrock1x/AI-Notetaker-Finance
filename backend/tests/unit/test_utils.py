"""Tests for app.utils.file_processing — MIME validation + category mapping.

(The former app.utils.audio and app.utils.time_utils modules were removed as
dead code; their tests went with them. extract_text_from_pdf/docx/xlsx are now
implemented — exercising them needs real document fixtures, which is out of
scope here — so the old NotImplementedError stub assertions were dropped.)
"""

from __future__ import annotations

from app.utils.file_processing import (
    ALLOWED_AUDIO_TYPES,
    ALLOWED_DOCUMENT_TYPES,
    ALLOWED_VIDEO_TYPES,
    MAX_FILE_SIZE_MB,
    get_file_category,
    validate_file_type,
)


class TestFileProcessingConstants:
    """Verify file_processing module constants are sensible."""

    def test_max_file_size(self):
        assert MAX_FILE_SIZE_MB == 500

    def test_audio_types_non_empty(self):
        assert len(ALLOWED_AUDIO_TYPES) > 0

    def test_video_types_non_empty(self):
        assert len(ALLOWED_VIDEO_TYPES) > 0

    def test_document_types_non_empty(self):
        assert len(ALLOWED_DOCUMENT_TYPES) > 0

    def test_audio_types_contain_common_formats(self):
        assert "audio/mpeg" in ALLOWED_AUDIO_TYPES
        assert "audio/wav" in ALLOWED_AUDIO_TYPES

    def test_video_types_contain_mp4(self):
        assert "video/mp4" in ALLOWED_VIDEO_TYPES

    def test_document_types_contain_pdf(self):
        assert "application/pdf" in ALLOWED_DOCUMENT_TYPES


class TestValidateFileType:
    """Tests for validate_file_type()."""

    def test_valid_audio(self):
        assert validate_file_type("audio/mpeg", "audio") is True

    def test_valid_video(self):
        assert validate_file_type("video/mp4", "video") is True

    def test_valid_document(self):
        assert validate_file_type("application/pdf", "document") is True

    def test_meeting_accepts_audio(self):
        assert validate_file_type("audio/wav", "meeting") is True

    def test_meeting_accepts_video(self):
        assert validate_file_type("video/mp4", "meeting") is True

    def test_audio_rejects_video(self):
        assert validate_file_type("video/mp4", "audio") is False

    def test_video_rejects_audio(self):
        assert validate_file_type("audio/wav", "video") is False

    def test_document_rejects_audio(self):
        assert validate_file_type("audio/mpeg", "document") is False

    def test_unknown_category(self):
        assert validate_file_type("audio/mpeg", "unknown") is False

    def test_empty_content_type(self):
        assert validate_file_type("", "audio") is False

    def test_empty_category(self):
        assert validate_file_type("audio/mpeg", "") is False

    def test_invalid_mime(self):
        assert validate_file_type("not-a-real/type", "audio") is False

    def test_meeting_rejects_document(self):
        assert validate_file_type("application/pdf", "meeting") is False


class TestGetFileCategory:
    """Tests for get_file_category()."""

    def test_audio_category(self):
        assert get_file_category("audio/mpeg") == "audio"

    def test_video_category(self):
        assert get_file_category("video/mp4") == "video"

    def test_document_category(self):
        assert get_file_category("application/pdf") == "document"

    def test_unknown_returns_none(self):
        assert get_file_category("application/octet-stream") is None

    def test_empty_string_returns_none(self):
        assert get_file_category("") is None

    def test_audio_x_m4a(self):
        assert get_file_category("audio/x-m4a") == "audio"

    def test_all_audio_types_return_audio(self):
        for ct in ALLOWED_AUDIO_TYPES:
            assert get_file_category(ct) == "audio"

    def test_all_video_types_return_video(self):
        for ct in ALLOWED_VIDEO_TYPES:
            assert get_file_category(ct) == "video"

    def test_all_document_types_return_document(self):
        for ct in ALLOWED_DOCUMENT_TYPES:
            assert get_file_category(ct) == "document"
