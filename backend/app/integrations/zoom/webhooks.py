from __future__ import annotations


class ZoomWebhookHandler:
    """Handles incoming Zoom webhook events."""

    def verify_signature(self, payload: bytes, signature: str, timestamp: str) -> bool:
        """Verify the authenticity of a Zoom webhook payload signature."""
        raise NotImplementedError

    async def handle_event(self, event_type: str, payload: dict) -> None:
        """Process an incoming Zoom webhook event."""
        raise NotImplementedError
