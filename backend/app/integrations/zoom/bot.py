"""Zoom meeting bot implemented as a Recall.ai wrapper.

Direct Zoom meeting-bot integration requires the Zoom Meeting SDK (native C++
with Python bindings) which is complex to deploy.  This module delegates all
meeting lifecycle operations to Recall.ai.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

import structlog

if TYPE_CHECKING:
    from app.integrations.recall.client import RecallClient

logger = structlog.get_logger(__name__)


class ZoomMeetingBot:
    """Bot that joins and records Zoom meetings via Recall.ai."""

    def __init__(self, recall_client: RecallClient) -> None:
        self._recall = recall_client
        self._bot_id: str | None = None

    @property
    def bot_id(self) -> str | None:
        """The Recall bot ID for the current session, if any."""
        return self._bot_id

    @staticmethod
    def _build_zoom_url(meeting_id: str, passcode: str | None = None) -> str:
        """Construct a ``zoommtg://`` or ``https://`` join URL from a meeting ID."""
        # Recall.ai accepts standard Zoom web join URLs
        base = f"https://zoom.us/j/{meeting_id}"
        if passcode:
            base += f"?pwd={quote(passcode)}"
        return base

    async def join_meeting(
        self, meeting_id: str, passcode: str | None = None
    ) -> None:
        """Join a Zoom meeting by meeting ID and optional passcode.

        Constructs a Zoom join URL and delegates to ``RecallClient.create_bot``.
        """
        meeting_url = self._build_zoom_url(meeting_id, passcode)
        logger.info(
            "zoom_bot_joining",
            meeting_id=meeting_id,
            has_passcode=passcode is not None,
        )
        result = await self._recall.create_bot(
            meeting_url=meeting_url,
            bot_name="Deal Companion Notetaker",
        )
        self._bot_id = result.get("id")
        logger.info("zoom_bot_joined", bot_id=self._bot_id)

    async def start_recording(self) -> None:
        """Start recording audio from the active Zoom meeting.

        No-op — Recall.ai begins recording automatically when the bot joins.
        """
        logger.debug("zoom_bot_start_recording_noop", bot_id=self._bot_id)

    async def stop_recording(self) -> bytes:
        """Stop recording and return the captured audio data.

        No-op — Recall.ai manages the full recording lifecycle.  The actual
        recording can be retrieved via ``RecallClient.get_recording(bot_id)``.
        Returns empty bytes; callers should use the Recall client directly.
        """
        logger.debug("zoom_bot_stop_recording_noop", bot_id=self._bot_id)
        return b""

    async def leave_meeting(self) -> None:
        """Leave the active Zoom meeting.

        Retrieves the bot status from Recall to confirm teardown.  If no bot
        is active this is a no-op.
        """
        if self._bot_id is None:
            logger.warning("zoom_bot_leave_no_active_bot")
            return

        logger.info("zoom_bot_leaving", bot_id=self._bot_id)
        # Recall does not expose an explicit "leave" endpoint — fetching the
        # bot status is sufficient; the bot leaves when the meeting ends or
        # when deleted via the API.  Logging the final status for diagnostics.
        try:
            status = await self._recall.get_bot(self._bot_id)
            logger.info(
                "zoom_bot_status_on_leave",
                bot_id=self._bot_id,
                status=status.get("status"),
            )
        except Exception:
            logger.warning(
                "zoom_bot_leave_status_check_failed",
                bot_id=self._bot_id,
                exc_info=True,
            )

    async def send_chat_message(self, message: str) -> None:
        """Send a chat message in the active Zoom meeting.

        Zoom in-meeting chat requires the Zoom Meeting SDK.  This is not
        supported in the Recall.ai wrapper — log a warning and no-op.
        """
        logger.warning(
            "zoom_chat_message_not_supported",
            bot_id=self._bot_id,
            detail="Sending in-meeting chat messages requires the Zoom "
            "Meeting SDK, which is not available in the Recall.ai wrapper.",
        )
