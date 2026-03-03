"""Microsoft Graph API client for Outlook calendar and user operations.

Uses httpx for async HTTP. Handles OData pagination via ``@odata.nextLink``
and uses ``$select`` to minimise payload size.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_TIMEOUT = 30.0

# Fields requested from the calendarView endpoint
CALENDAR_SELECT_FIELDS = (
    "id,subject,start,end,body,onlineMeeting,webLink,"
    "location,attendees,organizer,isOnlineMeeting"
)


class GraphApiError(Exception):
    """Raised when the Microsoft Graph API returns an error response."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(f"Graph API {status_code} ({error_code}): {message}")


class OutlookGraphClient:
    """Client for Microsoft Graph API operations related to Outlook."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _auth_headers(access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _raise_for_graph_error(resp: httpx.Response) -> None:
        """Inspect a non-2xx response and raise a structured error."""
        try:
            body = resp.json()
            err = body.get("error", {})
            code = err.get("code", "unknown")
            message = err.get("message", resp.text)
        except Exception:
            code = "unknown"
            message = resp.text
        raise GraphApiError(
            status_code=resp.status_code,
            error_code=code,
            message=message,
        )

    # ------------------------------------------------------------------
    # Calendar
    # ------------------------------------------------------------------

    async def get_calendar_events(
        self,
        access_token: str,
        time_min: datetime,
        time_max: datetime,
    ) -> list[dict]:
        """Retrieve Outlook calendar events within a time range.

        Uses the ``/me/calendarview`` endpoint with ``$select`` to fetch only
        the fields needed for meeting-link detection and display.  Follows
        ``@odata.nextLink`` for pagination.

        Args:
            access_token: A valid Microsoft Graph access token.
            time_min: Start of the window (inclusive, UTC).
            time_max: End of the window (exclusive, UTC).

        Returns:
            A list of calendar event dicts.
        """
        headers = self._auth_headers(access_token)
        params: dict[str, str] = {
            "startDateTime": time_min.isoformat(),
            "endDateTime": time_max.isoformat(),
            "$select": CALENDAR_SELECT_FIELDS,
            "$orderby": "start/dateTime",
            "$top": "50",
        }

        all_events: list[dict] = []
        url: str | None = f"{BASE_URL}/me/calendarview"

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                while url is not None:
                    resp = await client.get(url, params=params, headers=headers)
                    if resp.status_code != 200:
                        self._raise_for_graph_error(resp)

                    data = resp.json()
                    all_events.extend(data.get("value", []))

                    # Follow pagination link; params are embedded in the URL
                    url = data.get("@odata.nextLink")
                    params = {}  # nextLink already includes query params

        except GraphApiError:
            raise
        except httpx.RequestError as exc:
            logger.error("graph_request_error", endpoint="calendarview", error=str(exc))
            raise

        logger.info("graph_calendar_events_fetched", count=len(all_events))
        return all_events

    async def create_calendar_event(self, access_token: str, event: dict) -> dict:
        """Create a new Outlook calendar event.

        Args:
            access_token: A valid Microsoft Graph access token.
            event: Event payload dict with at minimum ``subject``, ``start``,
                ``end``, and optionally ``body``, ``attendees``, etc.

        Returns:
            The created event dict as returned by the Graph API.
        """
        headers = self._auth_headers(access_token)
        url = f"{BASE_URL}/me/events"

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(url, json=event, headers=headers)
                if resp.status_code not in (200, 201):
                    self._raise_for_graph_error(resp)
                data = resp.json()
        except GraphApiError:
            raise
        except httpx.RequestError as exc:
            logger.error("graph_request_error", endpoint="create_event", error=str(exc))
            raise

        logger.info("graph_calendar_event_created", event_id=data.get("id"))
        return data

    # ------------------------------------------------------------------
    # User profile
    # ------------------------------------------------------------------

    async def get_user_profile(self, access_token: str) -> dict:
        """Retrieve the authenticated user's profile from Microsoft Graph.

        Args:
            access_token: A valid Microsoft Graph access token.

        Returns:
            A dict with user profile fields (``displayName``, ``mail``, etc.).
        """
        headers = self._auth_headers(access_token)
        url = f"{BASE_URL}/me"

        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(url, headers=headers)
                if resp.status_code != 200:
                    self._raise_for_graph_error(resp)
                data = resp.json()
        except GraphApiError:
            raise
        except httpx.RequestError as exc:
            logger.error("graph_request_error", endpoint="me", error=str(exc))
            raise

        logger.info("graph_user_profile_fetched", user_id=data.get("id"))
        return data
