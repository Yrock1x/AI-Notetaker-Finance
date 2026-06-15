from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from app.schemas.common import BaseSchema


class Citation(BaseSchema):
    # Unlike request bodies (BaseSchema forbids extras to keep the write
    # contract honest), this model is also used to *deserialize* citation JSON
    # persisted on qa_interactions. Older rows stored richer keys (chunk_id,
    # relevance, and spread metadata like meeting_id/start_time); tolerate and
    # drop them on read so the Q&A history endpoint never 500s on legacy data.
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    source_type: str  # transcript_segment, document_chunk
    source_id: UUID
    source_title: str | None = None
    text_excerpt: str
    timestamp: float | None = None  # for transcript citations
    page: int | None = None  # for document citations


class QARequest(BaseSchema):
    question: str = Field(min_length=1, max_length=2000)


class QAResponse(BaseSchema):
    id: UUID
    deal_id: UUID
    question: str
    answer: str
    citations: list[Citation] = []
    grounding_score: float | None = None
    model_used: str
    created_at: datetime


class QAHistoryResponse(BaseSchema):
    id: UUID
    question: str
    answer: str
    citations: list[Citation] = []
    grounding_score: float | None = None
    created_at: datetime
