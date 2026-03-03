"""Slack app client for API operations.

Wraps the Slack Web API using httpx for async HTTP calls. All methods
validate the ``ok`` field in Slack's response envelope and raise on errors.
"""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger(__name__)

SLACK_API_BASE = "https://slack.com/api"
DEFAULT_TIMEOUT = 30.0


class SlackApiError(Exception):
    """Raised when the Slack API returns ok=false."""

    def __init__(self, method: str, error: str, data: dict | None = None) -> None:
        self.method = method
        self.error = error
        self.data = data or {}
        super().__init__(f"Slack API error on {method}: {error}")


class SlackApp:
    """Slack app client for API operations."""

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token
        self._headers = {
            "Authorization": f"Bearer {bot_token}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _post(self, method: str, payload: dict | None = None) -> dict:
        """Send a POST request to a Slack API method and return the parsed response."""
        url = f"{SLACK_API_BASE}/{method}"
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.post(url, json=payload or {}, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("slack_http_error", method=method, status=exc.response.status_code)
            raise
        except httpx.RequestError as exc:
            logger.error("slack_request_error", method=method, error=str(exc))
            raise

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            logger.warning("slack_api_error", method=method, error=error)
            raise SlackApiError(method=method, error=error, data=data)

        return data

    async def _get(self, method: str, params: dict | None = None) -> dict:
        """Send a GET request to a Slack API method and return the parsed response."""
        url = f"{SLACK_API_BASE}/{method}"
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                resp = await client.get(url, params=params or {}, headers=self._headers)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("slack_http_error", method=method, status=exc.response.status_code)
            raise
        except httpx.RequestError as exc:
            logger.error("slack_request_error", method=method, error=str(exc))
            raise

        if not data.get("ok"):
            error = data.get("error", "unknown_error")
            logger.warning("slack_api_error", method=method, error=error)
            raise SlackApiError(method=method, error=error, data=data)

        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    async def post_message(
        self,
        channel: str,
        text: str = "",
        blocks: list[dict] | None = None,
    ) -> dict:
        """Post a message to a Slack channel using chat.postMessage API.

        Args:
            channel: Channel ID or name to post to.
            text: Fallback plain-text content (also used for notifications).
            blocks: Optional Block Kit blocks for rich formatting.

        Returns:
            The full Slack API response dict (contains ``ts``, ``channel``, etc.).
        """
        payload: dict = {"channel": channel}
        if text:
            payload["text"] = text
        if blocks:
            payload["blocks"] = blocks
            # Slack requires a text fallback when blocks are provided
            if not text:
                payload["text"] = "New notification from Deal Companion"

        data = await self._post("chat.postMessage", payload)
        logger.info(
            "slack_message_posted",
            channel=channel,
            ts=data.get("ts"),
        )
        return data

    async def get_channel_info(self, channel_id: str) -> dict:
        """Get info about a Slack channel.

        Args:
            channel_id: The Slack channel ID.

        Returns:
            The channel info dict from Slack's ``conversations.info`` response.
        """
        data = await self._get("conversations.info", params={"channel": channel_id})
        return data.get("channel", {})

    async def list_channels(self, limit: int = 100) -> list[dict]:
        """List channels the bot has access to.

        Handles cursor-based pagination to collect up to ``limit`` channels.

        Args:
            limit: Maximum number of channels to return.

        Returns:
            A list of channel dicts.
        """
        all_channels: list[dict] = []
        cursor: str | None = None

        while len(all_channels) < limit:
            page_size = min(limit - len(all_channels), 200)
            params: dict = {
                "limit": page_size,
                "exclude_archived": "true",
                "types": "public_channel,private_channel",
            }
            if cursor:
                params["cursor"] = cursor

            data = await self._get("conversations.list", params=params)
            channels = data.get("channels", [])
            all_channels.extend(channels)

            # Check for pagination
            next_cursor = data.get("response_metadata", {}).get("next_cursor", "")
            if not next_cursor or not channels:
                break
            cursor = next_cursor

        return all_channels[:limit]

    async def test_auth(self) -> dict:
        """Test that the bot token is valid.

        Returns:
            A dict with ``user_id``, ``team_id``, ``bot_id``, etc.
        """
        data = await self._post("auth.test")
        logger.info(
            "slack_auth_verified",
            team=data.get("team"),
            user=data.get("user"),
            bot_id=data.get("bot_id"),
        )
        return data
