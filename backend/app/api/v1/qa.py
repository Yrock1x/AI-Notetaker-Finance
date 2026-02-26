import uuid as uuid_mod
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.llm.openai_provider import OpenAIEmbeddingProvider
from app.llm.router import LLMRouter
from app.llm.claude_provider import ClaudeProvider
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.qa import QAHistoryResponse, QARequest, QAResponse
from app.services.deal_service import DealService
from app.services.embedding_service import EmbeddingService
from app.services.qa_service import QAService

router = APIRouter()


@router.post("/ask", response_model=QAResponse)
async def ask_question(
    deal_id: UUID,
    payload: QARequest,
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> QAResponse:
    """Ask a question scoped to the deal's meetings and documents.

    Uses RAG to find relevant context and generates a citation-backed answer.
    Requires deal membership.
    """
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()

    # Set up the LLM router with Claude provider
    llm_router = LLMRouter()
    claude_provider = ClaudeProvider(api_key=settings.anthropic_api_key)
    llm_router.register_provider("claude", claude_provider)

    # Set up the embedding service with OpenAI provider
    embedding_provider = OpenAIEmbeddingProvider(api_key=settings.openai_api_key)
    embedding_service = EmbeddingService(db, embedding_provider)

    qa_service = QAService(db, llm_router, embedding_service)
    result = await qa_service.ask(
        deal_id=deal_id,
        org_id=org_id,
        question=payload.question,
    )

    # Map the service dataclass response to the API schema
    # The QA service does not persist interactions yet, so generate a transient ID
    return QAResponse(
        id=uuid_mod.uuid4(),
        deal_id=deal_id,
        question=payload.question,
        answer=result.answer,
        citations=[],  # Citation format differs between service and schema; map if needed
        grounding_score=result.grounding_score,
        model_used="claude",
        created_at=datetime.now(timezone.utc),
    )


@router.get("/history", response_model=PaginatedResponse[QAHistoryResponse])
async def get_qa_history(
    deal_id: UUID,
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[QAHistoryResponse]:
    """Get Q&A history for a deal."""
    # QA persistence model not yet implemented; return empty list
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    return PaginatedResponse(items=[], cursor=None, has_more=False)


@router.get("/history/{interaction_id}", response_model=QAResponse)
async def get_qa_interaction(
    deal_id: UUID,
    interaction_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> QAResponse:
    """Get a specific Q&A interaction with full citations."""
    # QA persistence model not yet implemented
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    raise HTTPException(501, "QA history persistence not yet implemented")
