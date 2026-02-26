import hashlib
import hmac
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

WEBHOOK_TIMESTAMP_TOLERANCE = 300  # 5 minutes


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
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    message = f"v0:{timestamp}:{raw_body.decode()}"
    expected = "v0=" + hmac.new(
        settings.zoom_webhook_secret_token.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Zoom signature")


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
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    sig_basestring = f"v0:{timestamp}:{raw_body.decode()}"
    expected = "v0=" + hmac.new(
        settings.slack_signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")


@router.post("/zoom")
async def zoom_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Handle Zoom webhook events (recording.completed, meeting.ended, etc.)."""
    raw_body = await request.body()
    body = await request.json()
    event = body.get("event", "")

    logger.info("Zoom webhook received: %s", event)

    # Zoom URL validation challenge — must return plainToken + encryptedToken
    if event == "endpoint.url_validation":
        plain_token = body.get("payload", {}).get("plainToken", "")
        settings = get_settings()
        encrypted_token = hmac.new(
            settings.zoom_webhook_secret_token.encode(),
            plain_token.encode(),
            hashlib.sha256,
        ).hexdigest()
        return JSONResponse(
            content={"plainToken": plain_token, "encryptedToken": encrypted_token}
        )

    # Verify signature for all non-challenge events
    settings = get_settings()
    _verify_zoom_signature(request, raw_body, settings)

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
        # TODO: Trigger Celery pipeline to download and process recording

    elif event == "meeting.ended":
        logger.info("Zoom meeting.ended event received")

    return JSONResponse(content={"received": True})


@router.post("/teams", response_model=None)
async def teams_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
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

    # Validate the client state token matches our configured secret
    settings = get_settings()
    notifications = body.get("value", [])
    for notification in notifications:
        client_state = notification.get("clientState", "")
        if client_state and hasattr(settings, "teams_webhook_secret"):
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
            logger.info("Teams call record notification received")
            # TODO: Fetch call record details via Graph API and trigger processing

    return JSONResponse(content={"received": True})


@router.post("/slack/events")
async def slack_events(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """Handle Slack event subscriptions.

    Slack sends a url_verification challenge during setup,
    and event callbacks for subscribed events.
    """
    raw_body = await request.body()
    body = await request.json()

    # Slack URL verification — must return the challenge value (no signature on this)
    if body.get("type") == "url_verification":
        logger.info("Slack URL verification challenge received")
        return JSONResponse(content={"challenge": body.get("challenge", "")})

    # Verify signature for all non-challenge events
    settings = get_settings()
    _verify_slack_signature(request, raw_body, settings)

    event = body.get("event", {})
    event_type = event.get("type", "")

    logger.info("Slack event received: %s", event_type)

    if event_type == "message":
        channel = event.get("channel", "")
        text = event.get("text", "")
        logger.info("Slack message in channel %s: %s", channel, text[:50])

    elif event_type == "app_mention":
        logger.info("Slack app mention received")

    return JSONResponse(content={"received": True})


@router.post("/slack/commands")
async def slack_commands(
    request: Request,
) -> dict:
    """Handle Slack slash commands (e.g., /dealwise status, /dealwise meetings)."""
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
                "*DealWise AI Commands:*\n"
                "• `/dealwise status` — Show recent meeting processing status\n"
                "• `/dealwise meetings` — List recent meetings\n"
                "• `/dealwise help` — Show this help message"
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
        "text": f"Unknown command: `{subcommand}`. Use `/dealwise help` for usage.",
    }
