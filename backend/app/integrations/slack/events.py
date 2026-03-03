"""Slack event and slash-command handler.

Processes incoming Slack events (messages, interactions) and routes slash
commands to the appropriate sub-handlers.  Message content is intentionally
**not** logged to avoid leaking sensitive deal information.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Help text returned for the /dealwise help command (or when no subcommand is given)
HELP_TEXT = (
    "*Deal Companion Slash Commands*\n"
    "`/dealwise help` - Show this help message\n"
    "`/dealwise status` - Show current processing status\n"
    "`/dealwise meetings` - List recent meetings\n"
)


class SlackEventHandler:
    """Handles incoming Slack events and slash commands."""

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def handle_message(self, event: dict) -> None:
        """Process an incoming Slack message event.

        Logs the channel and event type for observability but **never** logs
        the message text itself to avoid exposing confidential deal content.
        """
        channel = event.get("channel", "unknown")
        user = event.get("user", "unknown")
        event_type = event.get("type", "message")
        subtype = event.get("subtype")

        logger.info(
            "slack_message_received",
            channel=channel,
            user=user,
            event_type=event_type,
            subtype=subtype,
        )

    # ------------------------------------------------------------------
    # Slash-command routing
    # ------------------------------------------------------------------

    async def handle_command(self, command: str, payload: dict) -> dict:
        """Process a Slack slash command and return a response.

        Routes to sub-handlers based on the first word of the command text.
        All responses use ``response_type="ephemeral"`` so they are only
        visible to the invoking user.

        Args:
            command: The slash command name (e.g. ``/dealwise``).
            payload: The full Slack command payload dict.

        Returns:
            A dict suitable for returning as an immediate slash-command response.
        """
        text = payload.get("text", "").strip()
        parts = text.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1] if len(parts) > 1 else ""

        logger.info(
            "slack_command_received",
            command=command,
            subcommand=subcommand,
            user=payload.get("user_id", "unknown"),
            channel=payload.get("channel_id", "unknown"),
        )

        handler = self._SUBCOMMAND_MAP.get(subcommand, self._handle_help)
        return await handler(self, args, payload)

    # ------------------------------------------------------------------
    # Subcommand handlers
    # ------------------------------------------------------------------

    async def _handle_help(self, args: str, payload: dict) -> dict:
        """Return help text listing available commands."""
        return {
            "response_type": "ephemeral",
            "text": HELP_TEXT,
        }

    async def _handle_status(self, args: str, payload: dict) -> dict:
        """Return the current processing status.

        In a full implementation this would query the database for active
        processing jobs. For now it returns a placeholder.
        """
        return {
            "response_type": "ephemeral",
            "text": (
                "*Processing Status*\n"
                "No meetings are currently being processed.\n"
                "Use `/dealwise meetings` to see recent meetings."
            ),
        }

    async def _handle_meetings(self, args: str, payload: dict) -> dict:
        """Return a list of recent meetings.

        In a full implementation this would query the database for the
        org's recent meetings. For now it returns a placeholder.
        """
        return {
            "response_type": "ephemeral",
            "text": (
                "*Recent Meetings*\n"
                "No meetings found. Upload a recording or schedule a bot to get started."
            ),
        }

    # Map of subcommand names to handler methods
    _SUBCOMMAND_MAP: dict = {
        "help": _handle_help,
        "status": _handle_status,
        "meetings": _handle_meetings,
    }
