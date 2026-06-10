"""/internal/* — Provider ingest webhooks: Zoom recordings + Teams call records."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.internal._common import (
    MEETINGS_BUCKET,
    require_internal_token,
)
from app.db.deps import get_db
from app.db.models import (
    IntegrationCredential,
    Meeting,
    MeetingParticipant,
)
from app.storage import local as storage

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# /internal/zoom/ingest
# ---------------------------------------------------------------------------
class ZoomIngestRequest(BaseModel):
    zoom_meeting_id: str
    download_url: str
    topic: str | None = None


class ZoomIngestResponse(BaseModel):
    meeting_id: str | None
    status: str


@router.post(
    "/zoom/ingest",
    response_model=ZoomIngestResponse,
    dependencies=[Depends(require_internal_token)],
)
async def zoom_ingest(
    body: ZoomIngestRequest,
    session: Session = Depends(get_db),
) -> ZoomIngestResponse:
    """Handle a ``recording.completed`` Zoom webhook.

    Flow:
      1. Try to attach the recording to an existing calendar-synced meeting
         (match on ``external_provider='zoom'`` + ``external_event_id``).
      2. If none, create an unassigned ``meetings`` row so the user can
         associate it with a deal from the calendar page.
      3. Download the recording into local object storage using any active
         Zoom OAuth credential in the org (best-effort).
      4. Fire ``meeting/uploaded`` so the post-meeting pipeline runs.
    """
    from app.services.oauth_tokens import decrypt_token

    zoom_meeting_id = str(body.zoom_meeting_id)

    # 1) Attribution: find an existing meetings row for this external event.
    match = session.scalar(
        select(Meeting)
        .where(Meeting.external_provider == "zoom")
        .where(Meeting.external_event_id == zoom_meeting_id)
        .limit(1)
    )

    if match is not None:
        meeting = match
        meeting_id = meeting.id
        org_id = meeting.org_id
        deal_id = meeting.deal_id or ""
    else:
        # Create an unassigned meeting. Pick any org with an active zoom
        # credential; if we can't find one, we have nothing to bind to.
        cred = session.scalar(
            select(IntegrationCredential)
            .where(IntegrationCredential.platform == "zoom")
            .where(IntegrationCredential.is_active.is_(True))
            .limit(1)
        )
        if cred is None:
            logger.warning(
                "zoom_ingest_no_credential zoom_meeting_id=%s", zoom_meeting_id
            )
            return ZoomIngestResponse(meeting_id=None, status="no_credential")
        org_id = cred.org_id
        created_by = cred.user_id
        new_meeting = Meeting(
            org_id=org_id,
            deal_id=None,
            title=body.topic or "Zoom recording",
            source="zoom",
            external_provider="zoom",
            external_event_id=zoom_meeting_id,
            status="uploading",
            created_by=created_by,
        )
        session.add(new_meeting)
        session.flush()
        meeting_id = new_meeting.id
        deal_id = ""

    # 2) Look up any active zoom credential (prefer one in the matched org).
    cred_for_org = session.scalar(
        select(IntegrationCredential)
        .where(IntegrationCredential.platform == "zoom")
        .where(IntegrationCredential.is_active.is_(True))
        .where(IntegrationCredential.org_id == org_id)
        .limit(1)
    )
    auth_header: dict[str, str] = {}
    if cred_for_org and cred_for_org.access_token_encrypted:
        try:
            zoom_access = decrypt_token(cred_for_org.access_token_encrypted)
            auth_header = {"Authorization": f"Bearer {zoom_access}"}
        except Exception:
            logger.exception("zoom_ingest_decrypt_failed")

    # 3) Download.
    try:
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.get(
                body.download_url,
                headers=auth_header,
                follow_redirects=True,
            )
            resp.raise_for_status()
            file_bytes = resp.content
    except Exception as exc:
        logger.exception("zoom_ingest_download_failed")
        raise HTTPException(
            status_code=502, detail=f"Zoom download failed: {exc}"
        ) from exc

    file_key = f"zoom/{meeting_id}.mp4"
    storage.save_bytes(MEETINGS_BUCKET, file_key, file_bytes)

    # 4) Flip status + fire the post-meeting pipeline.
    meeting_to_update = session.get(Meeting, meeting_id)
    if meeting_to_update is not None:
        meeting_to_update.file_key = file_key
        meeting_to_update.status = "uploaded"
        meeting_to_update.source_url = body.download_url
        session.flush()

    from app.integrations.inngest import send_event

    await send_event(
        "meeting/uploaded",
        {"meeting_id": meeting_id, "deal_id": deal_id},
    )

    logger.info(
        "zoom_ingest_done meeting_id=%s bytes=%d", meeting_id, len(file_bytes)
    )
    return ZoomIngestResponse(meeting_id=meeting_id, status="uploaded")


# ---------------------------------------------------------------------------
# /internal/teams/ingest-call-record
# ---------------------------------------------------------------------------
class TeamsIngestRequest(BaseModel):
    call_record_id: str
    tenant_id: str | None = None


class TeamsIngestResponse(BaseModel):
    call_record_id: str
    organizer: str | None
    participant_count: int
    handled: bool


@router.post(
    "/teams/ingest-call-record",
    response_model=TeamsIngestResponse,
    dependencies=[Depends(require_internal_token)],
)
async def teams_ingest_call_record(
    body: TeamsIngestRequest,
    session: Session = Depends(get_db),
) -> TeamsIngestResponse:
    """Fetch a Teams call record via Graph API and log its structure.

    This mirrors what the old Celery ``process_teams_webhook`` did: locate
    an active Teams credential, use its access token to fetch the expanded
    call record, and record participants/organizer. Full attribution to a
    deal/meeting is a product decision left to a later phase.
    """
    from uuid import UUID

    from app.services.oauth_tokens import get_valid_access_token

    # Accept both the new unified 'microsoft' platform and the legacy 'teams'.
    cred = session.scalar(
        select(IntegrationCredential)
        .where(IntegrationCredential.platform.in_(["microsoft", "teams"]))
        .where(IntegrationCredential.is_active.is_(True))
        .limit(1)
    )
    if cred is None:
        logger.warning(
            "teams_ingest_no_credential call_record_id=%s", body.call_record_id
        )
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    cred_org_id = cred.org_id
    cred_user_id = cred.user_id
    # Legacy rows may carry platform="teams"; the refresh dispatch only knows
    # "microsoft" (one OAuth app backs Teams/Outlook/Calendar).
    cred_platform = "microsoft" if cred.platform == "teams" else cred.platform
    try:
        access_token = await get_valid_access_token(
            session,
            org_id=UUID(cred_org_id),
            user_id=UUID(cred_user_id),
            platform=cred_platform,  # type: ignore[arg-type]
        )
    except Exception:
        logger.exception("teams_ingest_token_resolve_failed")
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    from app.integrations.teams.graph_client import GraphAPIClient

    graph = GraphAPIClient()
    try:
        record = await graph.get_call_record(access_token, body.call_record_id)
    except Exception:
        logger.exception(
            "teams_ingest_fetch_failed call_record_id=%s", body.call_record_id
        )
        return TeamsIngestResponse(
            call_record_id=body.call_record_id,
            organizer=None,
            participant_count=0,
            handled=False,
        )

    organizer = ((record.get("organizer") or {}).get("user") or {}).get("displayName")
    participants = record.get("participants", []) or []

    # Try to attach the call record to a calendar-synced meeting so analysis
    # lands on the same row the user already knows about. Teams' call record
    # doesn't carry the calendar event id directly; match on session start
    # time to the nearest upcoming event for the organizer (best-effort).
    sessions = record.get("sessions", []) or []
    start_times = [s.get("startDateTime") for s in sessions if s.get("startDateTime")]
    matched_meeting: Meeting | None = None
    if start_times:
        probe = start_times[0]
        # Find a 'microsoft' synced meeting in the same org within ±30 min of
        # the session start. ISO-8601 UTC timestamps sort lexically, so a
        # string window works as long as both sides are UTC ISO strings.
        try:
            probe_dt = datetime.fromisoformat(str(probe).replace("Z", "+00:00"))
            window_start = (probe_dt - timedelta(minutes=30)).isoformat()
            window_end = (probe_dt + timedelta(minutes=30)).isoformat()
        except ValueError:
            window_start = window_end = probe  # unparseable → exact-match fallback
        matched_meeting = session.scalar(
            select(Meeting)
            .where(Meeting.org_id == cred_org_id)
            .where(Meeting.external_provider == "microsoft")
            .where(Meeting.meeting_date >= window_start)
            .where(Meeting.meeting_date <= window_end)
            .order_by(Meeting.meeting_date)
            .limit(1)
        )

    if matched_meeting is None:
        new_meeting = Meeting(
            org_id=cred_org_id,
            deal_id=None,
            title=organizer and f"Teams call w/ {organizer}" or "Teams call",
            source="teams",
            external_provider="microsoft",
            external_event_id=body.call_record_id,
            status="uploaded",
            created_by=cred_user_id,
        )
        session.add(new_meeting)
        session.flush()
        meeting_id = new_meeting.id
    else:
        meeting_id = matched_meeting.id
        matched_meeting.status = "uploaded"
        session.flush()

    # Persist participants. Graph returns either the legacy `participants`
    # list or `participants_v2`; both shapes carry user.displayName and an
    # identifying id we reuse as the upsert key on
    # (meeting_id, recall_participant_id) so retries are idempotent.
    persisted = 0
    for p in participants:
        identity = (p.get("user") or {}) if isinstance(p, dict) else {}
        display_name = (
            (identity.get("displayName") or p.get("displayName"))
            if isinstance(p, dict)
            else None
        )
        upn = (
            identity.get("userPrincipalName")
            or (p.get("userPrincipalName") if isinstance(p, dict) else None)
        )
        external_id = (
            (p.get("id") if isinstance(p, dict) else None)
            or identity.get("id")
        )
        if not external_id and not display_name:
            continue
        try:
            existing_part = None
            if external_id is not None:
                existing_part = session.scalar(
                    select(MeetingParticipant)
                    .where(MeetingParticipant.meeting_id == meeting_id)
                    .where(
                        MeetingParticipant.recall_participant_id == str(external_id)
                    )
                    .limit(1)
                )
            speaker_label = display_name or upn or external_id or "Unknown"
            if existing_part is not None:
                existing_part.speaker_label = speaker_label
                existing_part.speaker_name = display_name
                existing_part.email_address = upn
            else:
                session.add(
                    MeetingParticipant(
                        meeting_id=meeting_id,
                        speaker_label=speaker_label,
                        speaker_name=display_name,
                        email_address=upn,
                        recall_participant_id=(
                            str(external_id) if external_id is not None else None
                        ),
                    )
                )
            session.flush()
            persisted += 1
        except Exception:
            logger.exception(
                "teams_ingest_participant_persist_failed meeting_id=%s",
                meeting_id,
            )

    logger.info(
        "teams_call_record_fetched call_record_id=%s organizer=%s "
        "participants=%d persisted=%d meeting_id=%s",
        body.call_record_id,
        organizer,
        len(participants),
        persisted,
        meeting_id,
    )
    return TeamsIngestResponse(
        call_record_id=body.call_record_id,
        organizer=organizer,
        participant_count=len(participants),
        handled=True,
    )


