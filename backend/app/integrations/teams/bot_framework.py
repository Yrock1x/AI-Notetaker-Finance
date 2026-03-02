from __future__ import annotations


class TeamsMeetingBot:
    """Bot that joins and records Microsoft Teams meetings."""

    async def join_meeting(self, meeting_url: str) -> None:
        """Join a Teams meeting using the meeting URL."""
        raise NotImplementedError

    async def start_recording(self) -> None:
        """Start recording audio from the active Teams meeting."""
        raise NotImplementedError

    async def stop_recording(self) -> bytes:
        """Stop recording and return the captured audio data."""
        raise NotImplementedError

    async def send_adaptive_card(self, card: dict) -> None:
        """Send an Adaptive Card message in the active Teams meeting."""
        raise NotImplementedError
