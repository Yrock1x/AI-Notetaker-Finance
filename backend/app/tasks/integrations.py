from app.tasks.base import BaseTask
from app.tasks.celery_app import celery_app


@celery_app.task(base=BaseTask, bind=True, queue="integrations")
def sync_calendar(self, org_id: str, user_id: str, platform: str) -> None:
    """Sync calendar events from Outlook/Teams. Detect meetings with video links."""
    raise NotImplementedError


@celery_app.task(base=BaseTask, bind=True, queue="integrations")
def process_zoom_webhook(self, payload: dict) -> None:
    """Handle Zoom webhook event (recording.completed, etc.)."""
    raise NotImplementedError


@celery_app.task(base=BaseTask, bind=True, queue="integrations")
def download_zoom_recording(self, recording_url: str, org_id: str, deal_id: str) -> str:
    """Download Zoom cloud recording and upload to S3."""
    raise NotImplementedError
