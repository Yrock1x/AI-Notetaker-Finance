from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_current_user, get_db_with_rls, get_org_id
from app.models.user import User
from app.schemas.integration import (
    BotSessionCreate,
    BotSessionResponse,
    IntegrationResponse,
    OAuthInitResponse,
)
from app.services.bot_service import BotService
from app.services.integration_service import IntegrationService

router = APIRouter()


# --- OAuth Connections ---


@router.get("/", response_model=list[IntegrationResponse])
async def list_integrations(
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> list[IntegrationResponse]:
    """List connected integrations for the current user."""
    settings = get_settings()
    service = IntegrationService(db, settings)
    credentials = await service.list_integrations(
        user_id=current_user.id, org_id=org_id
    )
    return [
        IntegrationResponse(
            platform=c.platform,
            is_active=c.is_active,
            scopes=c.scopes,
            connected_at=c.created_at,
        )
        for c in credentials
    ]


@router.post("/{platform}/connect", response_model=OAuthInitResponse)
async def initiate_oauth(
    platform: str,
    request: Request,
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> OAuthInitResponse:
    """Start OAuth flow for a platform (zoom, teams, slack, outlook)."""
    settings = get_settings()
    service = IntegrationService(db, settings)

    # Build callback URL from the current request
    base_url = str(request.base_url).rstrip("/")
    redirect_uri = f"{base_url}/api/v1/integrations/{platform}/callback"

    authorization_url = await service.initiate_oauth(
        user_id=current_user.id,
        org_id=org_id,
        platform=platform,
        redirect_uri=redirect_uri,
    )
    return OAuthInitResponse(authorization_url=authorization_url)


@router.get("/{platform}/callback")
async def oauth_callback(
    platform: str,
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db_with_rls),
    current_user: User = Depends(get_current_user),
    org_id: UUID = Depends(get_org_id),
) -> dict:
    """Handle OAuth callback from external platforms."""
    settings = get_settings()
    service = IntegrationService(db, settings)
    await service.handle_oauth_callback(
        user_id=current_user.id,
        org_id=org_id,
        platform=platform,
        code=code,
        state=state,
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
