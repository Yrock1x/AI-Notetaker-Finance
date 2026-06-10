"""Shared internals for the /internal service-to-service routers:
the X-Internal-Token guard, storage bucket names, and helpers.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Meeting,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Service-to-service auth
# ---------------------------------------------------------------------------
def require_internal_token(
    x_internal_token: str | None = Header(default=None),
) -> None:
    expected = settings.worker_internal_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WORKER_INTERNAL_TOKEN is not configured",
        )
    if x_internal_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token",
        )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
MEETINGS_BUCKET = "meeting-recordings"
DOCUMENTS_BUCKET = "deal-documents"

# Map a meeting recording's file extension to a Deepgram-friendly mimetype.
_EXT_MIMETYPES: dict[str, str] = {
    "mp4": "audio/mp4",
    "m4a": "audio/mp4",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "flac": "audio/flac",
    "aac": "audio/aac",
}


def _mimetype_for_key(file_key: str) -> str:
    """Pick an audio mimetype from a storage key's extension (default mp4)."""
    ext = file_key.rsplit(".", 1)[-1].lower() if "." in file_key else ""
    return _EXT_MIMETYPES.get(ext, "audio/mp4")


def _dedupe_zoom_google_rows(
    session: Session,
    org_id: Any,
    dates: list[str],
) -> None:
    """Collapse Google+Zoom duplicates into one Zoom-sourced row.

    When a user schedules a Zoom meeting that auto-creates a Google Calendar
    event, both providers sync the same underlying call. The Zoom row has
    the real ``us05web.zoom.us/j/<id>`` URL; the Google row only has an
    ``htmlLink`` fallback (or a ``source='zoom'`` row we built from the
    description). After each sync we look at the dates we just touched and
    merge any same-time pair into the Zoom row so:
      - The Calendar view + Dashboard widget show one card, not two.
      - Any user-set ``deal_id`` / ``bot_enabled`` on either row is
        preserved on the surviving Zoom row.
    """
    from app.integrations.zoom.urls import extract_zoom_meeting_id

    if not dates:
        return
    rows = (
        session.scalars(
            select(Meeting)
            .where(Meeting.org_id == str(org_id))
            .where(Meeting.meeting_date.in_(list(set(dates))))
        ).all()
    )

    # Group by meeting_date — a Zoom meeting + its Google shadow share the
    # same start time down to the second, so that's a stable join key.
    by_date: dict[str, list[Meeting]] = {}
    for r in rows:
        if r.meeting_date is None:
            continue
        by_date.setdefault(r.meeting_date, []).append(r)

    for date_rows in by_date.values():
        if len(date_rows) < 2:
            continue
        # Prefer the row that came directly from Zoom's own calendar API
        # as the canonical one — its source_url is always the real
        # ``us05web.zoom.us/j/…`` join link with no HTML cruft. Google-
        # sourced rows can also carry source='zoom' (we parse the Zoom
        # URL out of the event description), but that URL may have been
        # pasted from a template and is less reliable.
        zoom_row = next(
            (
                r
                for r in date_rows
                if r.source == "zoom" and r.external_provider == "zoom"
            ),
            None,
        )
        if not zoom_row:
            zoom_row = next(
                (r for r in date_rows if r.source == "zoom"),
                None,
            )
        if not zoom_row:
            continue
        zoom_id = extract_zoom_meeting_id(zoom_row.source_url or "")

        for other in date_rows:
            if other.id == zoom_row.id:
                continue
            # Two rows for the SAME provider at the same second — don't
            # merge; that would be destroying two real back-to-back
            # meetings (vanishingly rare but possible).
            if other.external_provider == zoom_row.external_provider:
                continue
            # Confirm the other row points at the same Zoom meeting
            # before deleting. If we can extract a meeting id from its
            # source_url and it doesn't match, leave both alone — they
            # really are different calls.
            other_zoom_id = extract_zoom_meeting_id(other.source_url or "")
            if zoom_id and other_zoom_id and other_zoom_id != zoom_id:
                continue
            # Merge user-set fields onto the surviving Zoom row.
            if not zoom_row.deal_id and other.deal_id:
                zoom_row.deal_id = other.deal_id
            # bot_enabled: prefer an explicit off (user opt-out) over on.
            if other.bot_enabled is False:
                zoom_row.bot_enabled = False
            session.delete(other)
    session.flush()
