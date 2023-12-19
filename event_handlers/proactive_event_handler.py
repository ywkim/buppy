from __future__ import annotations
from google.cloud import firestore
from celery import Celery

from utils.proactive_messaging_utils import should_reschedule
from celery_tasks.proactive_messaging_task import schedule_proactive_message

def process_proactive_event(
    db: firestore.Client,
    celery_app: Celery,
    event_data: dict
) -> None:
    """
    Processes proactive messaging events.

    Args:
        db (firestore.Client): Firestore client for database operations.
        celery_app (Celery): Celery application instance for task scheduling.
        event_data (dict): Parsed data from the proactive event.
    """
    bot_id = event_data["id"]
    bot_ref = db.collection("Bots").document(bot_id)
    bot_doc = bot_ref.get().to_dict()

    if "proactive_messaging" in bot_doc:
        proactive_config = bot_doc["proactive_messaging"]
        if should_reschedule(
            event_data["oldValue"]["fields"]["proactive_messaging"], proactive_config
        ):
            schedule_proactive_message(celery_app, bot_ref, proactive_config, bot_id)
