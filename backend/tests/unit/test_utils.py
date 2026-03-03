"""Comprehensive tests for backend/app/utils/ modules.

Covers:
  - app.utils.time_utils: format_timestamp, parse_timestamp, format_duration
  - app.utils.file_processing: validate_file_type, get_file_category, constants,
    extract_text_from_pdf/docx/xlsx (stub behaviour)
  - app.utils.audio: _validate_media_path, extract_audio_from_video, constants

Note: file_processing.py uses ``str | None`` type-union syntax (Python 3.10+).
If running on Python < 3.10 those tests are skipped automatically.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# time_utils  --  pure-python, works on any 3.9+
# ---------------------------------------------------------------------------
from app.utils.time_utils import format_duration, format_timestamp, parse_timestamp

# ---------------------------------------------------------------------------
# audio  --  pure-python + asyncio, works on 3.9+
# ---------------------------------------------------------------------------
from app.utils.audio import (
    ALLOWED_AUDIO_FORMATS,
    ALLOWED_VIDEO_EXTENSIONS,
    _validate_media_path,
    extract_audio_from_video,
)

# ---------------------------------------------------------------------------
# file_processing  --  uses ``str | None`` union syntax (3.10+)
# Try to import; if it fails, mark the whole group as skipped.
# ---------------------------------------------------------------------------
_fp_import_error = None  # Optional[str] -- avoid union syntax for 3.9 compat
try:
    from app.utils.file_processing import (
        ALLOWED_AUDIO_TYPES,
        ALLOWED_DOCUMENT_TYPES,
        ALLOWED_VIDEO_TYPES,
        MAX_FILE_SIZE_MB,
        extract_text_from_docx,
        extract_text_from_pdf,
        extract_text_from_xlsx,
        get_file_category,
        validate_file_type,
    )
except TypeError:
    # Python 3.9: ``str | None`` is not supported
    _fp_import_error = (
        f"file_processing requires Python >= 3.10 (running {sys.version_info[:2]})"
    )

_skip_fp = pytest.mark.skipif(
    _fp_import_error is not None,
    reason=_fp_import_error or "",
)


# ===================================================================
# time_utils tests
# ===================================================================


class TestFormatTimestamp:
    """Tests for format_timestamp()."""

    # -- Happy path --

    def test_zero_seconds(self):
        assert format_timestamp(0) == "00:00"

    def test_under_one_minute(self):
        assert format_timestamp(45) == "00:45"

    def test_exact_one_minute(self):
        assert format_timestamp(60) == "01:00"

    def test_minutes_and_seconds(self):
        assert format_timestamp(125.5) == "02:05"

    def test_exactly_one_hour(self):
        assert format_timestamp(3600) == "1:00:00"

    def test_hours_minutes_seconds(self):
        assert format_timestamp(3661.0) == "1:01:01"

    def test_large_value(self):
        # 10 hours
        assert format_timestamp(36000) == "10:00:00"

    def test_fractional_seconds_truncated(self):
        # 90.9 seconds -> int(90) -> 01:30
        assert format_timestamp(90.9) == "01:30"

    # -- Edge cases --

    def test_float_just_under_hour(self):
        assert format_timestamp(3599.999) == "59:59"

    def test_59_minutes_59_seconds(self):
        assert format_timestamp(3599) == "59:59"


class TestParseTimestamp:
    """Tests for parse_timestamp()."""

    # -- Happy path --

    def test_mm_ss(self):
        assert parse_timestamp("02:05") == 125.0

    def test_hh_mm_ss(self):
        assert parse_timestamp("1:01:01") == 3661.0

    def test_zero(self):
        assert parse_timestamp("00:00") == 0.0

    def test_hour_zero(self):
        assert parse_timestamp("0:00:00") == 0.0

    # -- Edge cases --

    def test_large_hour(self):
        assert parse_timestamp("10:00:00") == 36000.0

    def test_single_digit_minutes(self):
        assert parse_timestamp("5:30") == 330.0

    # -- Error cases --

    def test_single_part_raises(self):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_timestamp("123")

    def test_four_parts_raises(self):
        with pytest.raises(ValueError, match="Invalid timestamp format"):
            parse_timestamp("1:2:3:4")

    def test_empty_string_raises(self):
        with pytest.raises((ValueError,)):
            parse_timestamp("")


class TestFormatDuration:
    """Tests for format_duration()."""

    # -- Happy path --

    def test_seconds_only(self):
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "2m 5s"

    def test_hours_minutes_seconds(self):
        assert format_duration(3661) == "1h 1m 1s"

    def test_zero_seconds(self):
        # "secs > 0 or not parts" => "0s"
        assert format_duration(0) == "0s"

    def test_exact_hour(self):
        assert format_duration(3600) == "1h"

    def test_exact_minute(self):
        assert format_duration(60) == "1m"

    # -- Edge cases --

    def test_hours_and_seconds_no_minutes(self):
        # 1 hour + 5 seconds = 3605
        assert format_duration(3605) == "1h 5s"

    def test_large_value(self):
        # 100 hours
        assert format_duration(360000) == "100h"


class TestTimestampRoundTrip:
    """Verify format_timestamp and parse_timestamp are inverses."""

    @pytest.mark.parametrize("seconds", [0, 45, 125, 3599, 3600, 3661, 36000])
    def test_roundtrip(self, seconds):
        formatted = format_timestamp(seconds)
        assert parse_timestamp(formatted) == float(seconds)


# ===================================================================
# file_processing tests  (skipped on Python < 3.10)
# ===================================================================


@_skip_fp
class TestFileProcessingConstants:
    """Verify file_processing module constants are sensible."""

    def test_max_file_size(self):
        assert MAX_FILE_SIZE_MB == 500  # type: ignore[name-defined]

    def test_audio_types_non_empty(self):
        assert len(ALLOWED_AUDIO_TYPES) > 0  # type: ignore[name-defined]

    def test_video_types_non_empty(self):
        assert len(ALLOWED_VIDEO_TYPES) > 0  # type: ignore[name-defined]

    def test_document_types_non_empty(self):
        assert len(ALLOWED_DOCUMENT_TYPES) > 0  # type: ignore[name-defined]

    def test_audio_types_contain_common_formats(self):
        assert "audio/mpeg" in ALLOWED_AUDIO_TYPES  # type: ignore[name-defined]
        assert "audio/wav" in ALLOWED_AUDIO_TYPES  # type: ignore[name-defined]

    def test_video_types_contain_mp4(self):
        assert "video/mp4" in ALLOWED_VIDEO_TYPES  # type: ignore[name-defined]

    def test_document_types_contain_pdf(self):
        assert "application/pdf" in ALLOWED_DOCUMENT_TYPES  # type: ignore[name-defined]


@_skip_fp
class TestValidateFileType:
    """Tests for validate_file_type()."""

    # -- Happy path --

    def test_valid_audio(self):
        assert validate_file_type("audio/mpeg", "audio") is True  # type: ignore[name-defined]

    def test_valid_video(self):
        assert validate_file_type("video/mp4", "video") is True  # type: ignore[name-defined]

    def test_valid_document(self):
        assert validate_file_type("application/pdf", "document") is True  # type: ignore[name-defined]

    def test_meeting_accepts_audio(self):
        assert validate_file_type("audio/wav", "meeting") is True  # type: ignore[name-defined]

    def test_meeting_accepts_video(self):
        assert validate_file_type("video/mp4", "meeting") is True  # type: ignore[name-defined]

    # -- Rejection cases --

    def test_audio_rejects_video(self):
        assert validate_file_type("video/mp4", "audio") is False  # type: ignore[name-defined]

    def test_video_rejects_audio(self):
        assert validate_file_type("audio/wav", "video") is False  # type: ignore[name-defined]

    def test_document_rejects_audio(self):
        assert validate_file_type("audio/mpeg", "document") is False  # type: ignore[name-defined]

    def test_unknown_category(self):
        assert validate_file_type("audio/mpeg", "unknown") is False  # type: ignore[name-defined]

    def test_empty_content_type(self):
        assert validate_file_type("", "audio") is False  # type: ignore[name-defined]

    def test_empty_category(self):
        assert validate_file_type("audio/mpeg", "") is False  # type: ignore[name-defined]

    def test_invalid_mime(self):
        assert validate_file_type("not-a-real/type", "audio") is False  # type: ignore[name-defined]

    def test_meeting_rejects_document(self):
        assert validate_file_type("application/pdf", "meeting") is False  # type: ignore[name-defined]


@_skip_fp
class TestGetFileCategory:
    """Tests for get_file_category()."""

    def test_audio_category(self):
        assert get_file_category("audio/mpeg") == "audio"  # type: ignore[name-defined]

    def test_video_category(self):
        assert get_file_category("video/mp4") == "video"  # type: ignore[name-defined]

    def test_document_category(self):
        assert get_file_category("application/pdf") == "document"  # type: ignore[name-defined]

    def test_unknown_returns_none(self):
        assert get_file_category("application/octet-stream") is None  # type: ignore[name-defined]

    def test_empty_string_returns_none(self):
        assert get_file_category("") is None  # type: ignore[name-defined]

    def test_audio_x_m4a(self):
        assert get_file_category("audio/x-m4a") == "audio"  # type: ignore[name-defined]

    def test_all_audio_types_return_audio(self):
        for ct in ALLOWED_AUDIO_TYPES:  # type: ignore[name-defined]
            assert get_file_category(ct) == "audio"  # type: ignore[name-defined]

    def test_all_video_types_return_video(self):
        for ct in ALLOWED_VIDEO_TYPES:  # type: ignore[name-defined]
            assert get_file_category(ct) == "video"  # type: ignore[name-defined]

    def test_all_document_types_return_document(self):
        for ct in ALLOWED_DOCUMENT_TYPES:  # type: ignore[name-defined]
            assert get_file_category(ct) == "document"  # type: ignore[name-defined]


@_skip_fp
class TestExtractTextStubs:
    """Verify that unimplemented extract_text_from_* raise NotImplementedError."""

    async def test_extract_text_from_pdf_not_implemented(self):
        with pytest.raises(NotImplementedError):
            await extract_text_from_pdf(b"fake pdf bytes")  # type: ignore[name-defined]

    async def test_extract_text_from_docx_not_implemented(self):
        with pytest.raises(NotImplementedError):
            await extract_text_from_docx(b"fake docx bytes")  # type: ignore[name-defined]

    async def test_extract_text_from_xlsx_not_implemented(self):
        with pytest.raises(NotImplementedError):
            await extract_text_from_xlsx(b"fake xlsx bytes")  # type: ignore[name-defined]


# ===================================================================
# audio tests
# ===================================================================


class TestAudioConstants:
    """Verify audio module constants."""

    def test_allowed_audio_formats(self):
        assert "wav" in ALLOWED_AUDIO_FORMATS
        assert "mp3" in ALLOWED_AUDIO_FORMATS
        assert "flac" in ALLOWED_AUDIO_FORMATS

    def test_allowed_video_extensions(self):
        assert ".mp4" in ALLOWED_VIDEO_EXTENSIONS
        assert ".mov" in ALLOWED_VIDEO_EXTENSIONS
        assert ".wav" in ALLOWED_VIDEO_EXTENSIONS


class TestValidateMediaPath:
    """Tests for _validate_media_path()."""

    # -- Happy path --

    def test_valid_input_mp4(self, tmp_path):
        p = tmp_path / "video.mp4"
        p.touch()
        result = _validate_media_path(str(p), "input")
        assert result == p.resolve()

    def test_valid_input_wav(self, tmp_path):
        p = tmp_path / "audio.wav"
        p.touch()
        result = _validate_media_path(str(p), "input")
        assert result == p.resolve()

    def test_valid_input_mov(self, tmp_path):
        p = tmp_path / "clip.mov"
        p.touch()
        result = _validate_media_path(str(p), "input")
        assert result == p.resolve()

    def test_output_label_allows_any_extension(self, tmp_path):
        # Output paths are not validated for extension
        p = tmp_path / "output.xyz"
        result = _validate_media_path(str(p), "output")
        assert result == p.resolve()

    # -- Error cases --

    def test_directory_traversal_rejected(self):
        with pytest.raises(ValueError, match="directory traversal"):
            _validate_media_path("/some/path/../etc/passwd.mp4", "input")

    def test_disallowed_extension_rejected(self, tmp_path):
        p = tmp_path / "file.txt"
        p.touch()
        with pytest.raises(ValueError, match="Unsupported input file extension"):
            _validate_media_path(str(p), "input")

    def test_disallowed_extension_exe(self, tmp_path):
        p = tmp_path / "file.exe"
        p.touch()
        with pytest.raises(ValueError, match="Unsupported input file extension"):
            _validate_media_path(str(p), "input")

    def test_traversal_with_double_dot_in_middle(self):
        with pytest.raises(ValueError, match="directory traversal"):
            _validate_media_path("/a/b/../c/file.mp4", "input")

    def test_all_allowed_extensions(self, tmp_path):
        for ext in ALLOWED_VIDEO_EXTENSIONS:
            p = tmp_path / f"file{ext}"
            p.touch()
            result = _validate_media_path(str(p), "input")
            assert result == p.resolve()

    def test_output_with_traversal_still_rejected(self):
        with pytest.raises(ValueError, match="directory traversal"):
            _validate_media_path("/some/../path/out.wav", "output")


class TestExtractAudioFromVideo:
    """Tests for extract_audio_from_video()."""

    async def test_unsupported_format_raises(self):
        with pytest.raises(ValueError, match="Unsupported audio format"):
            await extract_audio_from_video("/tmp/input.mp4", "/tmp/output.aac", format="aac")

    async def test_directory_traversal_in_input_raises(self):
        with pytest.raises(ValueError, match="directory traversal"):
            await extract_audio_from_video(
                "/tmp/../etc/input.mp4", "/tmp/output.wav", format="wav"
            )

    async def test_disallowed_input_extension_raises(self):
        with pytest.raises(ValueError, match="Unsupported input file extension"):
            await extract_audio_from_video("/tmp/input.txt", "/tmp/output.wav", format="wav")

    async def test_successful_extraction(self, tmp_path):
        """Mock subprocess to simulate successful ffmpeg execution."""
        input_file = tmp_path / "video.mp4"
        output_file = tmp_path / "audio.wav"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch("app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extract_audio_from_video(
                str(input_file), str(output_file), format="wav", sample_rate=16000, channels=1
            )
            assert result == str(output_file)

    async def test_ffmpeg_failure_raises_runtime_error(self, tmp_path):
        """Mock subprocess to simulate ffmpeg failure."""
        input_file = tmp_path / "video.mp4"
        output_file = tmp_path / "audio.wav"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b"Error: something went wrong"))
        mock_process.returncode = 1

        with patch("app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process):
            with pytest.raises(RuntimeError, match="ffmpeg failed"):
                await extract_audio_from_video(
                    str(input_file), str(output_file), format="wav"
                )

    async def test_mp3_codec_selection(self, tmp_path):
        """Verify that mp3 format uses libmp3lame codec."""
        input_file = tmp_path / "video.mp4"
        output_file = tmp_path / "audio.mp3"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch(
            "app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process
        ) as mock_exec:
            await extract_audio_from_video(
                str(input_file), str(output_file), format="mp3"
            )
            # Check that libmp3lame was passed as codec
            call_args = mock_exec.call_args[0]
            assert "libmp3lame" in call_args

    async def test_wav_codec_selection(self, tmp_path):
        """Verify that wav format uses pcm_s16le codec."""
        input_file = tmp_path / "video.mp4"
        output_file = tmp_path / "audio.wav"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch(
            "app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process
        ) as mock_exec:
            await extract_audio_from_video(
                str(input_file), str(output_file), format="wav"
            )
            call_args = mock_exec.call_args[0]
            assert "pcm_s16le" in call_args

    async def test_custom_sample_rate_and_channels(self, tmp_path):
        """Verify custom sample_rate and channels are passed to ffmpeg."""
        input_file = tmp_path / "video.mp4"
        output_file = tmp_path / "audio.wav"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        with patch(
            "app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process
        ) as mock_exec:
            await extract_audio_from_video(
                str(input_file), str(output_file), format="wav",
                sample_rate=44100, channels=2
            )
            call_args = mock_exec.call_args[0]
            assert "44100" in call_args
            assert "2" in call_args

    async def test_all_allowed_audio_formats_accepted(self, tmp_path):
        """Ensure every format in ALLOWED_AUDIO_FORMATS passes validation."""
        input_file = tmp_path / "video.mp4"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        for fmt in ALLOWED_AUDIO_FORMATS:
            output_file = tmp_path / f"audio.{fmt}"
            with patch(
                "app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process
            ):
                result = await extract_audio_from_video(
                    str(input_file), str(output_file), format=fmt
                )
                assert result == str(output_file)

    async def test_returns_original_output_path_string(self, tmp_path):
        """The function should return the exact output_path string passed in."""
        input_file = tmp_path / "video.mp4"
        output_file = tmp_path / "audio.wav"
        input_file.touch()

        mock_process = AsyncMock()
        mock_process.communicate = AsyncMock(return_value=(b"", b""))
        mock_process.returncode = 0

        original_path = str(output_file)
        with patch("app.utils.audio.asyncio.create_subprocess_exec", return_value=mock_process):
            result = await extract_audio_from_video(original_path, original_path, format="wav")
            # Note: input_path validation would fail if .wav wasn't in ALLOWED_VIDEO_EXTENSIONS
            # but .wav IS allowed, so this works. The return value should be the same string.
            assert result is original_path
