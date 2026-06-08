"""Local-filesystem object store + HMAC-signed URL helpers.

Replaces the three former Supabase Storage buckets
(``meeting-recordings``, ``deal-documents``, ``deliverables``) with files on
the worker's local disk under ``settings.storage_root/{bucket}/{key}``.

Access is gated by short-lived HMAC-SHA256 signatures issued by the worker:
the signature over ``"{bucket}:{key}:{expires_at}"`` IS the capability to
read or write that object until it expires.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

from app.core.config import settings

BUCKETS = {"meeting-recordings", "deal-documents", "deliverables"}


def _root() -> Path:
    return Path(settings.storage_root)


def _safe_path(bucket: str, key: str) -> Path:
    """Resolve ``{root}/{bucket}/{key}``, guaranteeing the result stays inside
    the bucket directory (defends against path traversal via the key)."""
    if bucket not in BUCKETS:
        raise ValueError(f"unknown bucket: {bucket!r}")
    if key.startswith("/"):
        raise ValueError(f"unsafe key: {key!r}")
    bucket_root = (_root() / bucket).resolve()
    candidate = (bucket_root / key).resolve()
    if not candidate.is_relative_to(bucket_root):
        raise ValueError(f"unsafe key: {key!r}")
    return candidate


# ---- object operations ----------------------------------------------------
def save_bytes(bucket: str, key: str, data: bytes) -> None:
    path = _safe_path(bucket, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def read_bytes(bucket: str, key: str) -> bytes:
    return _safe_path(bucket, key).read_bytes()


def delete(bucket: str, key: str) -> None:
    path = _safe_path(bucket, key)
    if path.exists():
        path.unlink()


def exists(bucket: str, key: str) -> bool:
    return _safe_path(bucket, key).is_file()


# ---- URL signing ----------------------------------------------------------
def _signing_key() -> str:
    return settings.storage_signing_key or settings.worker_internal_token


def sign(bucket: str, key: str, expires_at: int) -> str:
    msg = f"{bucket}:{key}:{expires_at}".encode()
    return hmac.new(_signing_key().encode(), msg, hashlib.sha256).hexdigest()


def make_signed_url(bucket: str, key: str, ttl_seconds: int = 3600) -> str:
    exp = int(time.time()) + ttl_seconds
    sig = sign(bucket, key, exp)
    return f"/api/v1/storage/{bucket}/{key}?expires={exp}&sig={sig}"


def verify(bucket: str, key: str, expires_at: int, sig: str) -> bool:
    if int(time.time()) > expires_at:
        return False
    expected = sign(bucket, key, expires_at)
    return hmac.compare_digest(expected, sig)
