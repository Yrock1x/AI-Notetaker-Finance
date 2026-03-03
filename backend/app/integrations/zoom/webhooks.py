"""Handler for incoming Zoom webhook events.

Zoom signs webhook payloads with HMAC-SHA256 using the ``webhook_secret_token``
configured in the Zoom Marketplace app.  This module verifies signatures and
routes events to the appropriate handlers.
"""

from __future__ import annotations

import hashlib
import hmac

import structlog

logger = structlog.get_logger(__name__)


class ZoomWebhookHandler:
    """Handles incoming Zoom webhook events."""

    def __init__(self, webhook_secret_token: str) -> None:
        """Initialize with the Zoom webhook secret token for signature verification."""
        self._secret = webhook_secret_token

    def verify_signature(
        self, payload: bytes, signature: str, timestamp: str
    ) -> bool:
        """Verify the authenticity of a Zoom webhook payload signature.

        Zoom computes the signature as::

            HMAC-SHA256(secret, "v0:{timestamp}:{payload}")

        and sends it in the ``x-zm-signature`` header prefixed with ``v0=``.
        """
        message = f"v0:{timestamp}:{payload.decode()}"
        expected_sig = hmac.new(
            self._secret.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        expected = f"v0={expected_sig}"
        is_valid = hmac.compare_digest(expected, signature)

        if not is_valid:
            logger.warning(
                "zoom_webhook_signature_invalid",
                expected_prefix=expected[:16] + "...",
                received_prefix=signature[:16] + "...",
            )

        return is_valid

    async def handle_event(self, event_type: str, payload: dict) -> None:
        """Process an incoming Zoom webhook event.

        Routes to a handler based on ``event_type``.  Unknown events are
        logged and silently ignored.
        """
        logger.info("zoom_webhook_received", event_type=event_type)

        handler = self._get_handler(event_type)
        if handler is not None:
            await handler(payload)
        else:
            logger.debug("zoom_webhook_unhandled_event", event_type=event_type)

    # ------------------------------------------------------------------
    # Event routing
    # ------------------------------------------------------------------

    def _get_handler(self, event_type: str):  # noqa: ANN202
        """Return the handler coroutine for *event_type*, or ``None``."""
        handlers = {
            "recording.completed": self._handle_recording_completed,
            "meeting.ended": self._handle_meeting_ended,
            "meeting.started": self._handle_meeting_started,
            "endpoint.url_validation": self._handle_url_validation,
        }
        return handlers.get(event_type)

    # ------------------------------------------------------------------
    # Individual event handlers
    # ------------------------------------------------------------------

    async def _handle_recording_completed(self, payload: dict) -> None:
        """Handle ``recording.completed`` — a cloud recording is ready.

        This is the primary trigger for kicking off the transcription /
        analysis pipeline.
        """
        meeting_id = payload.get("object", {}).get("id", "unknown")
        recording_files = payload.get("object", {}).get("recording_files", [])
        logger.info(
            "zoom_recording_completed",
            meeting_id=meeting_id,
            file_count=len(recording_files),
        )

        # TODO: Trigger the Celery processing pipeline:
        #   from app.tasks.pipeline import process_zoom_recording
        #   process_zoom_recording.delay(meeting_id=meeting_id, payload=payload)

    async def _handle_meeting_ended(self, payload: dict) -> None:
        """Handle ``meeting.ended`` — a Zoom meeting has concluded."""
        meeting_id = payload.get("object", {}).get("id", "unknown")
        host_id = payload.get("object", {}).get("host_id", "unknown")
        logger.info(
            "zoom_meeting_ended",
            meeting_id=meeting_id,
            host_id=host_id,
        )

    async def _handle_meeting_started(self, payload: dict) -> None:
        """Handle ``meeting.started`` — a Zoom meeting has begun."""
        meeting_id = payload.get("object", {}).get("id", "unknown")
        logger.info(
            "zoom_meeting_started",
            meeting_id=meeting_id,
        )

    async def _handle_url_validation(self, payload: dict) -> None:
        """Handle ``endpoint.url_validation`` — Zoom CRC challenge.

        Zoom sends this event during webhook endpoint registration.  The
        handler must respond with the ``plainToken`` hashed with the secret.
        Note: the actual HTTP response is typically handled at the route
        level, but we log the event here for diagnostics.
        """
        plain_token = payload.get("plainToken", "")
        logger.info(
            "zoom_url_validation_challenge",
            plain_token_prefix=plain_token[:8] + "..." if plain_token else "",
        )
