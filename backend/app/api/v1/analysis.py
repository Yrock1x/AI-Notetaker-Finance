"""Analysis endpoints — list / run / re-run, Supabase-backed.

Access is enforced by Supabase RLS: ``analyses`` rows are visible only to
members of the owning org. We don't do app-level RBAC checks here.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from app.api.v1.qa import _build_llm_router
from app.dependencies import AuthUser, get_current_user, get_user_supabase
from app.schemas.analysis import AnalysisRequest, AnalysisResponse
from app.services.analysis_service import AnalysisService

router = APIRouter()


def _meeting_org(supabase: Client, meeting_id: UUID) -> UUID:
    rows = (
        supabase.table("meetings")
        .select("org_id")
        .eq("id", str(meeting_id))
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    return UUID(rows[0]["org_id"])


@router.get("", response_model=list[AnalysisResponse])
async def list_analyses(
    meeting_id: UUID,
    supabase: Client = Depends(get_user_supabase),
    _user: AuthUser = Depends(get_current_user),
) -> list[AnalysisResponse]:
    svc = AnalysisService(supabase=supabase, llm_router=_build_llm_router())
    rows = await svc.list_analyses(meeting_id)
    return [AnalysisResponse.model_validate(r) for r in rows]


@router.post("", response_model=AnalysisResponse, status_code=202)
async def run_analysis(
    meeting_id: UUID,
    payload: AnalysisRequest,
    current_user: AuthUser = Depends(get_current_user),
    supabase: Client = Depends(get_user_supabase),
) -> AnalysisResponse:
    """Run an analysis synchronously and return the resulting row.

    Long-term this should be fired into Inngest; for now we execute it
    inline so the caller gets a finished analysis back. Inngest path is
    added by the frontend's ``meeting/uploaded`` event.
    """
    org_id = _meeting_org(supabase, meeting_id)
    svc = AnalysisService(supabase=supabase, llm_router=_build_llm_router())
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
    supabase: Client = Depends(get_user_supabase),
    _user: AuthUser = Depends(get_current_user),
) -> AnalysisResponse:
    svc = AnalysisService(supabase=supabase, llm_router=_build_llm_router())
    rows = await svc.list_analyses(meeting_id)
    if not rows:
        raise HTTPException(status_code=404, detail="No analyses found")
    return AnalysisResponse.model_validate(rows[0])


@router.get("/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(
    meeting_id: UUID,
    analysis_id: UUID,
    supabase: Client = Depends(get_user_supabase),
    _user: AuthUser = Depends(get_current_user),
) -> AnalysisResponse:
    svc = AnalysisService(supabase=supabase, llm_router=_build_llm_router())
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
    supabase: Client = Depends(get_user_supabase),
    current_user: AuthUser = Depends(get_current_user),  # noqa: ARG001 - reserved
) -> AnalysisResponse:
    svc = AnalysisService(supabase=supabase, llm_router=_build_llm_router())
    try:
        row = await svc.rerun_analysis(analysis_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row["meeting_id"] != str(meeting_id):
        raise HTTPException(status_code=404, detail="Analysis not in meeting")
    return AnalysisResponse.model_validate(row)
