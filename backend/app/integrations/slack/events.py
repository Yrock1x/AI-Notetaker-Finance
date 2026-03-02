from __future__ import annotations


class SlackEventHandler:
    """Handles incoming Slack events and slash commands."""

    async def handle_message(self, event: dict) -> None:
        """Process an incoming Slack message event."""
        raise NotImplementedError

    async def handle_command(self, command: str, payload: dict) -> dict:
        """Process a Slack slash command and return a response."""
        raise NotImplementedError
