"""Handler for incoming Microsoft Teams / Graph webhook notifications.

Graph API subscriptions deliver change notifications via POST to a registered
webhook URL.  This module routes those events to the appropriate handlers.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


class TeamsWebhookHandler:
    """Handles incoming Microsoft Teams webhook events."""

    async def handle_event(self, event_type: str, payload: dict) -> None:
        """Process an incoming Teams webhook event.

        Routes to a specific handler based on ``event_type``.  Unknown event
        types are logged and silently ignored so new Graph notification types
        do not cause errors.
        """
        logger.info("teams_webhook_received", event_type=event_type)

        handler = self._get_handler(event_type)
        if handler is not None:
            await handler(payload)
        else:
            logger.debug(
                "teams_webhook_unhandled_event",
                event_type=event_type,
            )

    # ------------------------------------------------------------------
    # Event routing
    # ------------------------------------------------------------------

    def _get_handler(self, event_type: str):  # noqa: ANN202
        """Return the handler coroutine for *event_type*, or ``None``."""
        handlers = {
            "callRecord": self._handle_call_record,
            "chatMessage": self._handle_chat_message,
        }
        return handlers.get(event_type)

    # ------------------------------------------------------------------
    # Individual event handlers
    # ------------------------------------------------------------------

    async def _handle_call_record(self, payload: dict) -> None:
        """Handle a ``callRecord`` notification.

        Triggered when a Teams call ends and the call record is available.
        This is the primary entry point for kicking off post-meeting
        transcription and analysis pipelines.
        """
        call_record_id = payload.get("resourceData", {}).get("id", "unknown")
        logger.info(
            "teams_call_record_received",
            call_record_id=call_record_id,
            change_type=payload.get("changeType"),
        )

        # TODO: Trigger the Celery processing pipeline once the task
        # infrastructure is wired:
        #   from app.tasks.pipeline import process_teams_call_record
        #   process_teams_call_record.delay(call_record_id=call_record_id)

    async def _handle_chat_message(self, payload: dict) -> None:
        """Handle a ``chatMessage`` notification.

        Currently only logs the event.  Could be extended to support
        slash-command interactions within Teams chat.
        """
        resource = payload.get("resource", "")
        logger.info(
            "teams_chat_message_received",
            resource=resource,
            change_type=payload.get("changeType"),
        )
