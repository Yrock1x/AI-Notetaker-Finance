import structlog
from celery import Task

logger = structlog.get_logger(__name__)


class BaseTask(Task):
    """Base task with shared error handling and status tracking."""

    autoretry_for = (Exception,)
    max_retries = 3
    retry_backoff = True
    retry_backoff_max = 600  # 10 minutes max backoff

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(
            "task_failed",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
            args=args,
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        logger.warning(
            "task_retrying",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        logger.info(
            "task_succeeded",
            task_name=self.name,
            task_id=task_id,
        )
        super().on_success(retval, task_id, args, kwargs)
