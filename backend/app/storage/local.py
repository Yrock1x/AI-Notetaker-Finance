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


def object_path(bucket: str, key: str) -> Path:
    """Validated (traversal-safe) filesystem path for an object.

    Lets callers stream a file straight off disk (e.g. ``FileResponse``)
    instead of buffering the whole thing into memory via :func:`read_bytes`.
    """
    return _safe_path(bucket, key)


def delete(bucket: str, key: str) -> None:
    path = _safe_path(bucket, key)
    if path.exists():
        path.unlink()


def exists(bucket: str, key: str) -> bool:
    return _safe_path(bucket, key).is_file()


# ---- URL signing ----------------------------------------------------------
def _signing_key() -> str:
    if settings.storage_signing_key:
        return settings.storage_signing_key
    # Dev/test convenience only — production boot requires STORAGE_SIGNING_KEY
    # (config._require_prod_secrets), so storage signing never silently reuses
    # the shared internal token in prod.
    if not settings.is_production:
        return settings.worker_internal_token
    raise RuntimeError("STORAGE_SIGNING_KEY is not configured")


def sign(method: str, bucket: str, key: str, expires_at: int) -> str:
    # Bind the HTTP method into the signature so a GET (download) URL can't be
    # replayed as a PUT (overwrite) and vice-versa.
    msg = f"{method.upper()}:{bucket}:{key}:{expires_at}".encode()
    return hmac.new(_signing_key().encode(), msg, hashlib.sha256).hexdigest()


def make_signed_url(
    bucket: str, key: str, *, method: str = "GET", ttl_seconds: int = 3600
) -> str:
    exp = int(time.time()) + ttl_seconds
    sig = sign(method, bucket, key, exp)
    return f"/api/v1/storage/{bucket}/{key}?expires={exp}&sig={sig}"


def verify(method: str, bucket: str, key: str, expires_at: int, sig: str) -> bool:
    if int(time.time()) > expires_at:
        return False
    expected = sign(method, bucket, key, expires_at)
    return hmac.compare_digest(expected, sig)
