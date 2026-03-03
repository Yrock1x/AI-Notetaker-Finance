"""Unit tests for webhook endpoint handlers (Zoom, Teams, Slack).

Tests verify signature validation, challenge/handshake protocols, and event
dispatching for all three platforms. HMAC signatures are computed in-test to
validate the verification logic end-to-end.
"""

import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

ZOOM_WEBHOOK_SECRET = "test-zoom-webhook-secret"  # noqa: S105
SLACK_SIGNING_SECRET = "test-slack-signing-secret"  # noqa: S105
TEAMS_WEBHOOK_SECRET = "test-teams-webhook-secret"  # noqa: S105


@pytest.fixture
def webhook_settings() -> Settings:
    """Settings configured with test webhook secrets."""
    return Settings(
        database_url="postgresql+asyncpg://test:test@localhost/test",
        app_env="development",
        zoom_webhook_secret_token=ZOOM_WEBHOOK_SECRET,
        slack_signing_secret=SLACK_SIGNING_SECRET,
        teams_webhook_secret=TEAMS_WEBHOOK_SECRET,
    )


@pytest.fixture
def webhook_app(webhook_settings: Settings) -> FastAPI:
    """FastAPI app wired with webhook routes and mocked dependencies."""
    from app.dependencies import get_db
    from app.main import create_app

    app = create_app()

    async def override_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = override_get_db

    return app


@pytest.fixture
async def webhook_client(
    webhook_app: FastAPI, webhook_settings: Settings
) -> AsyncClient:
    """AsyncClient that patches get_settings to use test webhook secrets."""
    transport = ASGITransport(app=webhook_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper: Compute signatures
# ---------------------------------------------------------------------------


def _zoom_signature(body: bytes, timestamp: str, secret: str = ZOOM_WEBHOOK_SECRET) -> str:
    """Compute a valid Zoom webhook signature."""
    message = f"v0:{timestamp}:{body.decode()}"
    return "v0=" + hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _slack_signature(body: bytes, timestamp: str, secret: str = SLACK_SIGNING_SECRET) -> str:
    """Compute a valid Slack webhook signature."""
    sig_basestring = f"v0:{timestamp}:{body.decode()}"
    return "v0=" + hmac.new(secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()


# ===========================================================================
# ZOOM WEBHOOK TESTS
# ===========================================================================


class TestZoomWebhook:
    """Tests for the POST /api/v1/webhooks/zoom endpoint."""

    @patch("app.api.v1.webhooks.get_settings")
    async def test_zoom_webhook_url_validation_challenge(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Zoom URL validation challenge should return plainToken and encryptedToken."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "event": "endpoint.url_validation",
            "payload": {"plainToken": "abc123"},
        }
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        sig = _zoom_signature(raw, ts)

        resp = await webhook_client.post(
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
        assert data["plainToken"] == "abc123"
        # The encryptedToken should be the HMAC of the plainToken
        expected_encrypted = hmac.new(
            ZOOM_WEBHOOK_SECRET.encode(), b"abc123", hashlib.sha256
        ).hexdigest()
        assert data["encryptedToken"] == expected_encrypted

    @patch("app.api.v1.webhooks.get_settings")
    async def test_zoom_webhook_recording_completed(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Zoom recording.completed event should be accepted and return received=True."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "event": "recording.completed",
            "payload": {
                "object": {
                    "id": "123456789",
                    "recording_files": [
                        {
                            "recording_type": "shared_screen_with_speaker_view",
                            "download_url": "https://zoom.us/rec/download/abc123",
                            "file_type": "MP4",
                        }
                    ],
                }
            },
        }
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        sig = _zoom_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/zoom",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-zm-request-timestamp": ts,
                "x-zm-signature": sig,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["received"] is True

    @patch("app.api.v1.webhooks.get_settings")
    async def test_zoom_webhook_meeting_ended(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Zoom meeting.ended event should be accepted and return received=True."""
        mock_get_settings.return_value = webhook_settings

        body = {"event": "meeting.ended", "payload": {"object": {"id": "999"}}}
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        sig = _zoom_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/zoom",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-zm-request-timestamp": ts,
                "x-zm-signature": sig,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["received"] is True

    @patch("app.api.v1.webhooks.get_settings")
    async def test_zoom_webhook_invalid_signature_rejected(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """A Zoom webhook request with an invalid signature should be rejected with 401."""
        mock_get_settings.return_value = webhook_settings

        body = {"event": "meeting.ended", "payload": {}}
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))

        resp = await webhook_client.post(
            "/api/v1/webhooks/zoom",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-zm-request-timestamp": ts,
                "x-zm-signature": "v0=invalid-signature",
            },
        )

        assert resp.status_code == 401

    @patch("app.api.v1.webhooks.get_settings")
    async def test_zoom_webhook_expired_timestamp_rejected(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """A Zoom webhook with a timestamp older than 5 minutes should be rejected."""
        mock_get_settings.return_value = webhook_settings

        body = {"event": "meeting.ended", "payload": {}}
        raw = json.dumps(body).encode()
        # Use a timestamp from 10 minutes ago
        ts = str(int(time.time()) - 600)
        sig = _zoom_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/zoom",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "x-zm-request-timestamp": ts,
                "x-zm-signature": sig,
            },
        )

        assert resp.status_code == 401


# ===========================================================================
# TEAMS WEBHOOK TESTS
# ===========================================================================


class TestTeamsWebhook:
    """Tests for the POST /api/v1/webhooks/teams endpoint."""

    @patch("app.api.v1.webhooks.get_settings")
    async def test_teams_webhook_validation_token_echo(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Teams subscription validation should echo back the validationToken as plain text."""
        mock_get_settings.return_value = webhook_settings

        resp = await webhook_client.post(
            "/api/v1/webhooks/teams?validationToken=test-validation-token-12345",
            content=b"{}",
            headers={"Content-Type": "application/json"},
        )

        assert resp.status_code == 200
        assert resp.text == "test-validation-token-12345"

    @patch("app.api.v1.webhooks.get_settings")
    async def test_teams_webhook_call_record_notification(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Teams call record notification with valid clientState should be accepted."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "value": [
                {
                    "resource": "communications/callRecords/abc-123",
                    "changeType": "created",
                    "clientState": TEAMS_WEBHOOK_SECRET,
                }
            ]
        }

        resp = await webhook_client.post(
            "/api/v1/webhooks/teams",
            json=body,
        )

        assert resp.status_code == 200
        assert resp.json()["received"] is True

    @patch("app.api.v1.webhooks.get_settings")
    async def test_teams_webhook_invalid_client_state_rejected(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Teams notification with wrong clientState should be rejected with 401."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "value": [
                {
                    "resource": "communications/callRecords/abc-123",
                    "changeType": "created",
                    "clientState": "wrong-secret",
                }
            ]
        }

        resp = await webhook_client.post(
            "/api/v1/webhooks/teams",
            json=body,
        )

        assert resp.status_code == 401


# ===========================================================================
# SLACK EVENTS TESTS
# ===========================================================================


class TestSlackEvents:
    """Tests for the POST /api/v1/webhooks/slack/events endpoint."""

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_events_url_verification_challenge(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Slack url_verification challenge should echo the challenge value."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "type": "url_verification",
            "challenge": "slack-challenge-token-xyz",
        }
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["challenge"] == "slack-challenge-token-xyz"

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_events_message_received(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Slack message event should be accepted and return received=True."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "type": "event_callback",
            "event": {
                "type": "message",
                "channel": "C123456",
                "text": "Hello from test",
                "user": "U123456",
            },
        }
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["received"] is True

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_events_app_mention_received(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Slack app_mention event should be accepted and return received=True."""
        mock_get_settings.return_value = webhook_settings

        body = {
            "type": "event_callback",
            "event": {
                "type": "app_mention",
                "channel": "C123456",
                "text": "<@U_BOT_ID> show status",
                "user": "U123456",
            },
        }
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        assert resp.json()["received"] is True

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_events_invalid_signature_rejected(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """Slack event with invalid signature should be rejected with 401."""
        mock_get_settings.return_value = webhook_settings

        body = {"type": "event_callback", "event": {"type": "message"}}
        raw = json.dumps(body).encode()
        ts = str(int(time.time()))

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/events",
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": "v0=totally-wrong-signature",
            },
        )

        assert resp.status_code == 401


# ===========================================================================
# SLACK COMMANDS TESTS
# ===========================================================================


class TestSlackCommands:
    """Tests for the POST /api/v1/webhooks/slack/commands endpoint."""

    def _build_form_body(self, text: str = "") -> bytes:
        """Build a URL-encoded form body like Slack sends for slash commands."""
        from urllib.parse import urlencode

        params = {
            "command": "/dealwise",
            "text": text,
            "user_id": "U123456",
            "channel_id": "C123456",
            "team_id": "T123456",
            "response_url": "https://hooks.slack.com/commands/test",
        }
        return urlencode(params).encode()

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_commands_help(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """The 'help' subcommand should return usage instructions."""
        mock_get_settings.return_value = webhook_settings

        raw = self._build_form_body("help")
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/commands",
            content=raw,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["response_type"] == "ephemeral"
        assert "Deal Companion Commands" in data["text"]
        assert "/dealwise status" in data["text"]
        assert "/dealwise meetings" in data["text"]

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_commands_status(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """The 'status' subcommand should return a status check response."""
        mock_get_settings.return_value = webhook_settings

        raw = self._build_form_body("status")
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/commands",
            content=raw,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["response_type"] == "ephemeral"
        assert "status" in data["text"].lower()

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_commands_meetings(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """The 'meetings' subcommand should return a meeting fetch response."""
        mock_get_settings.return_value = webhook_settings

        raw = self._build_form_body("meetings")
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/commands",
            content=raw,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["response_type"] == "ephemeral"
        assert "meetings" in data["text"].lower()

    @patch("app.api.v1.webhooks.get_settings")
    async def test_slack_commands_unknown_returns_help(
        self, mock_get_settings, webhook_client: AsyncClient, webhook_settings: Settings
    ):
        """An unknown subcommand should return a help pointer."""
        mock_get_settings.return_value = webhook_settings

        raw = self._build_form_body("foobar")
        ts = str(int(time.time()))
        sig = _slack_signature(raw, ts)

        resp = await webhook_client.post(
            "/api/v1/webhooks/slack/commands",
            content=raw,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Slack-Request-Timestamp": ts,
                "X-Slack-Signature": sig,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["response_type"] == "ephemeral"
        assert "Unknown command" in data["text"]
        assert "/dealwise help" in data["text"]
