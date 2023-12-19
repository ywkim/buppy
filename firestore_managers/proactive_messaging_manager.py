from __future__ import annotations

from google.cloud import firestore
from google.cloud.firestore import Transaction
from celery import Celery

from utils.proactive_messaging_utils import ProactiveMessagingContext, calculate_next_schedule_time

def update_proactive_messaging_settings(
    db_client: firestore.Client,
    celery_app: Celery,
    bot_ref: firestore.DocumentReference,
    proactive_config: dict,
    bot_id: str
) -> None:
    """
    Updates proactive messaging settings in Firestore and schedules a messaging task.

    Args:
        db_client (firestore.Client): Firestore client for database operations.
        celery_app (Celery): Celery application instance for task scheduling.
        bot_ref (firestore.DocumentReference): Reference to the Firestore document for the bot.
        proactive_config (dict): Configuration details for proactive messaging.
        bot_id (str): Unique identifier for the bot.
    """
    transaction = db_client.transaction()
    with transaction:
        bot_doc = bot_ref.get(transaction=transaction).to_dict()
        current_task_id = bot_doc.get("current_task_id", None)

        context = ProactiveMessagingContext(app=None, config=proactive_config, bot_id=bot_id)
        next_schedule_time = calculate_next_schedule_time(proactive_config)
        task = celery_app.send_task(
            'generate_and_send_proactive_message', args=[context], eta=next_schedule_time
        )
        try:
            transaction.update(
                bot_ref,
                {
                    "proactive_messaging.current_task_id": task.id,
                    "proactive_messaging.last_scheduled": next_schedule_time.isoformat(),
                },
            )
        except Exception as e:
            celery_app.control.revoke(task.id)
            raise e
        finally:
            revoke_existing_tasks(celery_app, current_task_id)

def update_task_id_in_firestore(
    db_client: firestore.Client,
    bot_id: str,
    task_id: str
) -> None:
    """
    Updates the current task ID in Firestore for the given bot.

    Args:
        db_client (firestore.Client): Firestore client for database operations.
        bot_id (str): The bot ID for which to update the task ID.
        task_id (str): The new task ID to be stored.
    """
    bot_ref = db_client.collection("Bots").document(bot_id)
    bot_ref.update({"proactive_messaging.current_task_id": task_id})

def revoke_existing_tasks(
    celery_app: Celery,
    task_id: str
) -> None:
    """
    Revokes the existing proactive messaging task in Celery.

    Args:
        celery_app (Celery): The Celery application instance.
        task_id (str): The ID of the task to be revoked.
    """
    if task_id:
        celery_app.control.revoke(task_id)
