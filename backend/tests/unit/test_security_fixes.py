"""Regression tests for the P0 security fixes.

Each test guards a specific finding from the security/scale audit. The
goal is to fail loudly if a future PR re-introduces the vulnerability
(e.g. someone re-adds verify_signature=False, drops the dedupe LRU, or
relaxes the upload size cap).

These are pure unit tests against module-level functions / Pydantic
schemas — no FastAPI TestClient or Supabase fixture needed.
"""

from __future__ import annotations

import time
import uuid

import pytest
from fastapi import HTTPException
from jose import jwt as jose_jwt
from pydantic import ValidationError

from app.api.v1.meetings_upload import MAX_UPLOAD_SIZE_BYTES, UploadTicketRequest
from app.api.v1.recall_webhooks import (
    _SEEN_TTL_SECONDS,
    _SEEN_WEBHOOK_IDS,
    _is_replay,
)
from app.dependencies import _verify_supabase_jwt
from app.core.config import settings


# =============================================================================
# P0 #1 — JWT signature verification (regression for verify_signature=False)
# =============================================================================


class TestJwtHs256Verification:
    """Guard against the verify_signature=False regression in
    backend/app/dependencies.py:_verify_supabase_jwt.

    Before the fix, ANY HS256 token decoded as authentic. After the fix:
    - HS256 path requires SUPABASE_JWT_SECRET to be configured
    - Tokens are verified cryptographically against that secret
    - A token signed with the wrong secret raises 401
    """

    @pytest.fixture(autouse=True)
    def _restore_settings(self):
        """Snapshot settings.supabase_jwt_secret around each test."""
        original = settings.supabase_jwt_secret
        try:
            yield
        finally:
            settings.supabase_jwt_secret = original

    def _make_hs256(self, secret: str, sub: str | None = None) -> str:
        return jose_jwt.encode(
            {"sub": sub or str(uuid.uuid4()), "email": "u@example.com"},
            secret,
            algorithm="HS256",
        )

    @pytest.mark.asyncio
    async def test_rejects_when_no_secret_configured(self):
        """HS256 token must be rejected when SUPABASE_JWT_SECRET is unset.

        Before the fix this path silently accepted unverified tokens.
        """
        settings.supabase_jwt_secret = ""
        token = self._make_hs256("any-secret-here")

        with pytest.raises(HTTPException) as exc:
            await _verify_supabase_jwt(token)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_token_signed_with_wrong_secret(self):
        """A forged HS256 token with the wrong secret must 401.

        This is the core regression: before the fix verify_signature=False
        meant any HS256 token decoded successfully regardless of its key.
        """
        settings.supabase_jwt_secret = "the-real-secret"
        forged = self._make_hs256("attacker-controlled-secret", sub=str(uuid.uuid4()))

        with pytest.raises(HTTPException) as exc:
            await _verify_supabase_jwt(forged)
        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_correctly_signed_token(self):
        """A token signed with the configured secret returns the claims."""
        secret = "matching-secret"
        settings.supabase_jwt_secret = secret
        sub = str(uuid.uuid4())
        token = self._make_hs256(secret, sub=sub)

        claims = await _verify_supabase_jwt(token)
        assert claims["sub"] == sub
        assert claims["email"] == "u@example.com"


# =============================================================================
# P0 #5 — Recall webhook replay protection (regression for the dedupe LRU)
# =============================================================================


class TestRecallReplayDedupe:
    """Guard the bounded-LRU replay-dedupe added to recall_webhooks.

    Before the fix, an attacker could capture a valid Recall webhook and
    re-play it within the 5-minute signature window.
    """

    def _clear(self) -> None:
        _SEEN_WEBHOOK_IDS.clear()

    def test_first_message_is_not_replay(self):
        self._clear()
        assert _is_replay("msg-1") is False

    def test_repeat_message_is_replay(self):
        self._clear()
        _is_replay("msg-2")
        assert _is_replay("msg-2") is True

    def test_distinct_messages_independent(self):
        self._clear()
        assert _is_replay("a") is False
        assert _is_replay("b") is False
        assert _is_replay("a") is True
        assert _is_replay("b") is True

    def test_empty_id_never_replay(self):
        """Without a webhook-id, dedupe is a no-op (legacy callers fall
        through to the upsert idempotency on recall_segment_id).
        """
        self._clear()
        assert _is_replay(None) is False
        assert _is_replay("") is False
        assert _is_replay(None) is False  # still false on second call

    def test_lru_evicts_after_ttl(self, monkeypatch):
        """An entry older than _SEEN_TTL_SECONDS is evicted on the next
        call so the cache stays bounded over time.
        """
        self._clear()
        # Stamp an old entry directly.
        _SEEN_WEBHOOK_IDS["old"] = time.time() - _SEEN_TTL_SECONDS - 1
        # A fresh insert triggers the eviction sweep.
        assert _is_replay("fresh") is False
        assert "old" not in _SEEN_WEBHOOK_IDS


# =============================================================================
# P2 — meetings_upload size cap + Pydantic schema discipline
# =============================================================================


class TestUploadTicketSizeCap:
    """Guard the 5GB application-level cap on meeting uploads."""

    def _payload(self, size: int) -> dict:
        return {
            "deal_id": str(uuid.uuid4()),
            "filename": "video.mp4",
            "content_type": "video/mp4",
            "size_bytes": size,
        }

    def test_accepts_under_cap(self):
        body = UploadTicketRequest(**self._payload(100_000_000))
        assert body.size_bytes == 100_000_000

    def test_accepts_at_cap(self):
        body = UploadTicketRequest(**self._payload(MAX_UPLOAD_SIZE_BYTES))
        assert body.size_bytes == MAX_UPLOAD_SIZE_BYTES

    def test_rejects_above_cap(self):
        with pytest.raises(ValidationError):
            UploadTicketRequest(**self._payload(MAX_UPLOAD_SIZE_BYTES + 1))

    def test_rejects_zero_size(self):
        with pytest.raises(ValidationError):
            UploadTicketRequest(**self._payload(0))

    def test_rejects_negative_size(self):
        with pytest.raises(ValidationError):
            UploadTicketRequest(**self._payload(-1))

    def test_size_required(self):
        """size_bytes was added as a required field — omitting it must
        fail loudly so callers can't bypass the cap.
        """
        body_without_size = {
            "deal_id": str(uuid.uuid4()),
            "filename": "video.mp4",
            "content_type": "video/mp4",
        }
        with pytest.raises(ValidationError) as exc:
            UploadTicketRequest(**body_without_size)
        assert "size_bytes" in str(exc.value)


# =============================================================================
# P2 — Pydantic BaseSchema extra="forbid" hardening
# =============================================================================


class TestBaseSchemaForbidExtra:
    """Guard that BaseSchema rejects unknown fields. A regression here
    would let frontend/worker contract drift slip through silently.
    """

    def test_base_schema_forbids_extra_keys(self):
        """Any schema extending BaseSchema must reject unknown keys."""
        from app.schemas.organization import OrgCreate

        with pytest.raises(ValidationError) as exc:
            OrgCreate(name="Org", slug="org", surprise_field="x")
        # Pydantic v2 phrasing: "Extra inputs are not permitted"
        assert "extra" in str(exc.value).lower() or "permitted" in str(exc.value).lower()
