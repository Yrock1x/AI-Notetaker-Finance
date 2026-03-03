import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Base event that flows through the internal event bus."""

    event_type: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    org_id: UUID | None = None
    user_id: UUID | None = None
    deal_id: UUID | None = None
    data: dict[str, Any] = field(default_factory=dict)


# Event type constants
MEETING_UPLOADED = "meeting.uploaded"
MEETING_TRANSCRIBED = "meeting.transcribed"
MEETING_ANALYZED = "meeting.analyzed"
MEETING_READY = "meeting.ready"
MEETING_FAILED = "meeting.failed"
DEAL_CREATED = "deal.created"
DEAL_MEMBER_ADDED = "deal.member_added"
DEAL_MEMBER_REMOVED = "deal.member_removed"
DOCUMENT_UPLOADED = "document.uploaded"
DOCUMENT_PROCESSED = "document.processed"
ANALYSIS_COMPLETED = "analysis.completed"
QA_QUESTION_ASKED = "qa.question_asked"

EventHandler = Callable[[Event], Awaitable[None]]


class EventBus:
    """Simple in-process async event bus for decoupling modules."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        for handler in self._handlers.get(event.event_type, []):
            try:
                await handler(event)
            except Exception:
                logger.warning(
                    "event_handler_failed: event_type=%s handler=%s",
                    event.event_type,
                    handler.__name__,
                    exc_info=True,
                )


# Global event bus instance
event_bus = EventBus()
