"""/internal/* — Calendar sync + Microsoft Graph subscription management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.internal._common import (
    _dedupe_zoom_google_rows,
    require_internal_token,
)
from app.core.config import settings
from app.db.deps import get_db
from app.db.models import (
    GraphSubscription,
    IntegrationCredential,
    Meeting,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# /internal/calendar/sync — fan-in from Inngest cron
# ---------------------------------------------------------------------------
class CalendarSyncRequest(BaseModel):
    user_id: str
    org_id: str
    platform: str  # 'zoom' | 'microsoft' | 'google'
    lookahead_days: int = 14


class CalendarSyncResponse(BaseModel):
    platform: str
    events_seen: int
    meetings_upserted: int


@router.post(
    "/calendar/sync",
    response_model=CalendarSyncResponse,
    dependencies=[Depends(require_internal_token)],
)
async def calendar_sync(
    body: CalendarSyncRequest,
    session: Session = Depends(get_db),
) -> CalendarSyncResponse:
    """Pull upcoming events from the user's connected calendar and upsert
    them into ``meetings`` keyed on (org_id, external_provider, external_event_id).

    Synced rows land with ``deal_id = NULL`` until a user assigns one on
    the calendar page. The ``source`` column is populated based on the
    conferencing platform (zoom / teams / meet / outlook).
    """
    from uuid import UUID

    from app.services.oauth_tokens import get_valid_access_token

    if body.platform not in {"zoom", "microsoft", "google"}:
        raise HTTPException(400, f"Unsupported platform {body.platform}")

    org_uuid = UUID(body.org_id)
    user_uuid = UUID(body.user_id)
    now = datetime.now(UTC)
    time_max = now + timedelta(days=body.lookahead_days)

    access_token = await get_valid_access_token(
        session,
        org_id=org_uuid,
        user_id=user_uuid,
        platform=body.platform,  # type: ignore[arg-type]
    )

    events: list[dict] = []
    rows: list[dict] = []

    if body.platform == "zoom":
        from app.integrations.zoom.api_client import ZoomAPIClient

        client = ZoomAPIClient()
        events = await client.list_upcoming_meetings(access_token)
        for ev in events:
            start = ev.get("start_time")
            if not start:
                continue
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("topic") or "Zoom meeting",
                    "meeting_date": start,
                    "source": "zoom",
                    "source_url": ev.get("join_url"),
                    "external_event_id": str(ev.get("id")),
                    "external_provider": "zoom",
                    "status": "uploading",
                    "bot_enabled": True,
                    "created_by": str(user_uuid),
                }
            )

    elif body.platform == "microsoft":
        from app.integrations.teams.graph_client import GraphAPIClient

        graph = GraphAPIClient()
        events = await graph.get_calendar_events(
            access_token, user_id="me", time_min=now, time_max=time_max
        )
        for ev in events:
            start = (ev.get("start") or {}).get("dateTime")
            if not start:
                continue
            online = ev.get("onlineMeeting") or {}
            join_url = online.get("joinUrl")
            source = "teams" if join_url and "teams.microsoft.com" in join_url else "outlook"
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("subject") or "Meeting",
                    "meeting_date": start,
                    "source": source,
                    "source_url": join_url or ev.get("webLink"),
                    "external_event_id": ev.get("id"),
                    "external_provider": "microsoft",
                    "status": "uploading",
                    "bot_enabled": bool(join_url),
                    "created_by": str(user_uuid),
                }
            )

    elif body.platform == "google":
        from app.integrations.google.calendar_client import GoogleCalendarClient
        from app.integrations.zoom.urls import extract_zoom_url

        gcal = GoogleCalendarClient()
        events = await gcal.list_events(
            access_token, time_min=now, time_max=time_max
        )
        for ev in events:
            start = (ev.get("start") or {}).get("dateTime")
            if not start:
                continue  # all-day events don't have dateTime
            meet_url = GoogleCalendarClient.extract_meet_url(ev)
            # Zoom-via-Google case: event was created in Zoom (or pasted in
            # manually), Google stores the join URL in description/location.
            # Falling back here means the Google-sourced row can carry the
            # real Zoom URL + source='zoom' even before the Zoom OAuth sync
            # runs — the auto-schedule cron then has everything it needs.
            zoom_from_body = (
                None
                if meet_url
                else extract_zoom_url(ev.get("description"))
                or extract_zoom_url(ev.get("location"))
            )
            source, source_url = (
                ("meet", meet_url)
                if meet_url
                else ("zoom", zoom_from_body)
                if zoom_from_body
                else ("upload", ev.get("htmlLink"))
            )
            rows.append(
                {
                    "org_id": str(org_uuid),
                    "deal_id": None,
                    "title": ev.get("summary") or "Meeting",
                    "meeting_date": start,
                    "source": source,
                    "source_url": source_url,
                    "external_event_id": ev.get("id"),
                    "external_provider": "google",
                    "status": "uploading",
                    "bot_enabled": bool(meet_url or zoom_from_body),
                    "created_by": str(user_uuid),
                }
            )

    upserted = 0
    # meetings has a PARTIAL unique index
    #   (org_id, external_provider, external_event_id) WHERE external_event_id
    # IS NOT NULL — select-then-insert-or-update per row to honour it.
    for row in rows:
        existing = session.scalar(
            select(Meeting)
            .where(Meeting.org_id == row["org_id"])
            .where(Meeting.external_provider == row["external_provider"])
            .where(Meeting.external_event_id == row["external_event_id"])
            .limit(1)
        )
        if existing is not None:
            # Preserve user-set state that the provider would otherwise
            # clobber on every re-sync:
            #   bot_enabled — user's on/off toggle
            #   deal_id     — user's assignment via AssignMeetingDialog
            # Everything else (title, meeting_date, source_url, status)
            # is safe to refresh from the provider.
            for k, v in row.items():
                if k in ("bot_enabled", "deal_id"):
                    continue
                setattr(existing, k, v)
        else:
            session.add(Meeting(**row))
        upserted += 1
    session.flush()

    # Dedupe pass. When a user has both Google Calendar sync and Zoom sync
    # active, the same Zoom meeting shows up as two rows: one from Zoom
    # (source='zoom', real join URL) and one from Google (source='meet' or
    # 'upload' with an htmlLink fallback). Keep the Zoom row — it has the
    # authoritative join URL — and collapse any duplicate into it.
    #
    # We only look at the dates we just touched to keep the query bounded.
    _dedupe_zoom_google_rows(session, org_uuid, [r["meeting_date"] for r in rows])

    logger.info(
        "calendar_sync_complete platform=%s user=%s events=%d upserted=%d",
        body.platform,
        body.user_id,
        len(events),
        upserted,
    )
    return CalendarSyncResponse(
        platform=body.platform,
        events_seen=len(events),
        meetings_upserted=upserted,
    )


# ---------------------------------------------------------------------------
# /internal/calendar/list-active-integrations — used by the Inngest fan-out
# ---------------------------------------------------------------------------
class ListActiveIntegrationsResponse(BaseModel):
    integrations: list[dict]


# ---------------------------------------------------------------------------
# /internal/microsoft/ensure-subscription — keep Graph subscriptions alive
# ---------------------------------------------------------------------------
class EnsureSubscriptionRequest(BaseModel):
    user_id: str
    org_id: str
    resource: str = "communications/callRecords"


class EnsureSubscriptionResponse(BaseModel):
    subscription_id: str
    expiration: str
    action: str  # 'created' | 'renewed' | 'noop'


@router.post(
    "/microsoft/ensure-subscription",
    response_model=EnsureSubscriptionResponse,
    dependencies=[Depends(require_internal_token)],
)
async def ensure_microsoft_subscription(
    body: EnsureSubscriptionRequest,
    session: Session = Depends(get_db),
) -> EnsureSubscriptionResponse:
    """Idempotent — creates a subscription if none exists for this user/resource
    or renews one that's within 24h of expiring.

    Call weekly/nightly from the Inngest cron; the 4230-min expiry window
    means we must renew within ~2.9 days of creation.
    """
    import secrets
    from uuid import UUID

    from app.integrations.teams.graph_client import GraphAPIClient
    from app.services.oauth_tokens import get_valid_access_token

    org_uuid = UUID(body.org_id)
    user_uuid = UUID(body.user_id)
    now = datetime.now(UTC)
    renewal_threshold = now + timedelta(hours=24)

    access_token = await get_valid_access_token(
        session,
        org_id=org_uuid,
        user_id=user_uuid,
        platform="microsoft",
    )

    existing = session.scalar(
        select(GraphSubscription)
        .where(GraphSubscription.user_id == str(user_uuid))
        .where(GraphSubscription.resource == body.resource)
        .where(GraphSubscription.is_active.is_(True))
        .limit(1)
    )

    notification_url = (
        f"{(settings.public_api_url or '').rstrip('/')}/api/v1/webhooks/teams"
    )
    client_state = settings.microsoft_webhook_secret or secrets.token_urlsafe(32)

    graph = GraphAPIClient()

    if existing is not None:
        expiration_iso = existing.expiration
        expiration_dt = datetime.fromisoformat(expiration_iso.replace("Z", "+00:00"))
        if expiration_dt > renewal_threshold:
            return EnsureSubscriptionResponse(
                subscription_id=existing.id,
                expiration=expiration_iso,
                action="noop",
            )
        try:
            renewed = await graph.renew_subscription(
                access_token, existing.id, expiration_minutes=4230
            )
            existing.expiration = renewed["expirationDateTime"]
            session.flush()
            return EnsureSubscriptionResponse(
                subscription_id=existing.id,
                expiration=renewed["expirationDateTime"],
                action="renewed",
            )
        except Exception as exc:
            logger.exception("graph_subscription_renew_failed id=%s", existing.id)
            # Deactivate so the next run re-creates.
            existing.is_active = False
            session.flush()
            del exc  # flow through to create

    created = await graph.subscribe_to_call_records(
        access_token,
        notification_url=notification_url,
        client_state=client_state,
    )
    created_id = created["id"]
    sub = session.get(GraphSubscription, created_id)
    if sub is not None:
        sub.org_id = str(org_uuid)
        sub.user_id = str(user_uuid)
        sub.resource = body.resource
        sub.client_state = client_state
        sub.notification_url = notification_url
        sub.expiration = created["expirationDateTime"]
        sub.is_active = True
    else:
        session.add(
            GraphSubscription(
                id=created_id,
                org_id=str(org_uuid),
                user_id=str(user_uuid),
                resource=body.resource,
                client_state=client_state,
                notification_url=notification_url,
                expiration=created["expirationDateTime"],
                is_active=True,
            )
        )
    session.flush()
    return EnsureSubscriptionResponse(
        subscription_id=created_id,
        expiration=created["expirationDateTime"],
        action="created",
    )


@router.get(
    "/calendar/list-active-integrations",
    response_model=ListActiveIntegrationsResponse,
    dependencies=[Depends(require_internal_token)],
)
async def list_active_integrations(
    session: Session = Depends(get_db),
) -> ListActiveIntegrationsResponse:
    """Return every active ``(org_id, user_id, platform)`` tuple so the
    Inngest cron can fan out one sync event per connection.
    """
    rows = session.scalars(
        select(IntegrationCredential)
        .where(IntegrationCredential.is_active.is_(True))
        .where(
            IntegrationCredential.platform.in_(["zoom", "microsoft", "google"])
        )
    ).all()
    return ListActiveIntegrationsResponse(
        integrations=[
            {
                "org_id": r.org_id,
                "user_id": r.user_id,
                "platform": r.platform,
            }
            for r in rows
        ]
    )


