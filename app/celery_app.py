from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "firstsignal",
    broker="redis://localhost:6379/0",
    include=["app.tasks"],
)

celery_app.conf.timezone = "Asia/Kolkata"

celery_app.conf.beat_schedule = {
    "run-daily-pipeline": {
        "task": "app.tasks.run_daily_pipeline",
        "schedule": crontab(hour=8, minute=0),
    },
}