from __future__ import annotations


class ZoomAPIClient:
    """Client for Zoom REST API operations."""

    async def get_user(self, access_token: str) -> dict:
        """Retrieve the authenticated Zoom user's profile."""
        raise NotImplementedError

    async def list_recordings(self, access_token: str, user_id: str) -> list[dict]:
        """List cloud recordings for a Zoom user."""
        raise NotImplementedError

    async def get_recording_download_url(self, access_token: str, recording_id: str) -> str:
        """Get a download URL for a specific Zoom recording."""
        raise NotImplementedError
