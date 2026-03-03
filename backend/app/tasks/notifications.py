"""Celery tasks for sending notifications via Slack and other channels.

Tasks run in the ``notifications`` queue and use ``_run_async`` to bridge
from Celery's synchronous execution model to the async integration clients.
"""

import asyncio
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.integrations.slack.notifications import SlackNotifier
from app.services.integration_service import IntegrationService
from app.tasks.base import BaseTask
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    """Run an async coroutine in a fresh event loop for Celery workers."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(base=BaseTask, bind=True, queue="notifications")
def send_completion_notification(
    self, meeting_id: str, event_type: str = "meeting_processed"
) -> None:
    """Send notification when processing completes -- dispatches to available channels.

    Attempts to look up the organisation's Slack integration credentials. If a
    Slack bot token is configured, a rich meeting-completion message is posted
    to the configured channel.  Otherwise the event is logged for future
    channel implementations (email, WebSocket push, etc.).
    """
    logger.info(
        "completion_notification",
        meeting_id=meeting_id,
        event_type=event_type,
    )

    async def _notify():
        settings = get_settings()
        async with async_session_factory() as session:
            try:
                # Retrieve the meeting record to build the notification payload
                from app.models.meeting import Meeting
                from sqlalchemy import select

                result = await session.execute(
                    select(Meeting).where(Meeting.id == UUID(meeting_id))
                )
                meeting = result.scalar_one_or_none()
                if meeting is None:
                    logger.warning(
                        "completion_notification_meeting_not_found",
                        meeting_id=meeting_id,
                    )
                    return

                # Try to find a Slack integration for the meeting's org
                integration_svc = IntegrationService(session, settings)
                # Query for any active Slack credential in this org
                from app.models.integration_credential import IntegrationCredential
                from sqlalchemy import and_

                cred_result = await session.execute(
                    select(IntegrationCredential).where(
                        and_(
                            IntegrationCredential.org_id == meeting.org_id,
                            IntegrationCredential.platform == "slack",
                            IntegrationCredential.is_active.is_(True),
                        )
                    )
                )
                credential = cred_result.scalars().first()

                if credential is None:
                    logger.info(
                        "completion_notification_no_slack",
                        meeting_id=meeting_id,
                        org_id=str(meeting.org_id),
                        detail="No active Slack integration found; skipping Slack notification",
                    )
                    return

                # Decrypt the bot token and send the notification
                bot_token = integration_svc._decrypt_token(
                    credential.access_token_encrypted
                )
                notifier = SlackNotifier(bot_token)

                meeting_data = {
                    "title": getattr(meeting, "title", "Untitled Meeting"),
                    "deal_name": getattr(meeting, "deal_name", "N/A"),
                    "date": (
                        meeting.created_at.strftime("%Y-%m-%d %H:%M UTC")
                        if hasattr(meeting, "created_at") and meeting.created_at
                        else "N/A"
                    ),
                    "duration_minutes": getattr(meeting, "duration_minutes", None),
                    "participant_count": getattr(meeting, "participant_count", 0),
                    "segment_count": getattr(meeting, "segment_count", 0),
                    "status": event_type,
                    "meeting_id": meeting_id,
                }

                # Use the channel from credential metadata, or fall back to #general
                channel = (
                    credential.metadata_.get("channel", "#general")
                    if hasattr(credential, "metadata_") and credential.metadata_
                    else "#general"
                )

                await notifier.send_meeting_complete(channel, meeting_data)
                logger.info(
                    "completion_notification_sent",
                    meeting_id=meeting_id,
                    channel=channel,
                )

            except Exception:
                logger.exception(
                    "completion_notification_error",
                    meeting_id=meeting_id,
                )

    _run_async(_notify())


@celery_app.task(base=BaseTask, bind=True, queue="notifications")
def send_slack_notification(
    self, org_id: str, channel: str, message: dict
) -> None:
    """Send a message to a Slack channel for an org.

    Looks up the org's Slack credentials, decrypts the bot token, and
    dispatches the message via :class:`SlackNotifier`.

    Args:
        org_id: Organisation UUID string.
        channel: Slack channel ID or name.
        message: Dict with ``blocks`` (list[dict]) and/or ``text`` (str).
    """

    async def _send():
        settings = get_settings()
        async with async_session_factory() as session:
            try:
                integration_svc = IntegrationService(session, settings)

                # Find an active Slack credential for this org
                from app.models.integration_credential import IntegrationCredential
                from sqlalchemy import and_, select

                cred_result = await session.execute(
                    select(IntegrationCredential).where(
                        and_(
                            IntegrationCredential.org_id == UUID(org_id),
                            IntegrationCredential.platform == "slack",
                            IntegrationCredential.is_active.is_(True),
                        )
                    )
                )
                credential = cred_result.scalars().first()

                if credential is None:
                    logger.warning(
                        "slack_notification_no_credential",
                        org_id=org_id,
                        channel=channel,
                    )
                    return

                bot_token = integration_svc._decrypt_token(
                    credential.access_token_encrypted
                )
                notifier = SlackNotifier(bot_token)

                blocks = message.get("blocks", [])
                text = message.get("text", "")

                if blocks:
                    await notifier.send_message(channel, blocks)
                elif text:
                    await notifier._app.post_message(channel, text=text)
                else:
                    logger.warning(
                        "slack_notification_empty_message",
                        org_id=org_id,
                        channel=channel,
                    )
                    return

                logger.info(
                    "slack_notification_sent",
                    org_id=org_id,
                    channel=channel,
                )

            except Exception:
                logger.exception(
                    "slack_notification_error",
                    org_id=org_id,
                    channel=channel,
                )

    _run_async(_send())
