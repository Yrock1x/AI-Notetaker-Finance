from app.tasks.celery_app import celery_app
from app.tasks.base import BaseTask


@celery_app.task(base=BaseTask, bind=True, queue="bot")
def start_bot_session(self, session_id: str) -> str:
    """Launch meeting bot to join a scheduled meeting."""
    raise NotImplementedError


@celery_app.task(base=BaseTask, bind=True, queue="bot")
def stop_bot_session(self, session_id: str) -> str:
    """Stop the bot and finalize the recording."""
    raise NotImplementedError


@celery_app.task(base=BaseTask, bind=True, queue="bot")
def process_bot_recording(self, session_id: str) -> str:
    """Upload bot recording to S3 and create a Meeting record. Triggers processing pipeline."""
    raise NotImplementedError
