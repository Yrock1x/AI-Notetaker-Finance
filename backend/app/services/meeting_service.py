import uuid as uuid_mod
from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.integrations.aws.s3 import S3Client
from app.models.meeting import Meeting
from app.models.meeting_participant import MeetingParticipant

logger = structlog.get_logger(__name__)


class MeetingService:
    def __init__(self, db: AsyncSession, s3_client: S3Client, settings: Settings) -> None:
        self.db = db
        self.s3_client = s3_client
        self.settings = settings

    def _s3_key(self, org_id: UUID, deal_id: UUID, filename: str) -> str:
        """Generate a unique S3 key for a meeting recording."""
        unique = uuid_mod.uuid4().hex[:12]
        return f"orgs/{org_id}/deals/{deal_id}/meetings/{unique}/{filename}"

    async def create_meeting_from_upload(
        self,
        deal_id: UUID,
        org_id: UUID,
        title: str,
        uploaded_by: UUID,
        s3_key: str,
        duration_seconds: int | None = None,
        meeting_date: datetime | None = None,
    ) -> Meeting:
        """Create a meeting record after an audio/video file upload."""
        meeting = Meeting(
            deal_id=deal_id,
            org_id=org_id,
            title=title,
            meeting_date=meeting_date or datetime.now(UTC),
            duration_seconds=duration_seconds,
            source="upload",
            file_key=s3_key,
            status="uploading",
            created_by=uploaded_by,
        )
        self.db.add(meeting)
        await self.db.flush()

        logger.info(
            "meeting_created",
            meeting_id=str(meeting.id),
            deal_id=str(deal_id),
            title=title,
        )
        return meeting

    async def generate_presigned_upload_url(
        self, org_id: UUID, deal_id: UUID, filename: str, content_type: str
    ) -> dict:
        """Generate a presigned S3 URL for uploading a meeting recording."""
        s3_key = self._s3_key(org_id, deal_id, filename)
        presigned = await self.s3_client.generate_presigned_upload_url(
            key=s3_key,
            content_type=content_type,
        )
        return {
            "s3_key": s3_key,
            "upload_url": presigned.get("url", ""),
            "fields": presigned.get("fields", {}),
        }

    async def get_meeting(self, meeting_id: UUID) -> Meeting:
        """Get a meeting by ID. Raises NotFoundError if not found."""
        stmt = select(Meeting).where(Meeting.id == meeting_id)
        result = await self.db.execute(stmt)
        meeting = result.scalar_one_or_none()
        if meeting is None:
            raise NotFoundError("Meeting", str(meeting_id))
        return meeting

    async def get_meeting_with_details(self, meeting_id: UUID) -> Meeting:
        """Get a meeting with participants eagerly loaded."""
        stmt = (
            select(Meeting)
            .options(selectinload(Meeting.participants))
            .where(Meeting.id == meeting_id)
        )
        result = await self.db.execute(stmt)
        meeting = result.scalar_one_or_none()
        if meeting is None:
            raise NotFoundError("Meeting", str(meeting_id))
        return meeting

    async def list_meetings(
        self,
        deal_id: UUID,
        cursor: str | None = None,
        limit: int = 50,
        status_filter: str | None = None,
    ) -> dict:
        """List meetings for a deal with cursor-based pagination."""
        stmt = (
            select(Meeting)
            .where(Meeting.deal_id == deal_id)
            .order_by(Meeting.created_at.desc())
        )

        if status_filter:
            stmt = stmt.where(Meeting.status == status_filter)

        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                stmt = stmt.where(Meeting.created_at < cursor_dt)
            except ValueError:
                pass

        stmt = stmt.limit(limit + 1)
        result = await self.db.execute(stmt)
        meetings = list(result.scalars().all())

        has_more = len(meetings) > limit
        if has_more:
            meetings = meetings[:limit]

        next_cursor = None
        if has_more and meetings:
            next_cursor = meetings[-1].created_at.isoformat()

        return {
            "items": meetings,
            "cursor": next_cursor,
            "has_more": has_more,
        }

    async def update_meeting_status(
        self,
        meeting_id: UUID,
        status: str,
        error_message: str | None = None,
    ) -> Meeting:
        """Update the processing status of a meeting."""
        meeting = await self.get_meeting(meeting_id)
        meeting.status = status
        if error_message is not None:
            meeting.error_message = error_message
        await self.db.flush()

        logger.info(
            "meeting_status_updated",
            meeting_id=str(meeting_id),
            status=status,
        )
        return meeting

    async def add_participants(
        self,
        meeting_id: UUID,
        participants: list[dict],
    ) -> list[MeetingParticipant]:
        """Add participant records to a meeting from diarization results."""
        created = []
        for p in participants:
            participant = MeetingParticipant(
                meeting_id=meeting_id,
                speaker_label=p["speaker_label"],
                speaker_name=p.get("speaker_name"),
                user_id=p.get("user_id"),
            )
            self.db.add(participant)
            created.append(participant)

        await self.db.flush()
        return created

    async def update_meeting(
        self,
        meeting_id: UUID,
        title: str | None = None,
        meeting_date: datetime | None = None,
        duration_seconds: int | None = None,
        bot_enabled: bool | None = None,
    ) -> Meeting:
        """Update editable meeting fields."""
        meeting = await self.get_meeting(meeting_id)
        if title is not None:
            meeting.title = title
        if meeting_date is not None:
            meeting.meeting_date = meeting_date
        if duration_seconds is not None:
            meeting.duration_seconds = duration_seconds
        if bot_enabled is not None:
            meeting.bot_enabled = bot_enabled
        await self.db.flush()
        return meeting

    async def delete_meeting(self, meeting_id: UUID) -> None:
        """Delete a meeting and its S3 recording."""
        meeting = await self.get_meeting(meeting_id)

        if meeting.file_key:
            try:
                await self.s3_client.delete_file(meeting.file_key)
            except Exception:
                logger.warning(
                    "s3_delete_failed",
                    meeting_id=str(meeting_id),
                    file_key=meeting.file_key,
                )

        await self.db.delete(meeting)
        await self.db.flush()
        logger.info("meeting_deleted", meeting_id=str(meeting_id))

    async def count_meetings(self, deal_id: UUID) -> int:
        """Count total meetings for a deal."""
        stmt = select(func.count(Meeting.id)).where(Meeting.deal_id == deal_id)
        result = await self.db.execute(stmt)
        return result.scalar_one()
