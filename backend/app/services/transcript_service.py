from uuid import UUID
from typing import Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.transcript import Transcript
from app.models.transcript_segment import TranscriptSegment

logger = structlog.get_logger(__name__)


class TranscriptService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_transcript(
        self,
        meeting_id: UUID,
        org_id: UUID,
        full_text: str,
        deepgram_response: Optional[dict] = None,
        language: str = "en",
        confidence_score: Optional[float] = None,
    ) -> Transcript:
        """Create a transcript record for a meeting."""
        word_count = len(full_text.split()) if full_text else 0

        transcript = Transcript(
            meeting_id=meeting_id,
            org_id=org_id,
            full_text=full_text,
            language=language,
            deepgram_response=deepgram_response,
            word_count=word_count,
            confidence_score=confidence_score,
        )
        self.db.add(transcript)
        await self.db.flush()

        logger.info(
            "transcript_created",
            transcript_id=str(transcript.id),
            meeting_id=str(meeting_id),
            word_count=word_count,
        )
        return transcript

    async def store_segments(
        self,
        transcript_id: UUID,
        meeting_id: UUID,
        segments: list[dict],
    ) -> list[TranscriptSegment]:
        """Store individual transcript segments with speaker and timing data.

        Each segment dict: speaker_label, speaker_name, text,
        start_time, end_time, confidence, segment_index.
        """
        created = []
        for seg in segments:
            segment = TranscriptSegment(
                transcript_id=transcript_id,
                meeting_id=meeting_id,
                speaker_label=seg["speaker_label"],
                speaker_name=seg.get("speaker_name"),
                text=seg["text"],
                start_time=seg["start_time"],
                end_time=seg["end_time"],
                confidence=seg.get("confidence"),
                segment_index=seg["segment_index"],
            )
            self.db.add(segment)
            created.append(segment)

        await self.db.flush()
        logger.info(
            "segments_stored",
            transcript_id=str(transcript_id),
            count=len(created),
        )
        return created

    async def get_transcript(self, meeting_id: UUID) -> Transcript:
        """Get the transcript for a meeting. Raises NotFoundError if not found."""
        stmt = select(Transcript).where(Transcript.meeting_id == meeting_id)
        result = await self.db.execute(stmt)
        transcript = result.scalar_one_or_none()
        if transcript is None:
            raise NotFoundError("Transcript", f"meeting={meeting_id}")
        return transcript

    async def get_transcript_by_id(self, transcript_id: UUID) -> Transcript:
        """Get a transcript by its own ID."""
        stmt = select(Transcript).where(Transcript.id == transcript_id)
        result = await self.db.execute(stmt)
        transcript = result.scalar_one_or_none()
        if transcript is None:
            raise NotFoundError("Transcript", str(transcript_id))
        return transcript

    async def get_segments(
        self,
        transcript_id: UUID,
        speaker: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> list[TranscriptSegment]:
        """Get transcript segments with optional speaker and time range filters."""
        stmt = (
            select(TranscriptSegment)
            .where(TranscriptSegment.transcript_id == transcript_id)
            .order_by(TranscriptSegment.segment_index)
        )

        if speaker:
            stmt = stmt.where(
                (TranscriptSegment.speaker_label == speaker)
                | (TranscriptSegment.speaker_name == speaker)
            )
        if start_time is not None:
            stmt = stmt.where(TranscriptSegment.end_time >= start_time)
        if end_time is not None:
            stmt = stmt.where(TranscriptSegment.start_time <= end_time)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def search_transcript(
        self, transcript_id: UUID, query: str
    ) -> list[TranscriptSegment]:
        """Search transcript segments by text content (case-insensitive)."""
        stmt = (
            select(TranscriptSegment)
            .where(
                TranscriptSegment.transcript_id == transcript_id,
                TranscriptSegment.text.ilike(f"%{query}%"),
            )
            .order_by(TranscriptSegment.segment_index)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update_speaker_name(
        self, transcript_id: UUID, old_name: str, new_name: str
    ) -> int:
        """Update speaker name across all segments, returning count of updated segments."""
        stmt = (
            update(TranscriptSegment)
            .where(
                TranscriptSegment.transcript_id == transcript_id,
                (TranscriptSegment.speaker_label == old_name)
                | (TranscriptSegment.speaker_name == old_name),
            )
            .values(speaker_name=new_name)
        )
        result = await self.db.execute(stmt)
        await self.db.flush()

        count = result.rowcount
        logger.info(
            "speaker_name_updated",
            transcript_id=str(transcript_id),
            old_name=old_name,
            new_name=new_name,
            segments_updated=count,
        )
        return count

    async def get_full_text_with_speakers(self, transcript_id: UUID) -> str:
        """Get the full transcript text with speaker attribution for LLM prompts."""
        segments = await self.get_segments(transcript_id)
        lines = []
        for seg in segments:
            name = seg.speaker_name or seg.speaker_label
            lines.append(f"[{name}]: {seg.text}")
        return "\n\n".join(lines)
