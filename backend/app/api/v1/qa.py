"""Deal / meeting scoped Q&A endpoints.

Access control is enforced in app code (app/db/scope.py): the caller may only
read/write ``qa_interactions`` for deals in an org they belong to. Fireworks
(or Claude if opted in) produces the answer via the LLM router.
"""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.deps import get_db, get_principal
from app.db.models import Meeting, QAInteraction
from app.db.scope import Principal, deal_org_id
from app.dependencies import (
    AuthUser,
    get_current_user,
    get_llm_router,
)
from app.schemas.common import PaginatedResponse
from app.schemas.qa import QAHistoryResponse, QARequest, QAResponse
from app.services.qa_service import Citation as ServiceCitation
from app.services.qa_service import QAService


def _llm_provider_http_error(exc: httpx.HTTPStatusError) -> HTTPException:
    """Map an upstream LLM provider error to a 502. In development surface the
    provider's message to debug misconfig; in production keep it generic so we
    don't leak internal model names / account state."""
    if settings.is_production:
        detail = "LLM provider unavailable"
    else:
        try:
            body = exc.response.json()
            detail = (body.get("error") or {}).get("message") or exc.response.text
        except Exception:
            detail = exc.response.text
        detail = f"LLM provider error ({exc.response.status_code}): {detail[:400]}"
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def _to_response_citation(c: ServiceCitation) -> dict:
    meta = c.metadata or {}
    return {
        "source_type": c.source_type,
        "source_id": c.source_id,
        "text_excerpt": c.text,
        "timestamp": meta.get("start_time"),
    }

router = APIRouter()
meeting_qa_router = APIRouter()

# Q&A is the most expensive endpoint (RAG retrieval + a long-context LLM
# call). 10/min/user blocks accidental loops + cost-DoS without getting
# in the way of normal interactive use.
QA_RATE_LIMIT = "10/minute"


def _persist_interaction(
    session: Session,
    principal: Principal,
    *,
    deal_id: UUID,
    user_id: UUID,
    question: str,
    answer: str,
    citations: list[dict],
    grounding_score: float | None,
    model_used: str,
    meeting_id: UUID | None,
) -> QAInteraction:
    # org_id is required by schema; derive from the deal and enforce that the
    # caller is a member of that org (replaces the old RLS check).
    org_id = deal_org_id(session, str(deal_id))
    if org_id is None or not principal.in_org(org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
        )
    interaction = QAInteraction(
        org_id=org_id,
        deal_id=str(deal_id),
        meeting_id=str(meeting_id) if meeting_id else None,
        user_id=str(user_id),
        question=question,
        answer=answer,
        citations=citations,
        grounding_score=grounding_score,
        model_used=model_used,
    )
    session.add(interaction)
    session.flush()
    return interaction


@router.post("/ask", response_model=QAResponse)
@limiter.limit(QA_RATE_LIMIT)
async def ask_question(
    request: Request,
    deal_id: UUID,
    payload: QARequest,
    current_user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> QAResponse:
    """Ask a question scoped to a deal (RAG over all deal artefacts)."""
    qa = QAService(session=session, llm_router=get_llm_router())
    try:
        result = await qa.ask(deal_id=deal_id, question=payload.question)
    except httpx.HTTPStatusError as exc:
        raise _llm_provider_http_error(exc) from exc

    citations = [
        {
            "chunk_id": c.chunk_id,
            "source_id": c.source_id,
            "source_type": c.source_type,
            "text_excerpt": c.text,
            "relevance": c.relevance,
            **(c.metadata or {}),
        }
        for c in result.citations
    ]
    interaction = _persist_interaction(
        session,
        principal,
        deal_id=deal_id,
        user_id=current_user.id,
        question=payload.question,
        answer=result.answer,
        citations=citations,
        grounding_score=result.grounding_score,
        model_used="llm-router",
        meeting_id=None,
    )
    return QAResponse(
        id=interaction.id,
        deal_id=deal_id,
        question=payload.question,
        answer=result.answer,
        citations=[_to_response_citation(c) for c in result.citations],
        grounding_score=result.grounding_score,
        model_used=interaction.model_used or "llm-router",
        created_at=interaction.created_at,
    )


@meeting_qa_router.post("/ask", response_model=QAResponse)
@limiter.limit(QA_RATE_LIMIT)
async def ask_meeting_question(
    request: Request,
    meeting_id: UUID,
    payload: QARequest,
    current_user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> QAResponse:
    """Ask a question scoped to a specific meeting. Feeds the meeting's full
    transcript to a cheap model when it fits, falling back to deal RAG when the
    transcript is too large or not yet available."""
    meeting = (
        session.query(Meeting.org_id, Meeting.deal_id)
        .filter(Meeting.id == str(meeting_id))
        .first()
    )
    if not meeting or not principal.in_org(meeting[0]) or meeting[1] is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    deal_id = UUID(meeting[1])

    qa = QAService(session=session, llm_router=get_llm_router())
    try:
        result = await qa.ask_meeting(
            deal_id=deal_id, meeting_id=meeting_id, question=payload.question
        )
    except httpx.HTTPStatusError as exc:
        raise _llm_provider_http_error(exc) from exc

    citations = [
        {
            "chunk_id": c.chunk_id,
            "source_id": c.source_id,
            "source_type": c.source_type,
            "text_excerpt": c.text,
            "relevance": c.relevance,
            **(c.metadata or {}),
        }
        for c in result.citations
    ]
    interaction = _persist_interaction(
        session,
        principal,
        deal_id=deal_id,
        user_id=current_user.id,
        question=payload.question,
        answer=result.answer,
        citations=citations,
        grounding_score=result.grounding_score,
        model_used="llm-router",
        meeting_id=meeting_id,
    )
    return QAResponse(
        id=interaction.id,
        deal_id=deal_id,
        question=payload.question,
        answer=result.answer,
        citations=[_to_response_citation(c) for c in result.citations],
        grounding_score=result.grounding_score,
        model_used=interaction.model_used or "llm-router",
        created_at=interaction.created_at,
    )


def _require_deal_access(session: Session, principal: Principal, deal_id: UUID) -> None:
    org_id = deal_org_id(session, str(deal_id))
    if org_id is None or not principal.in_org(org_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")


@router.get("/history", response_model=PaginatedResponse[QAHistoryResponse])
async def get_qa_history(
    deal_id: UUID,
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> PaginatedResponse[QAHistoryResponse]:
    """Paginated Q&A history for a deal (org-scoped)."""
    _require_deal_access(session, principal, deal_id)
    from sqlalchemy import select

    stmt = (
        select(QAInteraction)
        .where(QAInteraction.deal_id == str(deal_id))
        .order_by(QAInteraction.created_at.desc())
        .limit(limit + 1)
    )
    if cursor:
        stmt = stmt.where(QAInteraction.created_at < cursor)
    rows = session.scalars(stmt).all()

    has_more = len(rows) > limit
    items = rows[:limit]
    history = [
        QAHistoryResponse(
            id=r.id,
            question=r.question,
            answer=r.answer,
            citations=r.citations or [],
            grounding_score=r.grounding_score,
            created_at=r.created_at,
        )
        for r in items
    ]
    next_cursor = items[-1].created_at if has_more and items else None
    return PaginatedResponse(items=history, cursor=next_cursor, has_more=has_more)


@router.get("/history/{interaction_id}", response_model=QAResponse)
async def get_qa_interaction(
    deal_id: UUID,
    interaction_id: UUID,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> QAResponse:
    """Fetch a single Q&A interaction (org-scoped)."""
    _require_deal_access(session, principal, deal_id)
    from sqlalchemy import select

    row = session.scalar(
        select(QAInteraction).where(
            QAInteraction.id == str(interaction_id),
            QAInteraction.deal_id == str(deal_id),
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Q&A interaction not found")
    return QAResponse(
        id=row.id,
        deal_id=deal_id,
        question=row.question,
        answer=row.answer,
        citations=row.citations or [],
        grounding_score=row.grounding_score,
        model_used=row.model_used or "",
        created_at=row.created_at,
    )
