"""Slack event and slash-command handler.

Processes incoming Slack events (messages, interactions) and routes slash
commands to the appropriate sub-handlers.  Message content is intentionally
**not** logged to avoid leaking sensitive deal information.

Slash-command sub-handlers query the SQLite store for live data when the
handler is constructed with a DB session + a resolved org_id (the caller is
responsible for mapping the Slack team_id to a CogniSuite org via the
``integration_credentials`` table). Without those, the handler returns an
honest "not configured" message instead of fabricating empty data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = structlog.get_logger(__name__)

# Help text returned for the /cognisuite help command (or when no subcommand is given)
HELP_TEXT = (
    "*CogniSuite Slash Commands*\n"
    "`/cognisuite help` - Show this help message\n"
    "`/cognisuite status` - Show current processing status\n"
    "`/cognisuite meetings` - List recent meetings\n"
)

_NOT_CONFIGURED = (
    "*Slack integration not finished*\n"
    "Slash commands need a connected CogniSuite workspace. Ask an admin to "
    "finish the Slack connection from the *Integrations* page in the app."
)

_PROCESSING_STATUSES = ("uploaded", "transcribing", "diarizing", "analyzing")


class SlackEventHandler:
    """Handles incoming Slack events and slash commands."""

    def __init__(
        self,
        session: Session | None = None,
        org_id: str | None = None,
    ) -> None:
        # When both are supplied the slash-command sub-handlers run real
        # queries against the SQLite store (scoped to org_id here). When
        # either is missing they return _NOT_CONFIGURED.
        self._session = session
        self._org_id = org_id

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
            command: The slash command name (e.g. ``/cognisuite``).
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
        """Return the current processing status."""
        if not self._session or not self._org_id:
            return {"response_type": "ephemeral", "text": _NOT_CONFIGURED}

        try:
            from sqlalchemy import select

            from app.db.models import Meeting

            rows = self._session.scalars(
                select(Meeting)
                .where(Meeting.org_id == self._org_id)
                .where(Meeting.status.in_(list(_PROCESSING_STATUSES)))
                .order_by(Meeting.created_at.desc())
                .limit(10)
            ).all()
        except Exception:
            logger.exception("slack_status_query_failed")
            return {
                "response_type": "ephemeral",
                "text": "Couldn't reach the meeting database. Try again shortly.",
            }

        if not rows:
            return {
                "response_type": "ephemeral",
                "text": (
                    "*Processing Status*\n"
                    "No meetings are currently being processed.\n"
                    "Use `/cognisuite meetings` to see recent meetings."
                ),
            }

        lines = ["*Processing Status*"]
        for r in rows:
            title = r.title or "Untitled meeting"
            lines.append(f"• `{r.status}` — {title}")
        return {"response_type": "ephemeral", "text": "\n".join(lines)}

    async def _handle_meetings(self, args: str, payload: dict) -> dict:
        """Return a list of recent meetings."""
        if not self._session or not self._org_id:
            return {"response_type": "ephemeral", "text": _NOT_CONFIGURED}

        try:
            from sqlalchemy import select

            from app.db.models import Meeting

            rows = self._session.scalars(
                select(Meeting)
                .where(Meeting.org_id == self._org_id)
                .order_by(Meeting.created_at.desc())
                .limit(10)
            ).all()
        except Exception:
            logger.exception("slack_meetings_query_failed")
            return {
                "response_type": "ephemeral",
                "text": "Couldn't reach the meeting database. Try again shortly.",
            }

        if not rows:
            return {
                "response_type": "ephemeral",
                "text": (
                    "*Recent Meetings*\n"
                    "No meetings found. Upload a recording or schedule a bot to get started."
                ),
            }

        lines = ["*Recent Meetings*"]
        for r in rows:
            title = r.title or "Untitled meeting"
            when = r.meeting_date or r.created_at or ""
            lines.append(f"• {title} — `{r.status or '?'}` ({when[:10]})")
        return {"response_type": "ephemeral", "text": "\n".join(lines)}

    # Map of subcommand names to handler methods
    _SUBCOMMAND_MAP: dict = {
        "help": _handle_help,
        "status": _handle_status,
        "meetings": _handle_meetings,
    }
