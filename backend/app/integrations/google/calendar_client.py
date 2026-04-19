"""Google Calendar API — list upcoming events, extract Meet joinUrl."""

from __future__ import annotations

from datetime import datetime

import httpx
import structlog

logger = structlog.get_logger(__name__)

API_BASE = "https://www.googleapis.com/calendar/v3"


class GoogleCalendarClient:
    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    async def list_events(
        self,
        access_token: str,
        *,
        time_min: datetime,
        time_max: datetime,
        calendar_id: str = "primary",
        max_results: int = 100,
    ) -> list[dict]:
        """List events on the user's primary calendar in [time_min, time_max).

        ``conferenceData.entryPoints[].uri`` holds the Meet URL when one was
        attached to the event; older events fall back to ``hangoutLink``.
        """
        params = {
            "timeMin": time_min.isoformat(),
            "timeMax": time_max.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": str(max_results),
            "conferenceDataVersion": "1",
        }
        url = f"{API_BASE}/calendars/{calendar_id}/events"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                url,
                params=params,
                headers=self._auth_headers(access_token),
            )
            if resp.status_code >= 400:
                logger.error(
                    "google_calendar_list_error",
                    status=resp.status_code,
                    body=resp.text[:500],
                )
                resp.raise_for_status()
            data = resp.json()
            events = data.get("items", [])
            logger.info("google_calendar_events_fetched", count=len(events))
            return events

    @staticmethod
    def extract_meet_url(event: dict) -> str | None:
        """Pull a Google Meet URL out of a calendar event, if present."""
        conf = event.get("conferenceData") or {}
        for entry in conf.get("entryPoints") or []:
            if entry.get("entryPointType") == "video" and entry.get("uri"):
                return entry["uri"]
        return event.get("hangoutLink")
