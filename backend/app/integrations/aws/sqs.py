from __future__ import annotations


class SQSClient:
    """Client for AWS SQS queue operations."""

    async def send_to_dlq(self, queue_url: str, message: dict) -> None:
        """Send a failed message to the dead-letter queue."""
        raise NotImplementedError
