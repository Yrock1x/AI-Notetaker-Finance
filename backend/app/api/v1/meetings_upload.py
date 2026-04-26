"""Meeting upload ticket — returns a Supabase Storage signed upload URL.

Rationale: the frontend needs to PUT a multi-hundred-MB video/audio file
straight to storage without round-tripping through the worker. Supabase
Storage supports "resumable upload URLs" that work exactly like S3 presigned
PUTs. We mint the URL here (server-side, so the service-role key never
leaves the worker) and return it along with the resulting ``file_key``.

The frontend then:
  1. PUT the file at the returned URL
  2. Insert a ``meetings`` row with the ``file_key`` (RLS allows this
     because the user is a member of the target deal's org)
  3. Fire the ``meeting/uploaded`` Inngest event which kicks off the
     post-meeting pipeline.
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.dependencies import (
    AuthUser,
    get_current_user,
    get_service_supabase,
    get_user_supabase,
)
from supabase import Client

router = APIRouter()

RECORDINGS_BUCKET = "meeting-recordings"

# Application-level cap. Supabase Storage enforces a per-bucket ceiling at
# upload time, but checking here lets us reject obviously-too-large requests
# before minting a signed URL — and surface a clear error to the client.
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB


class UploadTicketRequest(BaseModel):
    deal_id: str
    filename: str
    content_type: Literal[
        "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav",
        "audio/mp4", "audio/m4a", "audio/webm", "audio/ogg",
        "video/mp4", "video/webm", "video/quicktime", "video/x-msvideo",
    ]
    # Browser File API gives us this for free — required so we can reject
    # over-cap uploads before consuming a signed-URL slot.
    size_bytes: int = Field(gt=0, le=MAX_UPLOAD_SIZE_BYTES)


class UploadTicketResponse(BaseModel):
    file_key: str
    upload_url: str
    token: str


@router.post("/upload-ticket", response_model=UploadTicketResponse)
async def create_upload_ticket(
    body: UploadTicketRequest,
    current_user: AuthUser = Depends(get_current_user),
    user_supabase: Client = Depends(get_user_supabase),
    service_supabase: Client = Depends(get_service_supabase),
) -> UploadTicketResponse:
    """Mint a signed upload URL for Supabase Storage.

    The resulting ``upload_url`` is a single-use PUT target. After a
    successful upload, the client creates the ``meetings`` row pointing at
    ``file_key`` and fires ``meeting/uploaded`` into Inngest.
    """
    # Confirm the caller can see this deal before minting a Storage path
    # under it. The user-scoped client respects RLS, so a returned row IS
    # the membership proof — without this, anyone could enumerate deal IDs
    # and obtain valid signed PUT URLs into another tenant's storage tree.
    deal_rows = (
        user_supabase.table("deals")
        .select("id")
        .eq("id", body.deal_id)
        .limit(1)
        .execute()
        .data
    )
    if not deal_rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deal not found",
        )

    ext = ("." + body.filename.rsplit(".", 1)[1]) if "." in body.filename else ""
    file_key = f"{body.deal_id}/{uuid.uuid4()}{ext}"

    try:
        result = service_supabase.storage.from_(RECORDINGS_BUCKET).create_signed_upload_url(
            file_key
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not create upload URL: {exc}",
        ) from exc

    # supabase-py returns {'signedURL': ..., 'token': ..., 'path': ...}
    upload_url = result.get("signedURL") or result.get("signed_url") or ""
    token = result.get("token", "")
    if not upload_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Upload URL missing from Supabase response",
        )

    return UploadTicketResponse(
        file_key=file_key, upload_url=upload_url, token=token
    )
