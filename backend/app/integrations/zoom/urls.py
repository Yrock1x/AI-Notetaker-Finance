"""Helpers for extracting Zoom join URLs from arbitrary text.

Used by the calendar-sync pipeline when a Google Calendar event carries a
Zoom meeting link inside its description / location (the common case for
Zoom meetings scheduled via a Zoom add-in / scheduler — Google's
``conferenceData`` only exposes native Meet links, so those show up as
plain text in the event body).
"""

from __future__ import annotations

import re

# Zoom surfaces regional subdomains like ``us05web.zoom.us`` and
# ``us02web.zoom.us`` for personal meeting rooms, plus the bare
# ``zoom.us`` for business accounts. Capture up to the first whitespace,
# closing bracket, or newline — Zoom URLs never legally contain those.
_ZOOM_URL = re.compile(
    r"https?://[a-zA-Z0-9-]*\.?zoom\.us/j/\d+(?:\?[^\s)\]]+)?",
    re.IGNORECASE,
)

# ``zoom.us/j/<numeric>`` is the part that uniquely identifies a
# meeting — different subdomains or ``?pwd=`` params can still point at
# the same call. Used for dedupe matching across providers.
_ZOOM_MEETING_ID = re.compile(r"zoom\.us/j/(\d+)", re.IGNORECASE)


def extract_zoom_url(text: str | None) -> str | None:
    """Return the first Zoom join URL found in ``text``, or ``None``."""
    if not text:
        return None
    m = _ZOOM_URL.search(text)
    return m.group(0) if m else None


def extract_zoom_meeting_id(text: str | None) -> str | None:
    """Return the numeric Zoom meeting id embedded in ``text``."""
    if not text:
        return None
    m = _ZOOM_MEETING_ID.search(text)
    return m.group(1) if m else None
