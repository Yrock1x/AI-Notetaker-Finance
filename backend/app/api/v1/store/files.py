"""Storage endpoints: signed upload tickets + signed PUT/GET of objects.

Replaces Supabase Storage. The frontend asks for an upload ticket (scoped to a
deal it can access), then PUTs the file straight at the signed URL. Downloads
use the same signature scheme. The HMAC signature is the capability — the
PUT/GET handlers need no principal because a valid signature already proves the
caller was granted access when the URL was issued.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.db.scope import Principal
from app.schemas.common import BaseSchema
from app.storage import local

router = APIRouter()

# Buckets the frontend is allowed to upload into directly. ``deliverables`` are
# produced server-side, so they are not in this set.
UPLOADABLE_BUCKETS = {"deal-documents", "meeting-recordings"}

# Application-level cap on a single uploaded object (recordings are the large
# case). Enforced at the PUT handler — the real ingress point — so a holder of a
# valid signed URL can't stream an unbounded body into memory/disk.
MAX_UPLOAD_SIZE_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB


class UploadTicketRequest(BaseSchema):
    bucket: str
    deal_id: str
    filename: str


@router.post("/storage/upload-ticket")
def create_upload_ticket(
    payload: UploadTicketRequest,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> dict:
    if payload.bucket not in local.BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown bucket"
        )
    if payload.bucket not in UPLOADABLE_BUCKETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploads not allowed for this bucket",
        )
    scoped_deal_or_404(session, principal, payload.deal_id)

    ext = PurePosixPath(payload.filename).suffix
    key = f"{payload.deal_id}/{uuid4()}{ext}"
    return {
        "bucket": payload.bucket,
        "key": key,
        "upload_url": local.make_signed_url(payload.bucket, key, method="PUT"),
        "method": "PUT",
    }


@router.put("/storage/{bucket}/{key:path}")
async def put_object(
    bucket: str,
    key: str,
    request: Request,
    expires: int = Query(...),
    sig: str = Query(...),
) -> dict:
    if not local.verify("PUT", bucket, key, expires, sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired signature"
        )

    # Reject oversize uploads up front via Content-Length so we don't buffer a
    # huge body. Re-check the materialised length in case the header lied.
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,  # Content Too Large
            detail="Upload exceeds maximum allowed size",
        )
    data = await request.body()
    if len(data) > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=413,  # Content Too Large
            detail="Upload exceeds maximum allowed size",
        )
    local.save_bytes(bucket, key, data)
    return {"ok": True, "key": key}


@router.get("/storage/{bucket}/{key:path}")
def get_object(
    bucket: str,
    key: str,
    expires: int = Query(...),
    sig: str = Query(...),
) -> Response:
    if not local.verify("GET", bucket, key, expires, sig):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired signature"
        )
    if not local.exists(bucket, key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Stream straight off disk (sendfile + Range support) instead of buffering
    # the whole object — recordings can be multiple GB and would otherwise be
    # read fully into the worker's memory per download.
    return FileResponse(
        path=local.object_path(bucket, key),
        media_type="application/octet-stream",
    )
