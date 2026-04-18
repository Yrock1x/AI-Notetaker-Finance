"""Thin Inngest event-send helper for the Python worker.

The worker fires events into Inngest whenever a provider webhook arrives
(Zoom/Teams/Recall). Inngest's ingestion API is a simple JSON POST to
``https://inn.gs/e/{event_key}`` — no Python SDK needed.

Docs: https://www.inngest.com/docs/events
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

INNGEST_INGEST_URL = "https://inn.gs/e"


async def send_event(name: str, data: dict[str, Any]) -> None:
    """Fire an event into Inngest. No-op if INNGEST_EVENT_KEY is unset.

    Failures are logged but never raised — webhook endpoints should still
    200 back to the provider so they don't retry forever on transient
    Inngest outages. Inngest has its own retry/durability; we're just
    responsible for getting the event to them once.
    """
    if not settings.inngest_event_key:
        logger.warning(
            "inngest_event_dropped_no_key event=%s (set INNGEST_EVENT_KEY)", name
        )
        return

    payload = {"name": name, "data": data}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                f"{INNGEST_INGEST_URL}/{settings.inngest_event_key}",
                json=payload,
            )
            if resp.status_code >= 400:
                logger.error(
                    "inngest_event_send_failed event=%s status=%d body=%s",
                    name,
                    resp.status_code,
                    resp.text[:300],
                )
                return
            logger.info("inngest_event_sent event=%s", name)
    except Exception as exc:  # noqa: BLE001
        logger.exception("inngest_event_send_error event=%s error=%s", name, exc)
