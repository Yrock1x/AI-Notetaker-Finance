from __future__ import annotations

from datetime import datetime


class GraphAPIClient:
    """Client for Microsoft Graph API operations related to Teams."""

    async def get_calendar_events(
        self, access_token: str, user_id: str, time_min: datetime, time_max: datetime
    ) -> list[dict]:
        """Retrieve calendar events for a user within a time range."""
        raise NotImplementedError

    async def get_meeting_recordings(self, access_token: str, meeting_id: str) -> list[dict]:
        """Retrieve recordings for a specific Teams meeting."""
        raise NotImplementedError
