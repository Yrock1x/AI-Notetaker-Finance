"""Deal / meeting scoped Q&A endpoints.

Access control is delegated to Supabase RLS — the user can only insert/
select ``qa_interactions`` rows for deals they belong to. Fireworks (or
Claude if opted in) produces the answer via the LLM router.
"""

from __future__ import annotations

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from supabase import Client

from app.core.config import settings
from app.core.rate_limit import limiter
from app.dependencies import (
    AuthUser,
    get_current_user,
    get_llm_router,
    get_user_supabase,
)
from app.schemas.common import PaginatedResponse
from app.schemas.qa import QAHistoryResponse, QARequest, QAResponse
from app.services.qa_service import QAService

router = APIRouter()
meeting_qa_router = APIRouter()

# Q&A is the most expensive endpoint (RAG retrieval + a long-context LLM
# call). 10/min/user blocks accidental loops + cost-DoS without getting
# in the way of normal interactive use.
QA_RATE_LIMIT = "10/minute"


def _persist_interaction(
    supabase: Client,
    *,
    deal_id: UUID,
    user_id: UUID,
    question: str,
    answer: str,
    citations: list[dict],
    grounding_score: float | None,
    model_used: str,
    meeting_id: UUID | None,
) -> dict:
    row = {
        "deal_id": str(deal_id),
        "meeting_id": str(meeting_id) if meeting_id else None,
        "user_id": str(user_id),
        "question": question,
        "answer": answer,
        "citations": citations,
        "grounding_score": grounding_score,
        "model_used": model_used,
    }
    # org_id is required by schema; derive from the deal via RPC or a join.
    deal_rows = (
        supabase.table("deals").select("org_id").eq("id", str(deal_id)).limit(1).execute().data
    )
    if not deal_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
        )
    row["org_id"] = deal_rows[0]["org_id"]
    return (
        supabase.table("qa_interactions").insert(row).execute().data[0]
    )


@router.post("/ask", response_model=QAResponse)
@limiter.limit(QA_RATE_LIMIT)
async def ask_question(
    request: Request,
    deal_id: UUID,
    payload: QARequest,
    current_user: AuthUser = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase),
) -> QAResponse:
    """Ask a question scoped to a deal (RAG over all deal artefacts)."""
    llm_router = get_llm_router()
    qa = QAService(supabase=supabase, llm_router=llm_router)
    try:
        result = await qa.ask(deal_id=deal_id, question=payload.question)
    except httpx.HTTPStatusError as exc:
        # In development, surface the upstream LLM error verbatim so we can
        # debug Fireworks/Claude misconfig (e.g. 412 "account suspended").
        # In production, return a generic message — provider error bodies
        # can leak internal model names, request ids, and account state.
        if settings.is_production:
            detail = "LLM provider unavailable"
        else:
            try:
                body = exc.response.json()
                detail = (body.get("error") or {}).get("message") or exc.response.text
            except Exception:
                detail = exc.response.text
            detail = f"LLM provider error ({exc.response.status_code}): {detail[:400]}"
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
        ) from exc

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
        supabase=supabase,
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
        id=interaction["id"],
        deal_id=deal_id,
        question=payload.question,
        answer=result.answer,
        citations=citations,
        grounding_score=result.grounding_score,
        model_used=interaction.get("model_used", "llm-router"),
        created_at=interaction["created_at"],
    )


@meeting_qa_router.post("/ask", response_model=QAResponse)
@limiter.limit(QA_RATE_LIMIT)
async def ask_meeting_question(
    request: Request,
    meeting_id: UUID,
    payload: QARequest,
    current_user: AuthUser = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase),
) -> QAResponse:
    """Ask a question scoped to a specific meeting. Shares the deal RAG
    pipeline today; future optimisation: filter chunks by meeting_id."""
    meeting_rows = (
        supabase.table("meetings")
        .select("deal_id")
        .eq("id", str(meeting_id))
        .limit(1)
        .execute()
        .data
    )
    if not meeting_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    deal_id = UUID(meeting_rows[0]["deal_id"])

    llm_router = get_llm_router()
    qa = QAService(supabase=supabase, llm_router=llm_router)
    result = await qa.ask(
        deal_id=deal_id, question=payload.question, meeting_id=meeting_id
    )

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
        supabase=supabase,
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
        id=interaction["id"],
        deal_id=deal_id,
        question=payload.question,
        answer=result.answer,
        citations=citations,
        grounding_score=result.grounding_score,
        model_used=interaction.get("model_used", "llm-router"),
        created_at=interaction["created_at"],
    )


@router.get("/history", response_model=PaginatedResponse[QAHistoryResponse])
async def get_qa_history(
    deal_id: UUID,
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    supabase: Client = Depends(get_user_supabase),
    _user: AuthUser = Depends(get_current_user),
) -> PaginatedResponse[QAHistoryResponse]:
    """Paginated Q&A history for a deal (RLS-scoped)."""
    query = (
        supabase.table("qa_interactions")
        .select("*")
        .eq("deal_id", str(deal_id))
        .order("created_at", desc=True)
        .limit(limit + 1)
    )
    if cursor:
        query = query.lt("created_at", cursor)
    rows = query.execute().data or []

    has_more = len(rows) > limit
    items = rows[:limit]
    history = [
        QAHistoryResponse(
            id=row["id"],
            question=row["question"],
            answer=row["answer"],
            citations=row.get("citations") or [],
            grounding_score=row.get("grounding_score"),
            created_at=row["created_at"],
        )
        for row in items
    ]
    next_cursor = items[-1]["created_at"] if has_more and items else None
    return PaginatedResponse(items=history, cursor=next_cursor, has_more=has_more)


@router.get("/history/{interaction_id}", response_model=QAResponse)
async def get_qa_interaction(
    deal_id: UUID,
    interaction_id: UUID,
    supabase: Client = Depends(get_user_supabase),
    _user: AuthUser = Depends(get_current_user),
) -> QAResponse:
    """Fetch a single Q&A interaction."""
    rows = (
        supabase.table("qa_interactions")
        .select("*")
        .eq("id", str(interaction_id))
        .eq("deal_id", str(deal_id))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Q&A interaction not found")
    row = rows[0]
    return QAResponse(
        id=row["id"],
        deal_id=deal_id,
        question=row["question"],
        answer=row["answer"],
        citations=row.get("citations") or [],
        grounding_score=row.get("grounding_score"),
        model_used=row.get("model_used") or "",
        created_at=row["created_at"],
    )
