"""Outlook calendar synchronisation service.

Fetches upcoming events from a user's Outlook calendar via the Microsoft
Graph API and extracts meeting-platform URLs (Zoom, Teams, Google Meet)
so the system can automatically schedule recording bots.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import structlog

from app.integrations.outlook.graph_client import OutlookGraphClient

logger = structlog.get_logger(__name__)


class CalendarSyncService:
    """Service for synchronising Outlook calendar events and detecting meeting links."""

    # Regex patterns for meeting platform links
    ZOOM_PATTERN = re.compile(
        r'https?://[\w.-]*zoom\.us/[jw]/\d+[^\s"<]*', re.IGNORECASE
    )
    TEAMS_PATTERN = re.compile(
        r'https?://teams\.microsoft\.com/l/meetup-join/[^\s"<]+', re.IGNORECASE
    )
    GMEET_PATTERN = re.compile(
        r'https?://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}[^\s"<]*',
        re.IGNORECASE,
    )

    def __init__(self, graph_client: OutlookGraphClient | None = None) -> None:
        self._graph_client = graph_client or OutlookGraphClient()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def sync_for_user(
        self,
        org_id: str,
        user_id: str,
        access_token: str = "",
    ) -> list[dict]:
        """Fetch calendar events for the next 7 days and detect meeting links.

        Args:
            org_id: Organisation ID (for logging/context).
            user_id: User ID (for logging/context).
            access_token: Microsoft Graph OAuth access token.

        Returns:
            A list of dicts, each containing the calendar ``event`` and any
            detected ``meeting_links``.  Events without meeting links are
            excluded from the result.
        """
        now = datetime.now(UTC)
        time_max = now + timedelta(days=7)

        logger.info(
            "calendar_sync_started",
            org_id=org_id,
            user_id=user_id,
            window_start=now.isoformat(),
            window_end=time_max.isoformat(),
        )

        try:
            events = await self._graph_client.get_calendar_events(
                access_token, now, time_max
            )
        except Exception:
            logger.exception(
                "calendar_sync_fetch_failed",
                org_id=org_id,
                user_id=user_id,
            )
            raise

        results: list[dict] = []
        for event in events:
            links = self.detect_meeting_links([event])
            if links:
                results.append({
                    "event": event,
                    "meeting_links": links,
                })

        logger.info(
            "calendar_sync_complete",
            org_id=org_id,
            user_id=user_id,
            total_events=len(events),
            events_with_links=len(results),
        )

        return results

    # ------------------------------------------------------------------
    # Meeting-link detection
    # ------------------------------------------------------------------

    def detect_meeting_links(self, events: list[dict]) -> list[dict]:
        """Extract meeting platform URLs from event bodies, subjects, and location.

        Scans the ``subject``, ``body.content``, and ``location.displayName``
        fields for Zoom, Teams, and Google Meet URLs.

        Args:
            events: A list of calendar event dicts (Graph API format).

        Returns:
            A list of dicts with ``platform``, ``url``, and ``event_subject``.
        """
        links: list[dict] = []

        for event in events:
            # Consolidate all text fields that could contain a meeting link
            body_raw = event.get("body")
            if isinstance(body_raw, dict):
                body_text = body_raw.get("content", "")
            else:
                body_text = str(body_raw) if body_raw else ""

            location_raw = event.get("location")
            if isinstance(location_raw, dict):
                location_text = location_raw.get("displayName", "")
            else:
                location_text = str(location_raw) if location_raw else ""

            text = " ".join([
                event.get("subject", ""),
                body_text,
                location_text,
            ])

            subject = event.get("subject", "")

            for match in self.ZOOM_PATTERN.finditer(text):
                links.append({
                    "platform": "zoom",
                    "url": match.group(),
                    "event_subject": subject,
                })

            for match in self.TEAMS_PATTERN.finditer(text):
                links.append({
                    "platform": "teams",
                    "url": match.group(),
                    "event_subject": subject,
                })

            for match in self.GMEET_PATTERN.finditer(text):
                links.append({
                    "platform": "google_meet",
                    "url": match.group(),
                    "event_subject": subject,
                })

        return links
