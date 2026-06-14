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
from pydantic import ValidationError

from app.api.v1.recall_webhooks import (
    _SEEN_TTL_SECONDS,
    _SEEN_WEBHOOK_IDS,
    _is_replay,
)
from app.auth.tokens import issue_session_token, verify_session_token
from app.core.config import settings

# =============================================================================
# Session-JWT signature verification (self-issued HS256 tokens)
# =============================================================================


class TestSessionTokenVerification:
    """The self-issued session JWT must be cryptographically verified: a token
    signed with a different secret (e.g. after a key rotation, or a forgery)
    must not authenticate.
    """

    @pytest.fixture(autouse=True)
    def _restore_settings(self):
        original = settings.session_jwt_secret
        try:
            yield
        finally:
            settings.session_jwt_secret = original

    def test_accepts_correctly_signed_token(self):
        settings.session_jwt_secret = "the-real-session-secret"
        sub = str(uuid.uuid4())
        token = issue_session_token(sub, email="u@example.com")

        claims = verify_session_token(token)
        assert claims is not None
        assert claims["sub"] == sub
        assert claims["email"] == "u@example.com"

    def test_rejects_token_signed_with_wrong_secret(self):
        """A token minted under one secret must stop verifying once the signing
        secret changes — i.e. signatures are actually checked."""
        settings.session_jwt_secret = "secret-A-original"
        token = issue_session_token(str(uuid.uuid4()))

        settings.session_jwt_secret = "secret-B-rotated-different"
        assert verify_session_token(token) is None


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


# NOTE: the upload size cap moved from the (removed) /meetings/upload-ticket
# endpoint to the signed PUT handler — the real ingress point. Its regression
# test now lives in tests/unit/test_storage/test_files_api.py.


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
