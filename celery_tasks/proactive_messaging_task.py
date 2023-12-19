from __future__ import annotations

from celery import Celery
from google.cloud import firestore
from google.cloud.firestore import Transaction

from utils.proactive_messaging_utils import ProactiveMessagingContext, calculate_next_schedule_time
from firestore_managers.proactive_messaging_manager import update_proactive_messaging_settings

def schedule_proactive_message(
    celery_app: Celery,
    bot_ref: firestore.DocumentReference,
    proactive_config: dict,
    bot_id: str
) -> None:
    """
    Schedules a proactive messaging task using Celery.

    Args:
        celery_app (Celery): The Celery application instance.
        bot_ref (firestore.DocumentReference): Reference to the Firestore document for the bot.
        proactive_config (dict): Configuration details for proactive messaging.
        bot_id (str): Unique identifier for the bot.

    Raises:
        Exception: If an error occurs during Firestore update, the scheduled task is revoked.
    """
    transaction = firestore.Client().transaction()
    update_proactive_messaging_settings(transaction, celery_app, bot_ref, proactive_config, bot_id)

def revoke_existing_tasks(celery_app: Celery, task_id: str) -> None:
    """
    Revokes the existing proactive messaging task in Celery.

    Args:
        celery_app (Celery): The Celery application instance.
        task_id (str): The ID of the task to be revoked.
    """
    if task_id:
        celery_app.control.revoke(task_id)
