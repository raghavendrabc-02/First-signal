import os

from celery import Celery
from celery.schedules import crontab
from dotenv import load_dotenv

load_dotenv()

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")

if not CELERY_BROKER_URL:
    raise RuntimeError("CELERY_BROKER_URL is not set")

celery_app = Celery(
    "firstsignal",
    broker=CELERY_BROKER_URL,
    include=["app.tasks"],
)

celery_app.conf.timezone = "Asia/Kolkata"

celery_app.conf.beat_schedule = {
    "run-daily-pipeline": {
        "task": "app.tasks.run_daily_pipeline",
        "schedule": crontab(hour=8, minute=0),
    },
}