"""Analysis endpoints — list / run / re-run, SQLite-backed.

Org scoping is enforced in app code (app/db/scope.py); the org for a write is
derived from the meeting via ``meeting_org_id``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.db.deps import get_db, get_principal
from app.db.scope import Principal, meeting_org_id
from app.dependencies import (
    AuthUser,
    get_current_user,
    get_llm_router,
)
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis_service import AnalysisService

router = APIRouter()

# Analyses fan out to multiple LLM calls (summarisation + downstream calls)
# and write to storage — tighter than QA per minute.
ANALYSIS_RATE_LIMIT = "5/minute"


def _require_meeting_org(session: Session, principal: Principal, meeting_id: UUID) -> UUID:
    """Resolve the meeting's org and 404 unless the caller is a member."""
    org_id = meeting_org_id(session, str(meeting_id))
    if org_id is None or not principal.in_org(org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    return UUID(org_id)


@router.get("", response_model=list[AnalysisResponse])
async def list_analyses(
    meeting_id: UUID,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[AnalysisResponse]:
    _require_meeting_org(session, principal, meeting_id)
    svc = AnalysisService(session=session, llm_router=get_llm_router())
    rows = await svc.list_analyses(meeting_id)
    return [AnalysisResponse.model_validate(r) for r in rows]


@router.post("", response_model=AnalysisResponse, status_code=202)
@limiter.limit(ANALYSIS_RATE_LIMIT)
async def run_analysis(
    request: Request,
    meeting_id: UUID,
    payload: AnalysisRequest,
    current_user: AuthUser = Depends(get_current_user),
    principal: Principal = Depends(get_principal),
    session: Session = Depends(get_db),
) -> AnalysisResponse:
    """Run an analysis synchronously and return the resulting row.

    Long-term this should be fired into Inngest; for now we execute it
    inline so the caller gets a finished analysis back. Inngest path is
    added by the frontend's ``meeting/uploaded`` event.
    """
    org_id = _require_meeting_org(session, principal, meeting_id)
    svc = AnalysisService(session=session, llm_router=get_llm_router())
    row = await svc.run_analysis(
        meeting_id=meeting_id,
        org_id=org_id,
        call_type=payload.call_type,
        requested_by=current_user.id,
    )
    return AnalysisResponse.model_validate(row)


@router.get("/latest", response_model=AnalysisResponse)
async def get_latest_analysis(
    meeting_id: UUID,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AnalysisResponse:
    _require_meeting_org(session, principal, meeting_id)
    svc = AnalysisService(session=session, llm_router=get_llm_router())
    rows = await svc.list_analyses(meeting_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No analyses found")
    return AnalysisResponse.model_validate(rows[0])


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    meeting_id: UUID,
    analysis_id: UUID,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AnalysisResponse:
    _require_meeting_org(session, principal, meeting_id)
    svc = AnalysisService(session=session, llm_router=get_llm_router())
    try:
        row = await svc.get_analysis(analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row["meeting_id"] != str(meeting_id):
        raise HTTPException(status_code=404, detail="Analysis not in meeting")
    return AnalysisResponse.model_validate(row)


@router.post("/{analysis_id}/rerun", response_model=AnalysisResponse, status_code=201)
async def rerun_analysis(
    meeting_id: UUID,
    analysis_id: UUID,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> AnalysisResponse:
    _require_meeting_org(session, principal, meeting_id)
    svc = AnalysisService(session=session, llm_router=get_llm_router())
    try:
        row = await svc.rerun_analysis(analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row["meeting_id"] != str(meeting_id):
        raise HTTPException(status_code=404, detail="Analysis not in meeting")
    return AnalysisResponse.model_validate(row)
