"""Recall.ai API client for meeting bot management.

When no API key is configured, all methods return demo/mock data so the
application can run in demo mode without a real Recall.ai account.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import structlog

logger = structlog.get_logger(__name__)

BASE_URL = "https://api.recall.ai/api/v1"


class RecallClient:
    """Thin async wrapper around the Recall.ai REST API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._headers = (
            {"Authorization": f"Token {api_key}", "Content-Type": "application/json"}
            if api_key
            else {}
        )

    @property
    def is_demo(self) -> bool:
        return not self._api_key

    # ------------------------------------------------------------------
    # Bot lifecycle
    # ------------------------------------------------------------------

    async def create_bot(
        self,
        meeting_url: str,
        bot_name: str = "Deal Companion Notetaker",
        *,
        transcription_provider: str = "default",
    ) -> dict:
        """Create a bot that joins the given meeting URL."""
        if self.is_demo:
            return self._mock_bot(meeting_url, bot_name)

        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                "meeting_url": meeting_url,
                "bot_name": bot_name,
                "real_time_transcription": {
                    "destination_url": "",
                    "partial_results": False,
                },
            }
            resp = await client.post(
                f"{BASE_URL}/bot", json=payload, headers=self._headers
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info("recall_bot_created", bot_id=data.get("id"))
            return data

    async def get_bot(self, bot_id: str) -> dict:
        """Get bot status."""
        if self.is_demo:
            return self._mock_bot_status(bot_id)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/bot/{bot_id}", headers=self._headers
            )
            resp.raise_for_status()
            return resp.json()

    async def list_bots(self) -> list[dict]:
        """List all bots."""
        if self.is_demo:
            return []

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/bot", headers=self._headers)
            resp.raise_for_status()
            return resp.json().get("results", [])

    async def get_transcript(self, bot_id: str) -> list[dict]:
        """Get transcript for a completed bot session."""
        if self.is_demo:
            return self._mock_transcript()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/bot/{bot_id}/transcript", headers=self._headers
            )
            resp.raise_for_status()
            return resp.json()

    async def get_recording(self, bot_id: str) -> dict | None:
        """Get recording URL for a completed bot session."""
        if self.is_demo:
            return {"url": "#", "content_type": "video/mp4"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{BASE_URL}/bot/{bot_id}/recording", headers=self._headers
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Demo / mock helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _mock_bot(meeting_url: str, bot_name: str) -> dict:
        return {
            "id": str(uuid.uuid4()),
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "status": {"code": "ready", "message": "Bot created (demo mode)"},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _mock_bot_status(bot_id: str) -> dict:
        return {
            "id": bot_id,
            "status": {"code": "done", "message": "Recording complete (demo)"},
        }

    @staticmethod
    def _mock_transcript() -> list[dict]:
        return [
            {
                "speaker": "Speaker 1",
                "words": [
                    {"text": "Thank you for joining today's call.", "start_time": 0.0, "end_time": 2.5}
                ],
            },
            {
                "speaker": "Speaker 2",
                "words": [
                    {"text": "Thanks for having us. Let's walk through the financials.", "start_time": 3.0, "end_time": 6.0}
                ],
            },
            {
                "speaker": "Speaker 1",
                "words": [
                    {"text": "Starting with revenue, we saw 35 percent year-over-year growth.", "start_time": 7.0, "end_time": 11.0}
                ],
            },
        ]
