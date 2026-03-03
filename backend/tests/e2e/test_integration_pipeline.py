"""End-to-end tests for the integration pipeline.

These tests exercise multi-step flows from bot scheduling through recording
completion. All external services (Recall.ai, Deepgram, LLM) are mocked.
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.integrations.deepgram.processor import DiarizationProcessor
from app.integrations.recall.client import RecallClient
from app.models.meeting_bot_session import MeetingBotSession
from app.services.bot_service import BotService


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ZOOM_SECRET = "e2e-zoom-secret"
SLACK_SECRET = "e2e-slack-secret"
TEAMS_SECRET = "e2e-teams-secret"


@pytest.fixture
def e2e_settings() -> Settings:
    """Settings configured for E2E tests."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        app_env="development",
        zoom_webhook_secret_token=ZOOM_SECRET,
        slack_signing_secret=SLACK_SECRET,
        teams_webhook_secret=TEAMS_SECRET,
    )


@pytest.fixture
def e2e_app(e2e_settings: Settings) -> FastAPI:
    """FastAPI app for E2E integration tests."""
    from app.main import create_app
    from app.dependencies import get_db, get_current_user
    from app.models.user import User

    app = create_app()

    mock_user = User(
        id=uuid.uuid4(),
        cognito_sub=f"cognito-{uuid.uuid4()}",
        email="e2e@example.com",
        full_name="E2E User",
        is_active=True,
    )
    mock_user.created_at = datetime.now(timezone.utc)
    mock_user.updated_at = datetime.now(timezone.utc)

    async def override_get_db():
        yield AsyncMock()

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    return app


@pytest.fixture
async def e2e_client(e2e_app: FastAPI) -> AsyncClient:
    """AsyncClient for E2E tests."""
    transport = ASGITransport(app=e2e_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ===========================================================================
# Full Pipeline: Demo Mode
# ===========================================================================


class TestFullPipelineDemoMode:
    """Test the end-to-end pipeline using Recall.ai in demo mode."""

    async def test_full_pipeline_demo_mode(self):
        """In demo mode, RecallClient + DiarizationProcessor should produce valid output without network calls."""
        # Step 1: Create bot in demo mode (no API key)
        recall_client = RecallClient(api_key=None)
        assert recall_client.is_demo is True

        bot = await recall_client.create_bot(
            "https://zoom.us/j/demo-meeting", "Pipeline Test Bot"
        )
        assert "id" in bot
        bot_id = bot["id"]

        # Step 2: Check bot status
        status = await recall_client.get_bot(bot_id)
        assert status["status"]["code"] == "done"

        # Step 3: Get transcript
        transcript = await recall_client.get_transcript(bot_id)
        assert len(transcript) >= 2

        # Step 4: Get recording
        recording = await recall_client.get_recording(bot_id)
        assert recording is not None
        assert recording["content_type"] == "video/mp4"

        # Step 5: Process transcript through DiarizationProcessor
        # Build a Deepgram-shaped response from the Recall transcript
        words = []
        for idx, entry in enumerate(transcript):
            speaker_words = entry.get("words", [])
            for w in speaker_words:
                words.append({
                    "word": w["text"].split()[0] if w["text"] else "",
                    "punctuated_word": w["text"],
                    "speaker": idx,
                    "start": w["start_time"],
                    "end": w["end_time"],
                    "confidence": 0.95,
                })

        deepgram_response = {
            "results": {
                "channels": [{"alternatives": [{"words": words}]}]
            }
        }

        processor = DiarizationProcessor()
        segments = processor.process_response(deepgram_response)
        assert len(segments) >= 1

        participants = processor.extract_participants(segments)
        assert len(participants) >= 1


# ===========================================================================
# Bot Schedule to Completion Flow
# ===========================================================================


class TestBotScheduleToCompletionFlow:
    """Test the bot lifecycle from scheduling through completion."""

    async def test_bot_schedule_to_completion_flow(self):
        """A bot should progress through scheduled -> joining -> recording -> completed."""
        mock_db = AsyncMock()
        mock_db.add = MagicMock()
        mock_db.flush = AsyncMock()

        service = BotService(db=mock_db)

        org_id = uuid.uuid4()
        deal_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Step 1: Schedule
        session = await service.schedule_bot(
            org_id=org_id,
            deal_id=deal_id,
            platform="zoom",
            meeting_url="https://zoom.us/j/lifecycle-test",
            scheduled_start=datetime.now(timezone.utc),
            created_by=user_id,
        )
        assert session.status == "scheduled"
        session_id = session.id

        # Step 2: Transition to joining
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        result = await service.update_bot_status(session_id, "joining")
        assert result.status == "joining"
        assert result.actual_start is None  # Not set until recording

        # Step 3: Transition to recording
        result = await service.update_bot_status(session_id, "recording")
        assert result.status == "recording"
        assert result.actual_start is not None

        # Step 4: Transition to completed
        result = await service.update_bot_status(session_id, "completed")
        assert result.status == "completed"
        assert result.actual_end is not None


# ===========================================================================
# Webhook to Pipeline Trigger
# ===========================================================================


class TestWebhookToPipelineTrigger:
    """Test that webhook events can trigger the processing pipeline."""

    @patch("app.api.v1.webhooks.get_settings")
    async def test_webhook_to_pipeline_trigger(
        self,
        mock_get_settings: MagicMock,
        e2e_client: AsyncClient,
        e2e_settings: Settings,
    ):
        """A Zoom recording.completed webhook should be accepted and could trigger a pipeline.

        This test verifies the full path from HTTP request through signature
        verification to event processing. The actual Celery task trigger is
        a TODO in the codebase, so we verify the endpoint accepts and returns
        success.
        """
        mock_get_settings.return_value = e2e_settings

        body = {
            "event": "recording.completed",
            "payload": {
                "object": {
                    "id": "pipeline-meeting-123",
                    "recording_files": [
                        {
                            "recording_type": "shared_screen_with_speaker_view",
                            "download_url": "https://zoom.us/rec/download/pipeline-test",
                            "file_type": "MP4",
                        }
                    ],
                }
            },
        }
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        message = f"v0:{ts}:{raw.decode()}"
        sig = "v0=" + hmac.new(
            ZOOM_SECRET.encode(), message.encode(), hashlib.sha256
        ).hexdigest()

        resp = await e2e_client.post(
            "/api/v1/webhooks/zoom",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-zm-request-timestamp": ts,
                "x-zm-signature": sig,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] is True
