from __future__ import annotations

from celery import Celery
from google.cloud import firestore
from google.cloud.firestore import Transaction

from utils.proactive_messaging_utils import (
    ProactiveMessagingContext,
    calculate_next_schedule_time,
    should_reschedule,
)


@firestore.transactional
def update_proactive_messaging_settings(
    transaction: Transaction,
    celery_app: Celery,
    context: ProactiveMessagingContext,
    bot_ref: firestore.DocumentReference,
) -> None:
    """
    Transactionally updates proactive messaging settings in Firestore and schedules a task.

    Args:
        transaction (Transaction): Firestore transaction.
        celery_app (Celery): The Celery application instance.
        context (ProactiveMessagingContext): Context for proactive messaging.
        bot_ref (firestore.DocumentReference): Reference to the Firestore document for the bot.
    """
    proactive_config = context.app_config.proactive_messaging_settings
    bot_doc = bot_ref.get(transaction=transaction).to_dict()
    current_task_id = bot_doc.get("current_task_id", None)

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

def revoke_existing_tasks(celery_app: Celery, task_id: str) -> None:
    """
    Revokes the existing proactive messaging task in Celery.

    Args:
        celery_app (Celery): The Celery application instance.
        task_id (str): The ID of the task to be revoked.
    """
    if task_id:
        celery_app.control.revoke(task_id)


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
            transaction = firestore.Client().transaction()
            update_proactive_messaging_settings(transaction, celery_app, bot_ref, proactive_config, bot_id)
