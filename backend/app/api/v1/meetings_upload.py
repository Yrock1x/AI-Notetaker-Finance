"""Meeting upload ticket — returns a worker-signed local-storage upload URL.

The frontend needs to PUT a multi-hundred-MB video/audio file to storage
without round-tripping the body through application logic. We mint a
short-lived HMAC-signed PUT URL into the ``meeting-recordings`` bucket (served
by app/api/v1/store/files.py) and return it with the resulting ``file_key``.

The frontend then PUTs the file at the URL, creates the ``meetings`` row via
``POST /deals/{id}/meetings``, and fires ``meeting/uploaded`` into Inngest.

(The generic ``POST /storage/upload-ticket`` covers the same need; this
endpoint is kept for the meeting-specific contract.)
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.core.config import settings
from app.db.scope import Principal
from app.storage.local import make_signed_url

router = APIRouter()

RECORDINGS_BUCKET = "meeting-recordings"

# Application-level cap, checked before minting a URL so we reject obviously
# too-large requests with a clear error.
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB


class UploadTicketRequest(BaseModel):
    deal_id: str
    filename: str
    content_type: Literal[
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/mp4", "audio/m4a", "audio/webm", "audio/ogg",
        "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    ]
    size_bytes: int = Field(gt=0, le=MAX_UPLOAD_SIZE_BYTES)


class UploadTicketResponse(BaseModel):
    file_key: str
    upload_url: str
    method: str = "PUT"


@router.post("/upload-ticket", response_model=UploadTicketResponse)
async def create_upload_ticket(
    body: UploadTicketRequest,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> UploadTicketResponse:
    """Mint a signed PUT URL into the meeting-recordings bucket for a deal.

    Org-scoped: the caller must be a member of the deal's org (404 otherwise),
    so signed URLs can't be minted into another tenant's storage tree.
    """
    scoped_deal_or_404(session, principal, body.deal_id)

    ext = ("." + body.filename.rsplit(".", 1)[1]) if "." in body.filename else ""
    file_key = f"{body.deal_id}/{uuid.uuid4()}{ext}"
    upload_url = settings.public_api_url.rstrip("/") + make_signed_url(
        RECORDINGS_BUCKET, file_key
    )
    if not upload_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not create upload URL",
        )
    return UploadTicketResponse(file_key=file_key, upload_url=upload_url)
