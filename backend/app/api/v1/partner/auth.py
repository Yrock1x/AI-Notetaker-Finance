"""M2M authentication for the CogniVault partner API.

A request authenticates with ``Authorization: Bearer <raw_key>``. We hash the
raw key (sha256) and look up an active ``PartnerApiKey`` by ``key_hash``. The key
is bound to exactly one org, and its ``scopes`` (a JSON list of strings) gate
which endpoints it may call. The matched key yields a :class:`PartnerContext`,
which can produce a :class:`Principal` scoped to that one org so the existing
``org_scoped`` / scope helpers can be reused unchanged.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import utcnow_iso
from app.db.deps import get_db
from app.db.models import PartnerApiKey
from app.db.scope import Principal


@dataclass(frozen=True)
class PartnerContext:
    """The authenticated partner key plus the single org it is scoped to."""

    key_id: str
    org_id: str
    scopes: tuple[str, ...]

    def principal(self) -> Principal:
        """A Principal scoped to this key's org (no admin orgs)."""
        return Principal(
            user_id=f"partner:{self.key_id}",
            org_ids=(self.org_id,),
            admin_org_ids=(),
        )


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def get_partner_context(
    authorization: str | None = Header(None),
    session: Session = Depends(get_db),
) -> PartnerContext:
    """Resolve a partner API key from the Authorization header.

    Raises 401 if the header is missing/malformed or the key is unknown or
    inactive. On success, bumps ``last_used_at`` and returns a PartnerContext.
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    scheme, _, raw_key = authorization.partition(" ")
    if scheme.lower() != "bearer" or not raw_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header",
        )

    key = session.scalar(
        select(PartnerApiKey).where(
            PartnerApiKey.key_hash == _hash_key(raw_key.strip()),
            PartnerApiKey.is_active.is_(True),
        )
    )
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )

    key.last_used_at = utcnow_iso()
    session.flush()

    return PartnerContext(
        key_id=key.id,
        org_id=key.org_id,
        scopes=tuple(key.scopes or ()),
    )


def require_scope(ctx: PartnerContext, scope: str) -> None:
    """Raise 403 unless the key carries the required scope."""
    if scope not in ctx.scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope: {scope}",
        )
