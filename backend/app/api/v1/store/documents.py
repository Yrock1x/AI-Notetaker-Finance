"""Documents REST API (replaces frontend direct Supabase access).

Documents are owned by a deal (and its org). Tenant isolation is enforced in
app code: list/create go through ``scoped_deal_or_404`` on the parent deal, and
the single-get verifies ``principal.in_org`` on the document's org.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.db.models import Document
from app.db.scope import Principal
from app.schemas.common import BaseSchema

router = APIRouter()


# ---- schemas --------------------------------------------------------------
class DocumentCreate(BaseSchema):
    title: str
    document_type: str
    file_key: str
    file_size: int = 0


class DocumentResponse(BaseSchema):
    id: str
    org_id: str
    deal_id: str
    title: str
    document_type: str
    file_key: str
    file_size: int
    uploaded_by: str
    created_at: datetime
    updated_at: datetime


class DocumentDetailResponse(DocumentResponse):
    extracted_text: str | None = None


# ---- endpoints ------------------------------------------------------------
@router.get("/deals/{deal_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> list[DocumentResponse]:
    scoped_deal_or_404(session, principal, deal_id)
    rows = session.scalars(
        select(Document)
        .where(Document.deal_id == deal_id)
        .order_by(Document.created_at.desc())
    ).all()
    return [DocumentResponse.model_validate(d) for d in rows]


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> DocumentDetailResponse:
    doc = session.get(Document, document_id)
    if doc is None or not principal.in_org(doc.org_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        )
    return DocumentDetailResponse.model_validate(doc)


@router.post(
    "/deals/{deal_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    deal_id: str,
    payload: DocumentCreate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> DocumentResponse:
    deal = scoped_deal_or_404(session, principal, deal_id)
    doc = Document(
        org_id=deal.org_id,
        deal_id=deal.id,
        title=payload.title,
        document_type=payload.document_type,
        file_key=payload.file_key,
        file_size=payload.file_size,
        uploaded_by=principal.user_id,
    )
    session.add(doc)
    session.flush()
    return DocumentResponse.model_validate(doc)
