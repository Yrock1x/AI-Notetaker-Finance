from datetime import datetime, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_current_user, get_db, get_db_with_rls, get_org_id
from app.models.user import User
from app.schemas.integration import (
    BotSessionCreate,
    BotSessionResponse,
    IntegrationResponse,
    OAuthInitResponse,
)
from app.services.bot_service import BotService
from app.services.integration_service import IntegrationService

logger = structlog.get_logger(__name__)

router = APIRouter()

# In-memory demo connection state (resets on restart)
_demo_connections: dict[str, bool] = {
    "zoom": False,
    "teams": False,
    "slack": False,
    "outlook": False,
}

PLATFORM_SCOPES = {
    "zoom": "meeting:read recording:read user:read",
    "teams": "OnlineMeetings.Read Calendars.Read User.Read",
    "slack": "channels:read chat:write commands",
    "outlook": "Calendars.Read Mail.Read",
}


# --- OAuth Connections ---


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> list[IntegrationResponse]:
    """List all integrations with their connection status."""
    settings = get_settings()
    now = datetime.now(timezone.utc)

    if settings.demo_mode:
        return [
            IntegrationResponse(
                platform=platform,
                is_active=_demo_connections.get(platform, False),
                scopes=PLATFORM_SCOPES.get(platform),
                connected_at=now,
            )
            for platform in ("zoom", "teams", "slack", "outlook")
        ]

    service = IntegrationService(db, settings)
    credentials = await service.list_integrations(
        user_id=current_user.id, org_id=org_id
    )
    connected = {c.platform: c for c in credentials}

    results = []
    for platform in ("zoom", "teams", "slack", "outlook"):
        if platform in connected:
            c = connected[platform]
            results.append(
                IntegrationResponse(
                    platform=c.platform,
                    is_active=c.is_active,
                    scopes=c.scopes,
                    connected_at=c.created_at,
                )
            )
        else:
            results.append(
                IntegrationResponse(
                    platform=platform,
                    is_active=False,
                    scopes=None,
                    connected_at=now,
                )
            )
    return results


@router.post("/{platform}/connect")
async def initiate_oauth(
    platform: str,
    request: Request,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> dict:
    """Start OAuth flow for a platform. In demo mode, instantly connects."""
    settings = get_settings()

    if settings.demo_mode:
        _demo_connections[platform] = True
        return {"connected": True, "platform": platform}

    service = IntegrationService(db, settings)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/integrations/{platform}/callback"

    authorization_url = await service.initiate_oauth(
        user_id=current_user.id,
        org_id=org_id,
        platform=platform,
        redirect_uri=redirect_uri,
    )
    return {"authorization_url": authorization_url}


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Handle OAuth callback from external platforms.

    The provider redirects the user here after consent, so there is no Bearer
    token on the request.  Instead, user_id and org_id are recovered from the
    base64-encoded *state* parameter that ``initiate_oauth`` created.

    TODO: Add HMAC signature or server-side nonce verification on the state
    token to prevent CSRF / state-forgery attacks.  Currently the state is
    only base64-encoded JSON, which is sufficient for development but must
    be hardened before production deployment.
    """
    settings = get_settings()

    # Decode user context from the state token
    state_data = IntegrationService.decode_state(state)
    user_id: UUID = state_data["user_id"]
    org_id: UUID = state_data["org_id"]

    # Reconstruct the redirect_uri (must match what was sent in initiate_oauth)
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/integrations/{platform}/callback"

    service = IntegrationService(db, settings)
    credential = await service.handle_oauth_callback(
        user_id=user_id,
        org_id=org_id,
        platform=platform,
        code=code,
        state=state,
        redirect_uri=redirect_uri,
    )

    logger.info(
        "oauth_callback_success",
        platform=platform,
        user_id=str(user_id),
        org_id=str(org_id),
    )
    return {"status": "connected", "platform": platform}


@router.delete("/{platform}/disconnect", status_code=204)
async def disconnect_integration(
    platform: str,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> None:
    """Disconnect an integration."""
    settings = get_settings()

    if settings.demo_mode:
        _demo_connections[platform] = False
        return

    service = IntegrationService(db, settings)
    await service.disconnect(
        user_id=current_user.id, org_id=org_id, platform=platform
    )


# --- Meeting Bot ---


@router.post("/bot/sessions", response_model=BotSessionResponse, status_code=201)
async def schedule_bot(
    payload: BotSessionCreate,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> BotSessionResponse:
    """Schedule a meeting bot to join a call."""
    service = BotService(db)
    session = await service.schedule_bot(
        org_id=org_id,
        deal_id=payload.deal_id,
        platform=payload.platform,
        meeting_url=payload.meeting_url,
        scheduled_start=payload.scheduled_start,
        created_by=current_user.id,
    )
    return BotSessionResponse.model_validate(session)


@router.get("/bot/sessions", response_model=list[BotSessionResponse])
async def list_bot_sessions(
    deal_id: UUID | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> list[BotSessionResponse]:
    """List meeting bot sessions."""
    service = BotService(db)
    result = await service.list_sessions(
        org_id=org_id, deal_id=deal_id, status=status
    )
    return [BotSessionResponse.model_validate(s) for s in result["items"]]


@router.delete("/bot/sessions/{session_id}", status_code=204)
async def cancel_bot_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
) -> None:
    """Cancel a scheduled bot session."""
    service = BotService(db)
    await service.cancel_bot(session_id)
