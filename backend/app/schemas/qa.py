from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.schemas.common import BaseSchema


class Citation(BaseSchema):
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
