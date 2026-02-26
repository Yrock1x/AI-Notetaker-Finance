from datetime import datetime
from uuid import UUID

from app.schemas.common import BaseSchema


class TranscriptResponse(BaseSchema):
    id: UUID
    meeting_id: UUID
    full_text: str
    language: str
    word_count: int
    confidence_score: float | None = None
    created_at: datetime


class TranscriptSegmentResponse(BaseSchema):
    id: UUID
    speaker_label: str
    speaker_name: str | None = None
    text: str
    start_time: float
    end_time: float
    confidence: float | None = None
    segment_index: int
