"""Microsoft Graph API client for Teams / Outlook calendar and meeting data."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import structlog

logger = structlog.get_logger(__name__)

GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


class GraphAPIClient:
    """Client for Microsoft Graph API operations related to Teams."""

    def _auth_headers(self, access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    async def get_calendar_events(
        self,
        access_token: str,
        user_id: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict]:
        """Retrieve calendar events for a user within a time range.

        Uses the ``calendarview`` endpoint which expands recurring events.
        """
        params = {
            "startDateTime": time_min.isoformat(),
            "endDateTime": time_max.isoformat(),
            "$select": "subject,start,end,bodyPreview,onlineMeeting,webLink",
            "$orderby": "start/dateTime",
            "$top": "50",
        }
        url = f"{GRAPH_BASE_URL}/users/{user_id}/calendarview"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    params=params,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                data = resp.json()
                events = data.get("value", [])
                logger.info(
                    "graph_calendar_events_fetched",
                    user_id=user_id,
                    count=len(events),
                )
                return events
        except httpx.HTTPStatusError as exc:
            logger.error(
                "graph_calendar_events_error",
                user_id=user_id,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error(
                "graph_calendar_events_network_error",
                user_id=user_id,
                error=str(exc),
            )
            raise

    # ------------------------------------------------------------------
    # Recordings
    # ------------------------------------------------------------------

    async def get_meeting_recordings(
        self, access_token: str, meeting_id: str
    ) -> list[dict]:
        """Retrieve recordings for a specific Teams meeting.

        Uses the ``onlineMeetings/{id}/recordings`` endpoint (requires
        OnlineMeetings.Read or OnlineMeetings.ReadWrite permission).
        """
        url = f"{GRAPH_BASE_URL}/me/onlineMeetings/{meeting_id}/recordings"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    url,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                data = resp.json()
                recordings = data.get("value", [])
                logger.info(
                    "graph_meeting_recordings_fetched",
                    meeting_id=meeting_id,
                    count=len(recordings),
                )
                return recordings
        except httpx.HTTPStatusError as exc:
            logger.error(
                "graph_meeting_recordings_error",
                meeting_id=meeting_id,
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error(
                "graph_meeting_recordings_network_error",
                meeting_id=meeting_id,
                error=str(exc),
            )
            raise

    # ------------------------------------------------------------------
    # User profile
    # ------------------------------------------------------------------

    async def get_user_profile(self, access_token: str) -> dict:
        """Retrieve the authenticated user's profile from Graph API."""
        url = f"{GRAPH_BASE_URL}/me"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    url,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                profile = resp.json()
                logger.info(
                    "graph_user_profile_fetched",
                    user_principal=profile.get("userPrincipalName"),
                )
                return profile
        except httpx.HTTPStatusError as exc:
            logger.error(
                "graph_user_profile_error",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("graph_user_profile_network_error", error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Subscriptions (change notifications)
    # ------------------------------------------------------------------

    async def subscribe_to_call_records(
        self,
        access_token: str,
        notification_url: str,
        client_state: str,
        expiration_minutes: int = 4230,
    ) -> dict:
        """Create a Graph API subscription for ``communications/callRecords``.

        The subscription notifies ``notification_url`` whenever a call record
        is created.  ``client_state`` is an opaque string (max 128 chars) that
        Graph sends back with every notification for request validation.

        ``expiration_minutes`` defaults to ~2.9 days (the max for callRecords).
        """
        from datetime import timedelta

        expiration = (
            datetime.now(UTC) + timedelta(minutes=expiration_minutes)
        ).isoformat()

        payload = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": "communications/callRecords",
            "expirationDateTime": expiration,
            "clientState": client_state,
        }

        url = f"{GRAPH_BASE_URL}/subscriptions"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    url,
                    json=payload,
                    headers=self._auth_headers(access_token),
                )
                resp.raise_for_status()
                subscription = resp.json()
                logger.info(
                    "graph_subscription_created",
                    subscription_id=subscription.get("id"),
                    resource="communications/callRecords",
                )
                return subscription
        except httpx.HTTPStatusError as exc:
            logger.error(
                "graph_subscription_error",
                status=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise
        except httpx.HTTPError as exc:
            logger.error("graph_subscription_network_error", error=str(exc))
            raise
