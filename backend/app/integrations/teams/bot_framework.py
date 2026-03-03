"""Teams meeting bot implemented as a Recall.ai wrapper.

Actual Bot Framework SDK integration is complex and requires a dedicated
Azure Bot Service registration.  This module delegates meeting join /
recording to the Recall.ai bot API, which handles the underlying WebRTC
plumbing for all supported platforms.
"""

from __future__ import annotations

from typing import Optional

import structlog

from app.integrations.recall.client import RecallClient

logger = structlog.get_logger(__name__)


class TeamsMeetingBot:
    """Bot that joins and records Microsoft Teams meetings via Recall.ai."""

    def __init__(self, recall_client: RecallClient) -> None:
        self._recall = recall_client
        self._bot_id: Optional[str] = None

    @property
    def bot_id(self) -> Optional[str]:
        """The Recall bot ID for the current session, if any."""
        return self._bot_id

    async def join_meeting(self, meeting_url: str) -> None:
        """Join a Teams meeting using the meeting URL.

        Delegates to Recall.ai ``create_bot`` which will spawn a bot that
        joins the Teams meeting, handles consent, and begins capturing audio.
        """
        logger.info("teams_bot_joining", meeting_url=meeting_url)
        result = await self._recall.create_bot(
            meeting_url=meeting_url,
            bot_name="Deal Companion Notetaker",
        )
        self._bot_id = result.get("id")
        logger.info("teams_bot_joined", bot_id=self._bot_id)

    async def start_recording(self) -> None:
        """Start recording audio from the active Teams meeting.

        This is a no-op because Recall.ai begins recording automatically
        when the bot joins the meeting.
        """
        logger.debug("teams_bot_start_recording_noop", bot_id=self._bot_id)

    async def stop_recording(self) -> bytes:
        """Stop recording and return the captured audio data.

        This is a no-op because Recall.ai manages the recording lifecycle.
        The actual recording can be retrieved via
        ``RecallClient.get_recording(bot_id)``.
        Returns empty bytes — callers should use the Recall client directly
        for recording retrieval.
        """
        logger.debug("teams_bot_stop_recording_noop", bot_id=self._bot_id)
        return b""

    async def send_adaptive_card(self, card: dict) -> None:
        """Send an Adaptive Card message in the active Teams meeting.

        Adaptive Cards require a full Bot Framework SDK registration and
        Azure Bot Service.  This method logs a warning and is a no-op in
        the Recall.ai wrapper implementation.
        """
        logger.warning(
            "teams_adaptive_card_not_supported",
            bot_id=self._bot_id,
            detail="Sending Adaptive Cards requires the Bot Framework SDK "
            "and an Azure Bot Service registration. This is not supported "
            "in the Recall.ai wrapper implementation.",
        )
