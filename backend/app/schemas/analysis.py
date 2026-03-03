from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from app.schemas.common import BaseSchema


class AnalysisRequest(BaseSchema):
    call_type: Literal[
        "diligence", "management_presentation", "buyer_call",
        "financial_review", "qoe", "summarization", "general",
    ] = "general"


class AnalysisResponse(BaseSchema):
    id: UUID
    meeting_id: UUID
    call_type: str
    structured_output: dict[str, Any] | None = None
    model_used: str
    prompt_version: str
    grounding_score: float | None = None
    status: str
    error_message: str | None = None
    requested_by: UUID | None = None
    version: int
    created_at: datetime
    updated_at: datetime
