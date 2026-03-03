"""Unit tests for the RecallClient (Recall.ai bot management client).

Tests cover both demo mode (no API key) and real mode (mocked httpx calls).
Demo mode should return mock data without hitting the network. Real mode
tests verify that the correct HTTP requests are constructed and sent.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.recall.client import DEFAULT_BASE_URL, RecallClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def demo_client() -> RecallClient:
    """RecallClient in demo mode (no API key)."""
    return RecallClient(api_key=None)


@pytest.fixture
def real_client() -> RecallClient:
    """RecallClient in real mode (with API key)."""
    return RecallClient(api_key="test-recall-api-key")


# ===========================================================================
# Demo mode tests
# ===========================================================================


class TestDemoMode:
    """Tests for RecallClient behaviour when no API key is provided (demo mode)."""

    async def test_demo_mode_create_bot_returns_mock(self, demo_client: RecallClient):
        """create_bot in demo mode should return a mock bot dict without network calls."""
        result = await demo_client.create_bot(
            "https://zoom.us/j/123456", "Test Bot"
        )

        assert "id" in result
        assert result["meeting_url"] == "https://zoom.us/j/123456"
        assert result["bot_name"] == "Test Bot"
        assert result["status"]["code"] == "ready"
        assert "demo mode" in result["status"]["message"].lower()

    async def test_demo_mode_get_bot_returns_mock(self, demo_client: RecallClient):
        """get_bot in demo mode should return a mock status dict for any bot ID."""
        bot_id = str(uuid.uuid4())
        result = await demo_client.get_bot(bot_id)

        assert result["id"] == bot_id
        assert result["status"]["code"] == "done"

    async def test_demo_mode_get_transcript_returns_mock(self, demo_client: RecallClient):
        """get_transcript in demo mode should return a mock transcript list."""
        result = await demo_client.get_transcript("any-bot-id")

        assert isinstance(result, list)
        assert len(result) >= 2
        assert "speaker" in result[0]
        assert "words" in result[0]

    async def test_demo_mode_list_bots_returns_empty(self, demo_client: RecallClient):
        """list_bots in demo mode should return an empty list."""
        result = await demo_client.list_bots()

        assert result == []

    async def test_demo_mode_get_recording_returns_mock(self, demo_client: RecallClient):
        """get_recording in demo mode should return a mock recording dict."""
        result = await demo_client.get_recording("any-bot-id")

        assert result is not None
        assert "url" in result
        assert result["content_type"] == "video/mp4"


# ===========================================================================
# is_demo property
# ===========================================================================


class TestIsDemo:
    """Tests for the is_demo property."""

    def test_is_demo_true_without_api_key(self):
        """is_demo should be True when no API key is provided."""
        client = RecallClient(api_key=None)
        assert client.is_demo is True

    def test_is_demo_true_with_empty_string_api_key(self):
        """is_demo should be True when API key is an empty string."""
        client = RecallClient(api_key="")
        assert client.is_demo is True

    def test_is_demo_false_with_api_key(self):
        """is_demo should be False when a valid API key is provided."""
        client = RecallClient(api_key="valid-key")
        assert client.is_demo is False


# ===========================================================================
# Real mode tests (mocked httpx)
# ===========================================================================


class TestRealMode:
    """Tests for RecallClient in real mode with mocked HTTP calls."""

    @patch("app.integrations.recall.client.httpx.AsyncClient")
    async def test_create_bot_real_mode(
        self, mock_async_client_cls: MagicMock, real_client: RecallClient
    ):
        """create_bot in real mode should POST to /bot with the correct payload and headers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "bot-abc-123",
            "meeting_url": "https://zoom.us/j/999",
            "status": {"code": "ready"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = mock_client_instance

        result = await real_client.create_bot("https://zoom.us/j/999", "My Bot")

        assert result["id"] == "bot-abc-123"
        mock_client_instance.post.assert_awaited_once()
        call_args = mock_client_instance.post.call_args
        assert f"{DEFAULT_BASE_URL}/bot" == call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["meeting_url"] == "https://zoom.us/j/999"
        assert payload["bot_name"] == "My Bot"
        headers = call_args.kwargs["headers"]
        assert "Token test-recall-api-key" in headers["Authorization"]

    @patch("app.integrations.recall.client.httpx.AsyncClient")
    async def test_get_bot_real_mode(
        self, mock_async_client_cls: MagicMock, real_client: RecallClient
    ):
        """get_bot in real mode should GET /bot/{bot_id} with auth headers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "bot-xyz-789",
            "status": {"code": "in_call_recording"},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = mock_client_instance

        result = await real_client.get_bot("bot-xyz-789")

        assert result["id"] == "bot-xyz-789"
        mock_client_instance.get.assert_awaited_once()
        call_args = mock_client_instance.get.call_args
        assert f"{DEFAULT_BASE_URL}/bot/bot-xyz-789" == call_args.args[0]

    @patch("app.integrations.recall.client.httpx.AsyncClient")
    async def test_get_transcript_real_mode(
        self, mock_async_client_cls: MagicMock, real_client: RecallClient
    ):
        """get_transcript in real mode should GET /bot/{bot_id}/transcript."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"speaker": "Speaker 0", "words": [{"text": "Test", "start_time": 0.0}]}
        ]
        mock_response.raise_for_status = MagicMock()

        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = mock_client_instance

        result = await real_client.get_transcript("bot-t-111")

        assert isinstance(result, list)
        assert len(result) == 1
        mock_client_instance.get.assert_awaited_once()
        call_args = mock_client_instance.get.call_args
        assert f"{DEFAULT_BASE_URL}/bot/bot-t-111/transcript" == call_args.args[0]

    @patch("app.integrations.recall.client.httpx.AsyncClient")
    async def test_create_bot_http_error_propagates(
        self, mock_async_client_cls: MagicMock, real_client: RecallClient
    ):
        """HTTP errors from Recall.ai should propagate to the caller."""
        mock_response = MagicMock()
        mock_response.status_code = 422
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unprocessable Entity",
            request=MagicMock(),
            response=mock_response,
        )

        mock_client_instance = AsyncMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        mock_async_client_cls.return_value = mock_client_instance

        with pytest.raises(httpx.HTTPStatusError):
            await real_client.create_bot("https://zoom.us/j/bad", "Bot")
