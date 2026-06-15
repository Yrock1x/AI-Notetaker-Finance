"""CogniVault "Connect a deal to a VDR" endpoints.

A user connects a CogniScribe deal to a CogniVault VDR they administer. We
delegate the *VDR-admin* check entirely to CogniVault's OAuth consent screen
(it won't issue a ``code`` to a non-admin); on our side a user only needs access
to the deal (org membership, via ``scoped_deal_or_404``). The result is a
per-deal ``deal_vdr_connections`` row whose ``status``/``share_scopes`` are the
opt-in gate the partner API (/partner/v1) filters on.

Flow (mirrors app/api/v1/integrations.py, adapted to carry a deal_id + store a
per-deal connection instead of a per-user credential):

    POST /deals/{id}/connect  -> {authorization_url}  (browser redirects there)
    GET  /callback            <- CogniVault, after consent (no session cookie;
                                 the signed state carries org/user/deal)
    GET/PATCH/DELETE /deals/{id}/connection  -> manage the live connection
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.store._common import get_db, get_principal, scoped_deal_or_404
from app.core.config import settings
from app.db.audit import record_audit
from app.db.base import utcnow_iso
from app.db.models import DealVdrConnection
from app.db.scope import Principal, deal_org_id
from app.integrations.cognivault import SHAREABLE_SCOPES
from app.integrations.cognivault import oauth as cognivault_oauth
from app.schemas.common import BaseSchema
from app.services.oauth_tokens import (
    build_vdr_connect_state,
    encrypt_token,
    verify_vdr_connect_state,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------
class VdrConnectionResponse(BaseSchema):
    connected: bool
    status: str | None = None
    vdr_id: str | None = None
    vdr_name: str | None = None
    share_scopes: list[str] = []
    connected_at: str | None = None


class VdrShareScopesUpdate(BaseSchema):
    share_scopes: list[str]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _redirect_uri() -> str:
    base = (settings.public_api_url or "http://localhost:8000").rstrip("/")
    return f"{base}/api/v1/cognivault/callback"


def _active_connection(session: Session, deal_id: str) -> DealVdrConnection | None:
    return session.scalar(
        select(DealVdrConnection).where(
            DealVdrConnection.deal_id == deal_id,
            DealVdrConnection.status == "active",
        )
    )


def _upsert_connection(
    session: Session,
    *,
    deal_id: str,
    org_id: str,
    user_id: str,
    vdr_id: str,
    vdr_name: str | None,
    tokens: dict,
) -> DealVdrConnection:
    """Create or re-activate the deal's single VDR connection."""
    conn = session.scalar(
        select(DealVdrConnection).where(DealVdrConnection.deal_id == deal_id)
    )
    if conn is None:
        conn = DealVdrConnection(
            deal_id=deal_id, org_id=org_id, connected_by=user_id,
            share_scopes=list(SHAREABLE_SCOPES),
        )
        session.add(conn)
    conn.provider = "cognivault"
    conn.org_id = org_id
    conn.vdr_id = vdr_id
    conn.vdr_name = vdr_name
    conn.status = "active"
    conn.connected_by = user_id
    conn.connected_at = utcnow_iso()
    conn.revoked_at = None
    # First connect → share everything; reconnect → preserve the user's choices.
    if not conn.share_scopes:
        conn.share_scopes = list(SHAREABLE_SCOPES)

    # The CogniVault token isn't on the partner read path; store it (encrypted)
    # only when an encryption key is configured, so dev without a key still works.
    access = tokens.get("access_token")
    refresh = tokens.get("refresh_token")
    can_encrypt = bool(settings.token_encryption_key)
    conn.access_token_encrypted = (
        encrypt_token(access) if access and can_encrypt else None
    )
    conn.refresh_token_encrypted = (
        encrypt_token(refresh) if refresh and can_encrypt else None
    )
    expires_in = tokens.get("expires_in")
    conn.token_expires_at = (
        (datetime.now(UTC) + timedelta(seconds=int(expires_in))).isoformat()
        if expires_in
        else None
    )
    session.flush()
    return conn


def _to_response(conn: DealVdrConnection | None) -> VdrConnectionResponse:
    if conn is None:
        return VdrConnectionResponse(connected=False)
    return VdrConnectionResponse(
        connected=True,
        status=conn.status,
        vdr_id=conn.vdr_id,
        vdr_name=conn.vdr_name,
        share_scopes=list(conn.share_scopes or []),
        connected_at=conn.connected_at,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/cognivault/deals/{deal_id}/connect
# ---------------------------------------------------------------------------
@router.post("/deals/{deal_id}/connect")
def connect_vdr(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> dict:
    if not cognivault_oauth.is_configured():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CogniVault OAuth is not configured",
        )
    deal = scoped_deal_or_404(session, principal, deal_id)
    state = build_vdr_connect_state(
        UUID(deal.org_id), UUID(principal.user_id), deal.id
    )
    url = cognivault_oauth.build_authorize_url(
        client_id=settings.cognivault_client_id,
        redirect_uri=_redirect_uri(),
        state=state,
        deal_id=deal.id,
        deal_name=deal.name,
    )
    logger.info("cognivault_connect_initiated", deal_id=deal.id, user_id=principal.user_id)
    return {"authorization_url": url}


# ---------------------------------------------------------------------------
# GET /api/v1/cognivault/callback  (called by CogniVault after consent)
# ---------------------------------------------------------------------------
@router.get("/callback")
async def vdr_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    session: Session = Depends(get_db),
) -> RedirectResponse:
    frontend = (settings.frontend_url or "http://localhost:3000").rstrip("/")

    if not state:
        # Without state we can't know which deal to return to.
        raise HTTPException(400, "Missing state in OAuth callback")
    try:
        claims = verify_vdr_connect_state(state)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    org_id = claims["org_id"]
    user_id = claims["user_id"]
    deal_id = claims["deal_id"]
    return_to = f"{frontend}/deals/{deal_id}/settings"

    if error:
        logger.warning("cognivault_callback_provider_error", deal_id=deal_id, error=error)
        return RedirectResponse(url=f"{return_to}?error={error}", status_code=302)
    if not code:
        raise HTTPException(400, "Missing code in OAuth callback")

    # Defense in depth: the deal must still exist and belong to the state's org.
    if deal_org_id(session, deal_id) != org_id:
        return RedirectResponse(url=f"{return_to}?error=deal_not_found", status_code=302)

    tokens = await cognivault_oauth.exchange_code(
        client_id=settings.cognivault_client_id,
        client_secret=settings.cognivault_client_secret,
        redirect_uri=_redirect_uri(),
        code=code,
    )
    vdr_id = tokens.get("vdr_id")
    if not vdr_id:
        logger.error("cognivault_callback_missing_vdr", deal_id=deal_id)
        return RedirectResponse(url=f"{return_to}?error=missing_vdr", status_code=302)

    _upsert_connection(
        session,
        deal_id=deal_id,
        org_id=org_id,
        user_id=user_id,
        vdr_id=vdr_id,
        vdr_name=tokens.get("vdr_name"),
        tokens=tokens,
    )
    record_audit(
        session,
        org_id=org_id,
        user_id=user_id,
        action="share",
        resource_type="deal",
        resource_id=deal_id,
        deal_id=deal_id,
        details={"target": "cognivault", "vdr_id": vdr_id},
    )
    return RedirectResponse(url=f"{return_to}?connected=cognivault", status_code=302)


# ---------------------------------------------------------------------------
# GET /api/v1/cognivault/deals/{deal_id}/connection
# ---------------------------------------------------------------------------
@router.get("/deals/{deal_id}/connection", response_model=VdrConnectionResponse)
def get_connection(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> VdrConnectionResponse:
    deal = scoped_deal_or_404(session, principal, deal_id)
    return _to_response(_active_connection(session, deal.id))


# ---------------------------------------------------------------------------
# PATCH /api/v1/cognivault/deals/{deal_id}/connection  (resource toggles)
# ---------------------------------------------------------------------------
@router.patch("/deals/{deal_id}/connection", response_model=VdrConnectionResponse)
def update_share_scopes(
    deal_id: str,
    payload: VdrShareScopesUpdate,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> VdrConnectionResponse:
    deal = scoped_deal_or_404(session, principal, deal_id)
    invalid = [s for s in payload.share_scopes if s not in SHAREABLE_SCOPES]
    if invalid:
        raise HTTPException(400, f"Unknown share scopes: {invalid}")
    conn = _active_connection(session, deal.id)
    if conn is None:
        raise HTTPException(404, "No active CogniVault connection for this deal")
    # Dedupe while preserving order.
    conn.share_scopes = list(dict.fromkeys(payload.share_scopes))
    record_audit(
        session,
        org_id=deal.org_id,
        user_id=principal.user_id,
        action="update_share",
        resource_type="deal",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"target": "cognivault", "share_scopes": conn.share_scopes},
    )
    session.flush()
    return _to_response(conn)


# ---------------------------------------------------------------------------
# DELETE /api/v1/cognivault/deals/{deal_id}/connection  (revoke)
# ---------------------------------------------------------------------------
@router.delete("/deals/{deal_id}/connection", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_vdr(
    deal_id: str,
    session: Session = Depends(get_db),
    principal: Principal = Depends(get_principal),
) -> None:
    deal = scoped_deal_or_404(session, principal, deal_id)
    conn = _active_connection(session, deal.id)
    if conn is None:
        return  # idempotent — already disconnected
    conn.status = "revoked"
    conn.revoked_at = utcnow_iso()
    conn.access_token_encrypted = None
    conn.refresh_token_encrypted = None
    record_audit(
        session,
        org_id=deal.org_id,
        user_id=principal.user_id,
        action="unshare",
        resource_type="deal",
        resource_id=deal.id,
        deal_id=deal.id,
        details={"target": "cognivault"},
    )
    session.flush()
