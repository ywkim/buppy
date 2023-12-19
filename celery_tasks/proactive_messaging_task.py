from __future__ import annotations

from celery import Celery
from google.cloud import firestore
from google.cloud.firestore import Transaction

from utils.proactive_messaging_utils import ProactiveMessagingContext, calculate_next_schedule_time

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

@firestore.transactional
def update_proactive_messaging_settings(
    transaction: Transaction,
    celery_app: Celery,
    bot_ref: firestore.DocumentReference,
    proactive_config: dict,
    bot_id: str
) -> None:
    """
    Transactionally updates proactive messaging settings in Firestore and schedules a task.

    Args:
        transaction (Transaction): Firestore transaction.
        celery_app (Celery): The Celery application instance.
        bot_ref (firestore.DocumentReference): Reference to the Firestore document for the bot.
        proactive_config (dict): Configuration details for proactive messaging.
        bot_id (str): Unique identifier for the bot.
    """
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

def revoke_existing_tasks(celery_app: Celery, task_id: str) -> None:
    """
    Revokes the existing proactive messaging task in Celery.

    Args:
        celery_app (Celery): The Celery application instance.
        task_id (str): The ID of the task to be revoked.
    """
    if task_id:
        celery_app.control.revoke(task_id)
