import asyncio
from uuid import UUID

import structlog

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.integrations.recall.client import RecallClient
from app.services.bot_service import BotService
from app.tasks.base import BaseTask
from app.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(base=BaseTask, bind=True, queue="bot")
def start_bot_session(self, session_id: str) -> str:
    """Launch meeting bot to join a scheduled meeting via Recall.ai."""

    async def _start():
        settings = get_settings()
        recall = RecallClient(api_key=settings.recall_api_key or None)

        async with async_session_factory() as db:
            bot_svc = BotService(db)
            session = await bot_svc.get_session(UUID(session_id))

            await bot_svc.update_bot_status(UUID(session_id), "joining")
            await db.commit()

            bot_data = await recall.create_bot(
                meeting_url=session.meeting_url,
                bot_name="Deal Companion Notetaker",
            )

            await bot_svc.update_bot_status(UUID(session_id), "recording")
            await db.commit()

            logger.info(
                "bot_session_started",
                session_id=session_id,
                recall_bot_id=bot_data.get("id"),
                demo=recall.is_demo,
            )
            return session_id

    return _run_async(_start())


@celery_app.task(base=BaseTask, bind=True, queue="bot")
def stop_bot_session(self, session_id: str) -> str:
    """Stop the bot and finalize the recording."""

    async def _stop():
        async with async_session_factory() as db:
            bot_svc = BotService(db)
            await bot_svc.update_bot_status(UUID(session_id), "completed")
            await db.commit()
            logger.info("bot_session_stopped", session_id=session_id)
            return session_id

    return _run_async(_stop())


@celery_app.task(base=BaseTask, bind=True, queue="bot")
def process_bot_recording(self, session_id: str) -> str:
    """Fetch transcript from Recall.ai and store segments."""

    async def _process():
        settings = get_settings()
        recall = RecallClient(api_key=settings.recall_api_key or None)

        async with async_session_factory() as db:
            bot_svc = BotService(db)
            await bot_svc.get_session(UUID(session_id))

            transcript_data = await recall.get_transcript(session_id)

            logger.info(
                "bot_recording_processed",
                session_id=session_id,
                segment_count=len(transcript_data),
                demo=recall.is_demo,
            )

            await bot_svc.update_bot_status(UUID(session_id), "completed")
            await db.commit()
            return session_id

    return _run_async(_process())
