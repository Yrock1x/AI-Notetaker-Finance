"""FastAPI dependencies bridging auth → DB session → scoped Principal.

Kept separate from app/db/engine.py to avoid importing app.dependencies (and its
Supabase clients) into the low-level engine module. WS4 routers depend on
``get_db`` for a session and ``get_principal`` for tenant scoping. During the
transition the user id still comes from the existing JWT verifier; WS5 swaps
that source without changing these signatures.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.engine import get_db
from app.db.scope import Principal, load_principal
from app.dependencies import AuthUser, get_current_user

__all__ = ["get_db", "get_principal"]


def get_principal(
    user: AuthUser = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Principal:
    """The authenticated user plus their org memberships, for query scoping."""
    return load_principal(session, str(user.id))
