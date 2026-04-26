"""Provider webhooks — Zoom, Teams, Slack.

All endpoints verify their provider's HMAC signature and then acknowledge.
Event handling (e.g. "a Zoom recording finished, enqueue the meeting
pipeline") is dispatched into Inngest; see the migration plan Phase 5.
Until Inngest is wired up these handlers just log + ack, which is the
correct no-op behaviour (Zoom retries and we'll catch up once the queue
exists)."""

import hashlib
import hmac
import logging
import time
from collections import OrderedDict

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

WEBHOOK_TIMESTAMP_TOLERANCE = 300  # 5 minutes


# ---------------------------------------------------------------------------
# Replay protection
#
# Without dedupe, a captured webhook can be re-played within the 5-min
# timestamp tolerance window. Cache the (timestamp, signature) pair after
# signature verification and reject repeats. Bounded LRU keeps memory
# constant. Per-process scope is fine for single-worker patterns; with
# multiple uvicorn workers, replays may slip through to a different worker
# but the receiver-side semantics (Inngest event idempotency, upserts
# keyed on provider message ids) absorb the duplicate work.
# ---------------------------------------------------------------------------
_SEEN_WEBHOOKS: OrderedDict[str, float] = OrderedDict()
_SEEN_MAX_SIZE = 10000
_SEEN_TTL_SECONDS = WEBHOOK_TIMESTAMP_TOLERANCE * 2


def _is_replay(provider: str, signature: str, timestamp: str) -> bool:
    if not signature or not timestamp:
        return False
    key = f"{provider}:{timestamp}:{signature}"
    now = time.time()
    while _SEEN_WEBHOOKS:
        oldest_key, oldest_ts = next(iter(_SEEN_WEBHOOKS.items()))
        if now - oldest_ts > _SEEN_TTL_SECONDS:
            _SEEN_WEBHOOKS.popitem(last=False)
        else:
            break
    if key in _SEEN_WEBHOOKS:
        return True
    if len(_SEEN_WEBHOOKS) >= _SEEN_MAX_SIZE:
        _SEEN_WEBHOOKS.popitem(last=False)
    _SEEN_WEBHOOKS[key] = now
    return False


def _verify_zoom_signature(request: Request, raw_body: bytes, settings) -> None:
    """Verify Zoom webhook request signature using HMAC-SHA256."""
    timestamp = request.headers.get("x-zm-request-timestamp", "")
    signature = request.headers.get("x-zm-signature", "")

    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing Zoom signature headers")

    try:
        if abs(time.time() - int(timestamp)) > WEBHOOK_TIMESTAMP_TOLERANCE:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp") from None

    message = f"v0:{timestamp}:{raw_body.decode()}"
    expected = "v0=" + hmac.new(
        settings.zoom_webhook_secret_token.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Zoom signature")

    if _is_replay("zoom", signature, timestamp):
        logger.warning("zoom_webhook_replay_blocked timestamp=%s", timestamp)
        raise HTTPException(status_code=409, detail="Replay detected")


def _verify_slack_signature(request: Request, raw_body: bytes, settings) -> None:
    """Verify Slack webhook request signature using HMAC-SHA256."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing Slack signature headers")

    try:
        if abs(time.time() - int(timestamp)) > WEBHOOK_TIMESTAMP_TOLERANCE:
            raise HTTPException(status_code=401, detail="Webhook timestamp expired")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp") from None

    sig_basestring = f"v0:{timestamp}:{raw_body.decode()}"
    expected = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    if _is_replay("slack", signature, timestamp):
        logger.warning("slack_webhook_replay_blocked timestamp=%s", timestamp)
        raise HTTPException(status_code=409, detail="Replay detected")


@router.post("/zoom")
async def zoom_webhook(
    request: Request,
) -> JSONResponse:
    """Handle Zoom webhook events (recording.completed, meeting.ended, etc.)."""
    raw_body = await request.body()
    body = await request.json()
    event = body.get("event", "")

    logger.info("Zoom webhook received: %s", event)

    settings = get_settings()

    # Verify signature for ALL requests including challenges
    _verify_zoom_signature(request, raw_body, settings)

    # Zoom URL validation challenge — must return plainToken + encryptedToken
    if event == "endpoint.url_validation":
        plain_token = body.get("payload", {}).get("plainToken", "")
        encrypted_token = hmac.new(
            settings.zoom_webhook_secret_token.encode(),
            plain_token.encode(),
            hashlib.sha256,
        ).hexdigest()
        return JSONResponse(
            content={"plainToken": plain_token, "encryptedToken": encrypted_token}
        )

    if event == "recording.completed":
        payload = body.get("payload", {}).get("object", {})
        meeting_id_str = payload.get("id", "")
        download_url = None
        for file in payload.get("recording_files", []):
            if file.get("recording_type") == "shared_screen_with_speaker_view":
                download_url = file.get("download_url")
                break
            if file.get("file_type") == "MP4":
                download_url = file.get("download_url")

        logger.info(
            "Zoom recording.completed for meeting %s, has_download=%s",
            meeting_id_str,
            bool(download_url),
        )
        if download_url:
            from app.integrations.inngest import send_event

            await send_event(
                "zoom/recording.completed",
                {
                    "zoom_meeting_id": meeting_id_str,
                    "download_url": download_url,
                    "topic": payload.get("topic"),
                },
            )

    elif event == "meeting.ended":
        logger.info("Zoom meeting.ended event received")

    return JSONResponse(content={"received": True})


@router.post("/teams", response_model=None)
async def teams_webhook(
    request: Request,
) -> JSONResponse | PlainTextResponse:
    """Handle Microsoft Teams webhook events.

    Teams uses a validation token handshake on subscription creation,
    and sends change notifications for subscribed resources.
    """
    # Teams subscription validation — must echo the validationToken as plain text
    validation_token = request.query_params.get("validationToken")
    if validation_token:
        logger.info("Teams subscription validation received")
        return PlainTextResponse(content=validation_token)

    body = await request.json()

    # Validate the client state token
    settings = get_settings()
    if not settings.teams_webhook_secret:
        raise HTTPException(status_code=500, detail="Teams webhook secret not configured")

    notifications = body.get("value", [])
    for notification in notifications:
        client_state = notification.get("clientState", "")
        if not hmac.compare_digest(client_state, settings.teams_webhook_secret):
            raise HTTPException(status_code=401, detail="Invalid Teams client state")

    for notification in notifications:
        resource = notification.get("resource", "")
        change_type = notification.get("changeType", "")

        logger.info(
            "Teams webhook: resource=%s, changeType=%s",
            resource,
            change_type,
        )

        if "communications/callRecords" in resource:
            # Resource path looks like "communications/callRecords('<id>')".
            call_record_id = ""
            if "('" in resource and "')" in resource:
                call_record_id = resource.split("('")[1].split("')")[0]
            elif "/" in resource:
                call_record_id = resource.rsplit("/", 1)[-1]

            tenant_id = notification.get("tenantId") or notification.get("tenant_id")

            if call_record_id:
                from app.integrations.inngest import send_event

                await send_event(
                    "teams/call_record.created",
                    {"call_record_id": call_record_id, "tenant_id": tenant_id},
                )
            logger.info("teams_call_record_available_for_ingest resource=%s", resource)

    return JSONResponse(content={"received": True})


@router.post("/slack/events")
async def slack_events(
    request: Request,
) -> JSONResponse:
    """Handle Slack event subscriptions.

    Slack sends a url_verification challenge during setup,
    and event callbacks for subscribed events.
    """
    raw_body = await request.body()
    body = await request.json()

    # Verify signature for ALL requests including challenges
    settings = get_settings()
    _verify_slack_signature(request, raw_body, settings)

    # Slack URL verification — return the challenge value
    if body.get("type") == "url_verification":
        logger.info("Slack URL verification challenge received")
        return JSONResponse(content={"challenge": body.get("challenge", "")})

    event = body.get("event", {})
    event_type = event.get("type", "")

    logger.info("Slack event received: %s", event_type)

    if event_type == "message":
        channel = event.get("channel", "")
        # Don't log message content for security
        logger.info("Slack message in channel %s", channel)

    elif event_type == "app_mention":
        logger.info("Slack app mention received")

    return JSONResponse(content={"received": True})


@router.post("/slack/commands")
async def slack_commands(
    request: Request,
) -> dict:
    """Handle Slack slash commands (e.g., /cognisuite status, /cognisuite meetings)."""
    raw_body = await request.body()
    settings = get_settings()
    _verify_slack_signature(request, raw_body, settings)

    form_data = await request.form()
    command = form_data.get("command", "")
    text = form_data.get("text", "")
    user_id = form_data.get("user_id", "")
    channel_id = form_data.get("channel_id", "")

    logger.info(
        "Slack command: command=%s text=%s user=%s channel=%s",
        command,
        text,
        user_id,
        channel_id,
    )

    # Parse subcommand
    parts = str(text).strip().split(maxsplit=1) if text else []
    subcommand = parts[0] if parts else "help"

    if subcommand == "help":
        return {
            "response_type": "ephemeral",
            "text": (
                "*CogniSuite Commands:*\n"
                "• `/cognisuite status` — Show recent meeting processing status\n"
                "• `/cognisuite meetings` — List recent meetings\n"
                "• `/cognisuite help` — Show this help message"
            ),
        }

    if subcommand == "status":
        return {
            "response_type": "ephemeral",
            "text": "Checking meeting processing status...",
        }

    if subcommand == "meetings":
        return {
            "response_type": "ephemeral",
            "text": "Fetching recent meetings...",
        }

    return {
        "response_type": "ephemeral",
        "text": "Unknown command. Use `/cognisuite help` for usage.",
    }
