"""Unit tests for the BotService.

Tests cover bot scheduling, cancellation, status updates, and session listing.
All database interactions are mocked to isolate the service logic.
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import DomainValidationError
from app.models.meeting_bot_session import MeetingBotSession
from app.services.bot_service import BotService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a mock async database session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def service(mock_db: AsyncMock) -> BotService:
    """Create a BotService with a mocked database session."""
    return BotService(db=mock_db)


@pytest.fixture
def org_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def deal_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


def _make_session(
    status: str = "scheduled",
    org_id: uuid.UUID | None = None,
    deal_id: uuid.UUID | None = None,
    **overrides,
) -> MeetingBotSession:
    """Create a MeetingBotSession with sensible defaults for testing."""
    session = MeetingBotSession(
        id=overrides.get("id", uuid.uuid4()),
        org_id=org_id or uuid.uuid4(),
        deal_id=deal_id or uuid.uuid4(),
        platform="zoom",
        meeting_url="https://zoom.us/j/123",
        status=status,
        consent_obtained=False,
        created_by=overrides.get("created_by", uuid.uuid4()),
    )
    session.created_at = datetime.now(UTC)
    session.updated_at = datetime.now(UTC)
    session.actual_start = overrides.get("actual_start")
    session.actual_end = overrides.get("actual_end")
    session.scheduled_start = overrides.get("scheduled_start")
    session.recording_file_key = overrides.get("recording_file_key")
    return session


# ===========================================================================
# schedule_bot
# ===========================================================================


class TestScheduleBot:
    """Tests for BotService.schedule_bot."""

    async def test_schedule_bot_creates_session(
        self,
        service: BotService,
        mock_db: AsyncMock,
        org_id: uuid.UUID,
        deal_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Scheduling a bot for a valid platform should create a MeetingBotSession."""
        session = await service.schedule_bot(
            org_id=org_id,
            deal_id=deal_id,
            platform="zoom",
            meeting_url="https://zoom.us/j/123456",
            scheduled_start=datetime.now(UTC),
            created_by=user_id,
        )

        assert session.platform == "zoom"
        assert session.status == "scheduled"
        assert session.org_id == org_id
        assert session.deal_id == deal_id
        assert session.meeting_url == "https://zoom.us/j/123456"
        assert session.consent_obtained is False
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()

    async def test_schedule_bot_invalid_platform_raises(
        self,
        service: BotService,
        org_id: uuid.UUID,
        deal_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Scheduling a bot for an unsupported platform should raise DomainValidationError."""
        with pytest.raises(DomainValidationError, match="Unsupported bot platform"):
            await service.schedule_bot(
                org_id=org_id,
                deal_id=deal_id,
                platform="webex",
                meeting_url="https://webex.com/meet/123",
                scheduled_start=None,
                created_by=user_id,
            )


# ===========================================================================
# cancel_bot
# ===========================================================================


class TestCancelBot:
    """Tests for BotService.cancel_bot."""

    async def test_cancel_bot_scheduled_status(
        self, service: BotService, mock_db: AsyncMock
    ):
        """A bot in 'scheduled' status should be cancellable."""
        session = _make_session(status="scheduled")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        await service.cancel_bot(session.id)

        assert session.status == "cancelled"
        mock_db.flush.assert_awaited()

    async def test_cancel_bot_joining_status(
        self, service: BotService, mock_db: AsyncMock
    ):
        """A bot in 'joining' status should be cancellable."""
        session = _make_session(status="joining")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        await service.cancel_bot(session.id)

        assert session.status == "cancelled"

    async def test_cancel_bot_recording_status_raises(
        self, service: BotService, mock_db: AsyncMock
    ):
        """A bot in 'recording' status should NOT be cancellable."""
        session = _make_session(status="recording")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        with pytest.raises(DomainValidationError, match="Cannot cancel"):
            await service.cancel_bot(session.id)

    async def test_cancel_bot_completed_status_raises(
        self, service: BotService, mock_db: AsyncMock
    ):
        """A bot in 'completed' status should NOT be cancellable."""
        session = _make_session(status="completed")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        with pytest.raises(DomainValidationError, match="Cannot cancel"):
            await service.cancel_bot(session.id)


# ===========================================================================
# update_bot_status
# ===========================================================================


class TestUpdateBotStatus:
    """Tests for BotService.update_bot_status."""

    async def test_update_bot_status_sets_actual_start_on_recording(
        self, service: BotService, mock_db: AsyncMock
    ):
        """Transitioning to 'recording' should set actual_start if not already set."""
        session = _make_session(status="joining")
        assert session.actual_start is None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        result = await service.update_bot_status(session.id, "recording")

        assert result.status == "recording"
        assert result.actual_start is not None

    async def test_update_bot_status_sets_actual_end_on_completed(
        self, service: BotService, mock_db: AsyncMock
    ):
        """Transitioning to 'completed' should set actual_end."""
        session = _make_session(status="recording")
        session.actual_start = datetime.now(UTC)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = session
        mock_db.execute.return_value = mock_result

        result = await service.update_bot_status(session.id, "completed")

        assert result.status == "completed"
        assert result.actual_end is not None

    async def test_update_bot_status_invalid_status_raises(
        self, service: BotService, mock_db: AsyncMock
    ):
        """Setting an invalid status should raise DomainValidationError."""
        with pytest.raises(DomainValidationError, match="Invalid status"):
            await service.update_bot_status(uuid.uuid4(), "invalid_status")


# ===========================================================================
# list_sessions
# ===========================================================================


class TestListSessions:
    """Tests for BotService.list_sessions."""

    async def test_list_sessions_filters_by_deal_id(
        self,
        service: BotService,
        mock_db: AsyncMock,
        org_id: uuid.UUID,
        deal_id: uuid.UUID,
    ):
        """list_sessions with a deal_id filter should pass it to the query."""
        sessions = [
            _make_session(org_id=org_id, deal_id=deal_id),
            _make_session(org_id=org_id, deal_id=deal_id),
        ]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = sessions
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await service.list_sessions(org_id=org_id, deal_id=deal_id)

        assert len(result["items"]) == 2
        assert result["has_more"] is False
        assert result["cursor"] is None

    async def test_list_sessions_filters_by_status(
        self,
        service: BotService,
        mock_db: AsyncMock,
        org_id: uuid.UUID,
    ):
        """list_sessions with a status filter should pass it to the query."""
        sessions = [_make_session(org_id=org_id, status="recording")]

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = sessions
        mock_result = MagicMock()
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await service.list_sessions(org_id=org_id, status="recording")

        assert len(result["items"]) == 1
        assert result["items"][0].status == "recording"
