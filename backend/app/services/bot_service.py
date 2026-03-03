from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, DomainValidationError
from app.models.meeting_bot_session import MeetingBotSession

VALID_PLATFORMS = {"zoom", "teams", "google_meet"}
VALID_STATUSES = {"scheduled", "joining", "recording", "completed", "failed", "cancelled"}


class BotService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def schedule_bot(
        self,
        org_id: UUID,
        deal_id: UUID,
        platform: str,
        meeting_url: str,
        scheduled_start: datetime | None,
        created_by: UUID,
    ) -> MeetingBotSession:
        """Schedule a bot to join a meeting for live recording."""
        if platform not in VALID_PLATFORMS:
            raise DomainValidationError(f"Unsupported bot platform: {platform}")

        session = MeetingBotSession(
            org_id=org_id,
            deal_id=deal_id,
            platform=platform,
            meeting_url=meeting_url,
            status="scheduled",
            scheduled_start=scheduled_start,
            consent_obtained=False,
            created_by=created_by,
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def get_session(self, session_id: UUID) -> MeetingBotSession:
        """Get a bot session by ID."""
        stmt = select(MeetingBotSession).where(MeetingBotSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            raise NotFoundError("MeetingBotSession", str(session_id))
        return session

    async def cancel_bot(self, session_id: UUID) -> None:
        """Cancel a scheduled bot session."""
        session = await self.get_session(session_id)
        if session.status not in ("scheduled", "joining"):
            raise DomainValidationError(
                f"Cannot cancel session in '{session.status}' status"
            )
        session.status = "cancelled"
        await self.db.flush()

    async def update_bot_status(
        self, session_id: UUID, status: str, **kwargs: object
    ) -> MeetingBotSession:
        """Update the status of a bot session."""
        if status not in VALID_STATUSES:
            raise DomainValidationError(f"Invalid status: {status}")

        session = await self.get_session(session_id)
        session.status = status

        now = datetime.now(timezone.utc)
        if status == "recording" and session.actual_start is None:
            session.actual_start = now
        elif status in ("completed", "failed"):
            session.actual_end = now

        if "recording_file_key" in kwargs:
            session.recording_file_key = kwargs["recording_file_key"]  # type: ignore[assignment]
        if "consent_obtained" in kwargs:
            session.consent_obtained = kwargs["consent_obtained"]  # type: ignore[assignment]

        await self.db.flush()
        return session

    async def list_sessions(
        self,
        org_id: UUID,
        deal_id: Optional[UUID] = None,
        status: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
    ) -> dict:
        """List bot sessions with optional filters and cursor pagination."""
        stmt = (
            select(MeetingBotSession)
            .where(MeetingBotSession.org_id == org_id)
            .order_by(MeetingBotSession.created_at.desc())
        )

        if deal_id is not None:
            stmt = stmt.where(MeetingBotSession.deal_id == deal_id)
        if status is not None:
            stmt = stmt.where(MeetingBotSession.status == status)
        if cursor is not None:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(MeetingBotSession.created_at < cursor_dt)

        stmt = stmt.limit(limit + 1)
        result = await self.db.execute(stmt)
        sessions = list(result.scalars().all())

        has_more = len(sessions) > limit
        if has_more:
            sessions = sessions[:limit]

        next_cursor = None
        if has_more and sessions:
            next_cursor = sessions[-1].created_at.isoformat()

        return {"items": sessions, "cursor": next_cursor, "has_more": has_more}
