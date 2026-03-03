"""Zoom REST API client for user, recording, and meeting operations."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

ZOOM_API_BASE = "https://api.zoom.us/v2"


class ZoomAPIClient:
    """Client for Zoom REST API operations."""

    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def get_user(self, access_token: str) -> dict:
        """Retrieve the authenticated Zoom user's profile."""
        url = f"{ZOOM_API_BASE}/users/me"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                user = resp.json()
                logger.info(
                    "zoom_user_fetched",
                    user_id=user.get("id"),
                    email=user.get("email"),
                )
                return user
        except httpx.HTTPStatusError as exc:
            logger.error(
                "zoom_get_user_error",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("zoom_get_user_network_error", error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Recordings
    # ------------------------------------------------------------------

    async def list_recordings(
        self, access_token: str, user_id: str
    ) -> list[dict]:
        """List cloud recordings for a Zoom user.

        Returns the ``meetings`` array from the Zoom recordings list
        endpoint.  Each element contains ``recording_files`` with download
        URLs.
        """
        url = f"{ZOOM_API_BASE}/users/{user_id}/recordings"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                data = resp.json()
                meetings = data.get("meetings", [])
                logger.info(
                    "zoom_recordings_listed",
                    user_id=user_id,
                    count=len(meetings),
                )
                return meetings
        except httpx.HTTPStatusError as exc:
            logger.error(
                "zoom_list_recordings_error",
                user_id=user_id,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error(
                "zoom_list_recordings_network_error",
                user_id=user_id,
                error=str(exc),
            )
            raise

    async def get_recording_download_url(
        self, access_token: str, recording_id: str
    ) -> str:
        """Get a download URL for a specific Zoom recording.

        Fetches the recording metadata and returns the ``download_url``
        with an appended access token query parameter for authenticated
        download.
        """
        url = f"{ZOOM_API_BASE}/meetings/{recording_id}/recordings"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                data = resp.json()

                # Find the first audio recording file
                recording_files = data.get("recording_files", [])
                for rf in recording_files:
                    if rf.get("file_type") in ("MP4", "M4A", "mp4", "m4a"):
                        download_url = rf.get("download_url", "")
                        if download_url:
                            # Append access token for authenticated download
                            separator = "&" if "?" in download_url else "?"
                            authenticated_url = (
                                f"{download_url}{separator}"
                                f"access_token={access_token}"
                            )
                            logger.info(
                                "zoom_recording_download_url_resolved",
                                recording_id=recording_id,
                                file_type=rf.get("file_type"),
                            )
                            return authenticated_url

                # Fall back to the first file if no MP4/M4A found
                if recording_files:
                    download_url = recording_files[0].get("download_url", "")
                    if download_url:
                        separator = "&" if "?" in download_url else "?"
                        return (
                            f"{download_url}{separator}"
                            f"access_token={access_token}"
                        )

                logger.warning(
                    "zoom_no_recording_files",
                    recording_id=recording_id,
                )
                return ""

        except httpx.HTTPStatusError as exc:
            logger.error(
                "zoom_recording_download_error",
                recording_id=recording_id,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error(
                "zoom_recording_download_network_error",
                recording_id=recording_id,
                error=str(exc),
            )
            raise
