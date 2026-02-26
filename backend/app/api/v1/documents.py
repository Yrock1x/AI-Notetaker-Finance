from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import DealRole
from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.integrations.aws.s3 import get_s3_client
from app.models.user import User
from app.schemas.common import PaginatedResponse
from app.schemas.document import (
    DocumentCreate,
    DocumentDownloadResponse,
    DocumentResponse,
    DocumentUploadResponse,
)
from app.services.deal_service import DealService
from app.services.document_service import DocumentService
from app.tasks.pipelines import create_document_pipeline

router = APIRouter()


@router.get("/", response_model=PaginatedResponse[DocumentResponse])
async def list_documents(
    deal_id: UUID,
    document_type: str | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> PaginatedResponse[DocumentResponse]:
    """List documents in a deal. Requires deal membership."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()
    s3_client = get_s3_client()
    service = DocumentService(db, s3_client, settings)
    result = await service.list_documents(
        deal_id=deal_id,
        cursor=cursor,
        limit=limit,
        document_type=document_type,
    )
    items = [DocumentResponse.model_validate(d) for d in result["items"]]
    return PaginatedResponse(
        items=items,
        cursor=result["cursor"],
        has_more=result["has_more"],
    )


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def initiate_document_upload(
    deal_id: UUID,
    payload: DocumentCreate,
    content_type: str = Query(description="MIME type of the file"),
    file_name: str = Query(description="Original file name"),
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    """Get a presigned URL to upload a document. Requires write permission."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id, min_role=DealRole.ANALYST)

    settings = get_settings()
    s3_client = get_s3_client()
    service = DocumentService(db, s3_client, settings)

    # Generate presigned upload URL
    presigned = await service.generate_presigned_upload_url(
        org_id=org_id,
        deal_id=deal_id,
        filename=file_name,
        content_type=content_type,
    )

    # Create the document record
    document = await service.upload_document(
        deal_id=deal_id,
        org_id=org_id,
        filename=file_name,
        s3_key=presigned["s3_key"],
        content_type=content_type,
        file_size=0,  # Will be updated after upload confirmation
        uploaded_by=current_user.id,
    )

    return DocumentUploadResponse(
        document_id=document.id,
        upload_url=presigned["upload_url"],
        file_key=presigned["s3_key"],
    )


@router.post("/upload/{document_id}/confirm", response_model=DocumentResponse)
async def confirm_document_upload(
    deal_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    org_id: UUID = Depends(get_org_id),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Confirm document upload is complete. Triggers text extraction and embedding."""
    settings = get_settings()
    s3_client = get_s3_client()
    service = DocumentService(db, s3_client, settings)

    document = await service.get_document(document_id)

    # Trigger the document processing pipeline (text extraction + embeddings)
    create_document_pipeline(str(document_id), str(deal_id), str(org_id)).delay()

    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    deal_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    """Get document details."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()
    s3_client = get_s3_client()
    service = DocumentService(db, s3_client, settings)
    document = await service.get_document(document_id)
    return DocumentResponse.model_validate(document)


@router.get("/{document_id}/download", response_model=DocumentDownloadResponse)
async def download_document(
    deal_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> DocumentDownloadResponse:
    """Get a presigned download URL for a document."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id)

    settings = get_settings()
    s3_client = get_s3_client()
    service = DocumentService(db, s3_client, settings)
    download_url = await service.generate_download_url(document_id)
    return DocumentDownloadResponse(download_url=download_url)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    deal_id: UUID,
    document_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete a document. Requires delete permission."""
    deal_service = DealService(db)
    await deal_service.check_deal_access(deal_id, current_user.id, min_role=DealRole.LEAD)

    settings = get_settings()
    s3_client = get_s3_client()
    service = DocumentService(db, s3_client, settings)
    await service.delete_document(document_id)
