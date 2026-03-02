from __future__ import annotations


class TeamsWebhookHandler:
    """Handles incoming Microsoft Teams webhook events."""

    async def handle_event(self, event_type: str, payload: dict) -> None:
        """Process an incoming Teams webhook event."""
        raise NotImplementedError
