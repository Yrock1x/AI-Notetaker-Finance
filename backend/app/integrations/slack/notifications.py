from __future__ import annotations


class SlackNotifier:
    """Sends notifications and messages to Slack channels."""

    def __init__(self, bot_token: str) -> None:
        """Initialize the Slack notifier with a bot token."""
        self.bot_token = bot_token

    async def send_message(self, channel: str, blocks: list[dict]) -> None:
        """Send a Block Kit message to a Slack channel."""
        raise NotImplementedError

    async def send_meeting_complete(self, channel: str, meeting: dict) -> None:
        """Send a meeting completion notification to a Slack channel."""
        raise NotImplementedError
