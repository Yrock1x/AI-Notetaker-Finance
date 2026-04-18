"""OAuth + meeting-bot integration endpoints.

TEMPORARY STUB: the OAuth flow previously depended on a SQLAlchemy
``IntegrationService`` that stored Fernet-encrypted tokens in the
``integration_credentials`` table. That table now lives in Supabase and
the flow will be re-implemented against ``supabase-py`` in the Inngest
port PR (see plan Phase 5).

Until then these endpoints return 501 so callers fail fast rather than
appearing to "work" with a broken flow. The frontend integrations page
will show the OAuth cards as disabled.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

router = APIRouter()


@router.get("")
async def list_integrations() -> list[dict]:
    """Return an empty list until OAuth is re-implemented."""
    return []


@router.post("/{platform}/connect")
async def initiate_oauth(platform: str) -> dict:  # noqa: ARG001
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "OAuth connect is being reimplemented on Supabase; see the "
            "migration plan Phase 5."
        ),
    )


@router.get("/{platform}/callback")
async def oauth_callback(platform: str) -> dict:  # noqa: ARG001
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OAuth callback is being reimplemented on Supabase.",
    )


@router.delete("/{platform}/disconnect", status_code=204)
async def disconnect_integration(platform: str) -> None:  # noqa: ARG001
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OAuth disconnect is being reimplemented on Supabase.",
    )


@router.post("/bot/sessions", status_code=201)
async def schedule_bot() -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Bot scheduling is being reimplemented via Inngest + Recall; "
            "see the migration plan Phase 5."
        ),
    )


@router.get("/bot/sessions")
async def list_bot_sessions() -> list[dict]:
    """Return an empty list until bot scheduling is reimplemented.

    The frontend calendar page tolerates an empty list — it just means no
    bots are currently scheduled. Supabase RLS serves the actual
    ``meeting_bot_sessions`` reads directly from the browser now.
    """
    return []


@router.delete("/bot/sessions/{session_id}", status_code=204)
async def cancel_bot_session(session_id: str) -> None:  # noqa: ARG001
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Bot cancellation is being reimplemented.",
    )
