import asyncio
import subprocess
from pathlib import Path

ALLOWED_AUDIO_FORMATS = {"wav", "mp3", "flac", "ogg", "m4a"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4a", ".wav", ".mp3"}


def _validate_media_path(path: str, label: str) -> Path:
    """Validate that a media path is safe (no traversal, reasonable extension)."""
    resolved = Path(path).resolve()

    # Block path traversal via .. components
    if ".." in Path(path).parts:
        raise ValueError(f"{label} path contains directory traversal: {path}")

    # Validate extension for input files
    if label == "input" and resolved.suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValueError(
            f"Unsupported {label} file extension: {resolved.suffix}. "
            f"Allowed: {ALLOWED_VIDEO_EXTENSIONS}"
        )

    return resolved


async def extract_audio_from_video(
    input_path: str,
    output_path: str,
    format: str = "wav",
    sample_rate: int = 16000,
    channels: int = 1,
) -> str:
    """Extract mono audio from a video file using ffmpeg.

    Args:
        input_path: Path to the input video file.
        output_path: Path to write the extracted audio.
        format: Output audio format (wav, mp3, etc.).
        sample_rate: Audio sample rate in Hz.
        channels: Number of audio channels (1 = mono).

    Returns:
        The output_path on success.

    Raises:
        ValueError: If paths contain traversal or have disallowed extensions.
    """
    if format not in ALLOWED_AUDIO_FORMATS:
        raise ValueError(f"Unsupported audio format: {format}. Allowed: {ALLOWED_AUDIO_FORMATS}")

    safe_input = _validate_media_path(input_path, "input")
    safe_output = _validate_media_path(output_path, "output")

    cmd = [
        "ffmpeg",
        "-i", str(safe_input),
        "-vn",  # no video
        "-acodec", "pcm_s16le" if format == "wav" else "libmp3lame",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-y",  # overwrite
        str(safe_output),
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

    return output_path
