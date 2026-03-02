def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS format.

    Examples:
        125.5 -> "02:05"
        3661.0 -> "1:01:01"
    """
    total = int(seconds)
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_timestamp(ts: str) -> float:
    """Convert MM:SS or HH:MM:SS format to seconds.

    Examples:
        "02:05" -> 125.0
        "1:01:01" -> 3661.0
    """
    parts = ts.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    raise ValueError(f"Invalid timestamp format: {ts}")


def format_duration(seconds: int) -> str:
    """Convert total seconds to human-readable duration.

    Examples:
        3661 -> "1h 1m 1s"
        125 -> "2m 5s"
        45 -> "45s"
    """
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)
