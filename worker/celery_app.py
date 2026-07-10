"""
Celery Application — Production Queue
Used when CELERY_ENABLED=true in .env
Run worker: celery -A worker.celery_app worker --loglevel=info -Q high_priority,batch -c 2
Monitor:    celery -A worker.celery_app flower
"""
import os
from celery import Celery
from kombu import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "docextract",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["worker.tasks"],
)

celery_app.conf.update(
    # Queue routing
    task_queues=(
        Queue("high_priority", routing_key="high"),
        Queue("batch", routing_key="batch"),
        Queue("retry", routing_key="retry"),
    ),
    task_default_queue="high_priority",
    task_default_routing_key="high",

    # Reliability
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Results TTL (24 hours)
    result_expires=86400,

    # Retry
    task_max_retries=3,
    task_soft_time_limit=120,   # 2 min soft limit
    task_time_limit=180,        # 3 min hard limit

    # Timezone
    timezone="UTC",
    enable_utc=True,
)
