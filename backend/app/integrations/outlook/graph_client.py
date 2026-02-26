from __future__ import annotations

from datetime import datetime


class OutlookGraphClient:
    """Client for Microsoft Graph API operations related to Outlook."""

    async def get_calendar_events(
        self, access_token: str, time_min: datetime, time_max: datetime
    ) -> list[dict]:
        """Retrieve Outlook calendar events within a time range."""
        raise NotImplementedError

    async def create_calendar_event(self, access_token: str, event: dict) -> dict:
        """Create a new Outlook calendar event."""
        raise NotImplementedError
