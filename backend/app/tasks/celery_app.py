import ssl

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "dealwise",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

# Configure SSL for rediss:// URLs (e.g. Upstash)
if settings.redis_url.startswith("rediss://"):
    celery_app.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_NONE}

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "app.tasks.transcription.*": {"queue": "transcription"},
        "app.tasks.embedding.*": {"queue": "embedding"},
        "app.tasks.analysis.*": {"queue": "analysis"},
        "app.tasks.meeting_bot.*": {"queue": "bot"},
        "app.tasks.integrations.*": {"queue": "integrations"},
        "app.tasks.notifications.*": {"queue": "notifications"},
    },

    # Default queue
    task_default_queue="default",

    # Retry settings
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Result expiration
    result_expires=86400,  # 24 hours

    # Task time limits
    task_soft_time_limit=300,  # 5 minutes
    task_time_limit=600,  # 10 minutes hard limit

    # Autodiscover tasks
    include=[
        "app.tasks.transcription",
        "app.tasks.embedding",
        "app.tasks.analysis",
        "app.tasks.meeting_bot",
        "app.tasks.integrations",
        "app.tasks.notifications",
    ],
)
