import uuid as uuid_mod
from uuid import UUID
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.exceptions import NotFoundError
from app.integrations.aws.s3 import S3Client
from app.models.document import Document

logger = structlog.get_logger(__name__)

CONTENT_TYPE_MAP = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "text/plain": "txt",
}


class DocumentService:
    def __init__(self, db: AsyncSession, s3_client: S3Client, settings: Settings) -> None:
        self.db = db
        self.s3_client = s3_client
        self.settings = settings

    def _s3_key(self, org_id: UUID, deal_id: UUID, filename: str) -> str:
        """Generate a unique S3 key for a document."""
        unique = uuid_mod.uuid4().hex[:12]
        return f"orgs/{org_id}/deals/{deal_id}/documents/{unique}/{filename}"

    def _detect_document_type(self, filename: str, content_type: str) -> str:
        """Detect document type from content type or filename extension."""
        if content_type in CONTENT_TYPE_MAP:
            return CONTENT_TYPE_MAP[content_type]
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in ("pdf", "docx", "xlsx", "pptx", "txt"):
            return ext
        return "unknown"

    async def upload_document(
        self,
        deal_id: UUID,
        org_id: UUID,
        filename: str,
        s3_key: str,
        content_type: str,
        file_size: int,
        uploaded_by: UUID,
    ) -> Document:
        """Create a document record after file upload."""
        doc_type = self._detect_document_type(filename, content_type)

        document = Document(
            deal_id=deal_id,
            org_id=org_id,
            title=filename,
            document_type=doc_type,
            file_key=s3_key,
            file_size=file_size,
            uploaded_by=uploaded_by,
        )
        self.db.add(document)
        await self.db.flush()

        logger.info(
            "document_uploaded",
            document_id=str(document.id),
            deal_id=str(deal_id),
            filename=filename,
            doc_type=doc_type,
        )
        return document

    async def generate_presigned_upload_url(
        self, org_id: UUID, deal_id: UUID, filename: str, content_type: str
    ) -> dict:
        """Generate a presigned S3 URL for uploading a document."""
        s3_key = self._s3_key(org_id, deal_id, filename)
        presigned = await self.s3_client.generate_presigned_upload_url(
            key=s3_key,
            content_type=content_type,
        )
        return {
            "s3_key": s3_key,
            "upload_url": presigned.get("url", ""),
            "fields": presigned.get("fields", {}),
        }

    async def get_document(self, document_id: UUID) -> Document:
        """Get a document by ID. Raises NotFoundError if not found."""
        stmt = select(Document).where(Document.id == document_id)
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document", str(document_id))
        return document

    async def generate_download_url(self, document_id: UUID) -> str:
        """Generate a presigned S3 URL for downloading a document."""
        document = await self.get_document(document_id)
        return await self.s3_client.generate_presigned_download_url(document.file_key)

    async def list_documents(
        self,
        deal_id: UUID,
        cursor: Optional[str] = None,
        limit: int = 50,
        document_type: Optional[str] = None,
    ) -> dict:
        """List documents for a deal with cursor-based pagination."""
        from datetime import datetime

        stmt = (
            select(Document)
            .where(Document.deal_id == deal_id)
            .order_by(Document.created_at.desc())
        )

        if document_type:
            stmt = stmt.where(Document.document_type == document_type)

        if cursor:
            try:
                cursor_dt = datetime.fromisoformat(cursor)
                stmt = stmt.where(Document.created_at < cursor_dt)
            except ValueError:
                pass

        stmt = stmt.limit(limit + 1)
        result = await self.db.execute(stmt)
        documents = list(result.scalars().all())

        has_more = len(documents) > limit
        if has_more:
            documents = documents[:limit]

        next_cursor = None
        if has_more and documents:
            next_cursor = documents[-1].created_at.isoformat()

        return {
            "items": documents,
            "cursor": next_cursor,
            "has_more": has_more,
        }

    async def update_extracted_text(
        self, document_id: UUID, extracted_text: str
    ) -> Document:
        """Update the extracted text for a document (after text extraction)."""
        document = await self.get_document(document_id)
        document.extracted_text = extracted_text
        await self.db.flush()
        return document

    async def delete_document(self, document_id: UUID) -> None:
        """Delete a document and remove it from S3."""
        document = await self.get_document(document_id)

        try:
            await self.s3_client.delete_file(document.file_key)
        except Exception:
            logger.warning(
                "s3_delete_failed",
                document_id=str(document_id),
                file_key=document.file_key,
            )

        await self.db.delete(document)
        await self.db.flush()
        logger.info("document_deleted", document_id=str(document_id))
