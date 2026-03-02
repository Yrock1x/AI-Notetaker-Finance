from __future__ import annotations


class ZoomMeetingBot:
    """Bot that joins and records Zoom meetings."""

    async def join_meeting(self, meeting_id: str, passcode: str | None = None) -> None:
        """Join a Zoom meeting by meeting ID and optional passcode."""
        raise NotImplementedError

    async def start_recording(self) -> None:
        """Start recording audio from the active Zoom meeting."""
        raise NotImplementedError

    async def stop_recording(self) -> bytes:
        """Stop recording and return the captured audio data."""
        raise NotImplementedError

    async def leave_meeting(self) -> None:
        """Leave the active Zoom meeting."""
        raise NotImplementedError

    async def send_chat_message(self, message: str) -> None:
        """Send a chat message in the active Zoom meeting."""
        raise NotImplementedError
