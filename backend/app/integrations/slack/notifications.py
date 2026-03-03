"""Slack notification sender with Block Kit formatting.

Builds rich, structured Slack messages for meeting lifecycle events
(completion notifications, processing updates, etc.) using Block Kit.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog

from app.integrations.slack.app import SlackApp

logger = structlog.get_logger(__name__)


class SlackNotifier:
    """Sends notifications and messages to Slack channels."""

    def __init__(self, bot_token: str) -> None:
        """Initialize the Slack notifier with a bot token."""
        self.bot_token = bot_token
        self._app = SlackApp(bot_token)

    async def send_message(self, channel: str, blocks: list[dict]) -> None:
        """Send a Block Kit formatted message to a Slack channel.

        Args:
            channel: Slack channel ID to post to.
            blocks: List of Block Kit block dicts.
        """
        try:
            await self._app.post_message(channel, blocks=blocks)
            logger.info("slack_notification_sent", channel=channel, block_count=len(blocks))
        except Exception:
            logger.exception("slack_notification_failed", channel=channel)
            raise

    async def send_meeting_complete(self, channel: str, meeting: dict) -> None:
        """Send a rich meeting completion notification.

        Args:
            channel: Slack channel ID to post to.
            meeting: Dict containing meeting metadata. Expected keys:
                - title (str): Meeting title/subject.
                - deal_name (str, optional): Associated deal name.
                - date (str, optional): Meeting date string.
                - duration_minutes (int, optional): Meeting duration in minutes.
                - participant_count (int, optional): Number of participants.
                - segment_count (int, optional): Number of transcript segments.
                - status (str, optional): Processing status.
                - meeting_id (str, optional): Meeting ID for deep links.
        """
        blocks = self._build_meeting_complete_blocks(meeting)
        fallback_text = f"Meeting processed: {meeting.get('title', 'Untitled Meeting')}"

        try:
            await self._app.post_message(channel, text=fallback_text, blocks=blocks)
            logger.info(
                "slack_meeting_complete_sent",
                channel=channel,
                meeting_title=meeting.get("title"),
            )
        except Exception:
            logger.exception(
                "slack_meeting_complete_failed",
                channel=channel,
                meeting_title=meeting.get("title"),
            )
            raise

    # ------------------------------------------------------------------
    # Block Kit builders
    # ------------------------------------------------------------------

    def _build_meeting_complete_blocks(self, meeting: dict) -> list[dict]:
        """Build Block Kit blocks for a meeting completion notification.

        Returns a list of Block Kit block dicts that render a structured
        card with meeting metadata and a link to the analysis.
        """
        title = meeting.get("title", "Untitled Meeting")
        deal_name = meeting.get("deal_name", "N/A")
        date = meeting.get("date", "N/A")
        duration = meeting.get("duration_minutes")
        participant_count = meeting.get("participant_count", 0)
        segment_count = meeting.get("segment_count", 0)
        status = meeting.get("status", "processed")
        meeting_id = meeting.get("meeting_id", "")

        duration_text = f"{duration} min" if duration is not None else "N/A"

        blocks: list[dict] = [
            # Header
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Meeting Processed: {title}"[:150],
                    "emoji": True,
                },
            },
            # Deal name, date, and duration
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Deal:*\n{deal_name}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Date:*\n{date}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Duration:*\n{duration_text}",
                    },
                ],
            },
            # Participant count and segment count
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Participants:*\n{participant_count}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Transcript Segments:*\n{segment_count}",
                    },
                ],
            },
            # Status and analysis link
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{status.replace('_', ' ').title()}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"*Analysis:*\n<app://meetings/{meeting_id}|View Details>"
                            if meeting_id
                            else "*Analysis:*\nPending"
                        ),
                    },
                ],
            },
            # Divider
            {"type": "divider"},
            # Timestamp context
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "Deal Companion | "
                            f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}"
                        ),
                    },
                ],
            },
        ]

        return blocks
