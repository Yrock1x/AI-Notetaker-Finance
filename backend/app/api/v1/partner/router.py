"""CogniVault partner API — M2M endpoints scoped to one org per API key.

Every handler authenticates a :class:`PartnerContext` (one org per key), gates on
the key's ``scopes``, scopes all queries to ``ctx.org_id`` (via the reused
``org_scoped`` / explicit ``org_id`` filters), and writes an ``audit_logs`` row.

Paths are spelled out in full under ``/partner/v1`` so the router can be mounted
at an empty prefix.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.partner.auth import (
    PartnerContext,
    get_partner_context,
    require_scope,
)
from app.db.audit import record_audit
from app.db.deps import get_db
from app.db.models import (
    Analysis,
    Deal,
    Document,
    Meeting,
    OrgMembership,
    Transcript,
)
from app.db.scope import org_scoped
from app.db.vectors import match_embeddings_for_deal
from app.schemas.common import BaseSchema

router = APIRouter()


# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------
class DealResponse(BaseSchema):
    id: str
    org_id: str
    name: str
    description: str | None = None
    target_company: str | None = None
    deal_type: str
    stage: str | None = None
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime


class DealCreate(BaseSchema):
    name: str
    description: str | None = None
    target_company: str | None = None
    deal_type: str = "general"
    stage: str | None = None
    status: str = "active"


class DocumentResponse(BaseSchema):
    id: str
    org_id: str
    deal_id: str
    title: str
    document_type: str
    file_key: str
    file_size: int
    extracted_text: str | None = None
    uploaded_by: str
    created_at: datetime
    updated_at: datetime


class DocumentCreate(BaseSchema):
    title: str
    document_type: str
    file_key: str
    file_size: int = 0
    extracted_text: str | None = None


class TranscriptResponse(BaseSchema):
    id: str
    org_id: str
    meeting_id: str
    full_text: str
    language: str
    word_count: int
    confidence_score: float | None = None
    created_at: datetime
    updated_at: datetime


class AnalysisResponse(BaseSchema):
    id: str
    org_id: str
    meeting_id: str
    call_type: str
    structured_output: dict | None = None
    model_used: str
    prompt_version: str
    grounding_score: float | None = None
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class SearchRequest(BaseSchema):
    query_vector: list[float]
    top_k: int | None = None


class SearchHit(BaseSchema):
    id: str
    source_type: str
    source_id: str
    chunk_text: str
    similarity: float
    metadata: dict


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _org_actor_id(session: Session, org_id: str) -> str:
    """Pick a profile id to satisfy NOT-NULL FK columns on partner writes.

    Partner keys have no backing profile, but ``deals.created_by`` /
    ``documents.uploaded_by`` reference ``profiles.id``. Use the org's owner
    (falling back to any member); 400 if the org has no members.
    """
    user_id = session.scalar(
        select(OrgMembership.user_id)
        .where(OrgMembership.org_id == org_id)
        .order_by((OrgMembership.role == "owner").desc(), OrgMembership.joined_at)
    )
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Org has no members to attribute the write to",
        )
    return user_id


def _scoped_deal_or_404(
    session: Session, ctx: PartnerContext, deal_id: str
) -> Deal:
    deal = session.scalar(
        select(Deal).where(
            Deal.id == deal_id,
            Deal.org_id == ctx.org_id,
            Deal.deleted_at.is_(None),
        )
    )
    if deal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found"
        )
    return deal


def _scoped_meeting_or_404(
    session: Session, ctx: PartnerContext, meeting_id: str
) -> Meeting:
    meeting = session.scalar(
        select(Meeting).where(
            Meeting.id == meeting_id, Meeting.org_id == ctx.org_id
        )
    )
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found"
        )
    return meeting


# ---------------------------------------------------------------------------
# deals
# ---------------------------------------------------------------------------
@router.get("/partner/v1/deals", response_model=list[DealResponse])
def list_deals(
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> list[DealResponse]:
    require_scope(ctx, "deals:read")
    stmt = org_scoped(select(Deal), Deal, ctx.principal()).where(
        Deal.deleted_at.is_(None)
    )
    rows = session.scalars(stmt.order_by(Deal.created_at.desc())).all()
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="list",
        resource_type="partner",
        details={"resource": "deals", "count": len(rows)},
    )
    return [DealResponse.model_validate(d) for d in rows]


@router.get("/partner/v1/deals/{deal_id}", response_model=DealResponse)
def get_deal(
    deal_id: str,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> DealResponse:
    require_scope(ctx, "deals:read")
    deal = _scoped_deal_or_404(session, ctx, deal_id)
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="read",
        resource_type="partner",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"resource": "deal"},
    )
    return DealResponse.model_validate(deal)


@router.post(
    "/partner/v1/deals",
    response_model=DealResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_deal(
    payload: DealCreate,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> DealResponse:
    require_scope(ctx, "deals:write")
    created_by = _org_actor_id(session, ctx.org_id)
    deal = Deal(
        org_id=ctx.org_id,
        name=payload.name,
        description=payload.description,
        target_company=payload.target_company,
        deal_type=payload.deal_type,
        stage=payload.stage,
        status=payload.status,
        created_by=created_by,
    )
    session.add(deal)
    session.flush()
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="create",
        resource_type="partner",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"resource": "deal", "name": deal.name},
    )
    session.flush()
    return DealResponse.model_validate(deal)


# ---------------------------------------------------------------------------
# documents
# ---------------------------------------------------------------------------
@router.get(
    "/partner/v1/deals/{deal_id}/documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    deal_id: str,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> list[DocumentResponse]:
    require_scope(ctx, "documents:read")
    deal = _scoped_deal_or_404(session, ctx, deal_id)
    rows = session.scalars(
        select(Document)
        .where(Document.deal_id == deal.id, Document.org_id == ctx.org_id)
        .order_by(Document.created_at.desc())
    ).all()
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="list",
        resource_type="partner",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"resource": "documents", "count": len(rows)},
    )
    return [DocumentResponse.model_validate(d) for d in rows]


@router.post(
    "/partner/v1/deals/{deal_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    deal_id: str,
    payload: DocumentCreate,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> DocumentResponse:
    require_scope(ctx, "documents:write")
    deal = _scoped_deal_or_404(session, ctx, deal_id)
    uploaded_by = _org_actor_id(session, ctx.org_id)
    doc = Document(
        org_id=deal.org_id,
        deal_id=deal.id,
        title=payload.title,
        document_type=payload.document_type,
        file_key=payload.file_key,
        file_size=payload.file_size,
        extracted_text=payload.extracted_text,
        uploaded_by=uploaded_by,
    )
    session.add(doc)
    session.flush()
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="create",
        resource_type="partner",
        resource_id=doc.id,
        deal_id=deal.id,
        details={"resource": "document", "title": doc.title},
    )
    session.flush()
    return DocumentResponse.model_validate(doc)


# ---------------------------------------------------------------------------
# transcripts / analyses
# ---------------------------------------------------------------------------
@router.get(
    "/partner/v1/meetings/{meeting_id}/transcript",
    response_model=TranscriptResponse,
)
def get_transcript(
    meeting_id: str,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> TranscriptResponse:
    require_scope(ctx, "transcripts:read")
    meeting = _scoped_meeting_or_404(session, ctx, meeting_id)
    transcript = session.scalar(
        select(Transcript).where(
            Transcript.meeting_id == meeting.id,
            Transcript.org_id == ctx.org_id,
        )
    )
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Transcript not found"
        )
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="read",
        resource_type="partner",
        resource_id=transcript.id,
        details={"resource": "transcript", "meeting_id": meeting.id},
    )
    return TranscriptResponse.model_validate(transcript)


@router.get(
    "/partner/v1/meetings/{meeting_id}/analyses",
    response_model=list[AnalysisResponse],
)
def list_analyses(
    meeting_id: str,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> list[AnalysisResponse]:
    require_scope(ctx, "transcripts:read")
    meeting = _scoped_meeting_or_404(session, ctx, meeting_id)
    rows = session.scalars(
        select(Analysis)
        .where(
            Analysis.meeting_id == meeting.id,
            Analysis.org_id == ctx.org_id,
            Analysis.status == "completed",
        )
        .order_by(Analysis.created_at.desc())
    ).all()
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="list",
        resource_type="partner",
        details={
            "resource": "analyses",
            "meeting_id": meeting.id,
            "count": len(rows),
        },
    )
    return [AnalysisResponse.model_validate(a) for a in rows]


# ---------------------------------------------------------------------------
# vector search
# ---------------------------------------------------------------------------
@router.post(
    "/partner/v1/deals/{deal_id}/search",
    response_model=list[SearchHit],
)
def search_deal(
    deal_id: str,
    payload: SearchRequest,
    ctx: PartnerContext = Depends(get_partner_context),
    session: Session = Depends(get_db),
) -> list[SearchHit]:
    require_scope(ctx, "search")
    deal = _scoped_deal_or_404(session, ctx, deal_id)
    results = match_embeddings_for_deal(
        session,
        deal_id=deal.id,
        query_vector=payload.query_vector,
        top_k=payload.top_k or 15,
    )
    record_audit(
        session,
        org_id=ctx.org_id,
        user_id=None,
        action="search",
        resource_type="partner",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"resource": "search", "hits": len(results)},
    )
    return [SearchHit.model_validate(r) for r in results]
