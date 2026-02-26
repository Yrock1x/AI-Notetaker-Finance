from __future__ import annotations


class CalendarSyncService:
    """Service for synchronizing Outlook calendar events."""

    async def sync_for_user(self, org_id: str, user_id: str) -> list[dict]:
        """Synchronize calendar events for a specific user in an organization."""
        raise NotImplementedError

    async def detect_meeting_links(self, events: list[dict]) -> list[dict]:
        """Detect and extract meeting platform links from calendar events."""
        raise NotImplementedError
