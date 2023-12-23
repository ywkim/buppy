from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from celery import Celery
from google.cloud import firestore

from utils.proactive_messaging_utils import (
    ProactiveMessagingContext,
    calculate_next_schedule_time,
    generate_and_send_proactive_message,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def create_proactive_message_task(celery_app: Celery, db: firestore.Client) -> Any:
    """
    Registers a Celery task for sending proactive messages using the given Celery app.

    Args:
        celery_app (Celery): The Celery application instance to register the task with.
        db (firestore.Client): The Firestore client for database operations.

    Returns:
        The Celery task function.
    """

    @celery_app.task(name="schedule_proactive_message")
    def schedule_proactive_message(context: ProactiveMessagingContext) -> None:
        """
        Sends a proactive message and schedules the next message. This function
        is registered as a Celery task to handle the asynchronous operation.

        Args:
            context (ProactiveMessagingContext): Context containing Slack client,
            app configuration, and bot user ID.
        """
        asyncio.run(generate_and_send_proactive_message(context))

        # Schedule the next proactive message
        schedule_proactive_message_task(context, celery_app, db)

    return schedule_proactive_message

def schedule_proactive_message_task(
    context: ProactiveMessagingContext,
    celery_app: Celery,
    db: firestore.Client
) -> None:
    """
    Schedules a proactive messaging task and updates the task ID in Firestore.

    Args:
        context (ProactiveMessagingContext): The context containing Slack client and app configuration.
        celery_app (Celery): The Celery application instance.
        db (firestore.Client): Firestore client for database operations.
    """
    next_schedule_time = calculate_next_schedule_time(context.app_config.proactive_messaging_settings)
    task_function = create_proactive_message_task(celery_app, db)
    task = task_function.apply_async(args=[context], eta=next_schedule_time)

    # Update the task ID in Firestore
    update_task_in_firestore(db, context.bot_user_id, task.id, next_schedule_time)

    logging.info("Proactive message scheduled for %s with task ID %s", next_schedule_time, task.id)

def update_task_in_firestore(
    db: firestore.Client,
    bot_user_id: str,
    task_id: str | None,
    eta: datetime | None = None
) -> None:
    """
    Updates the task ID and eta in Firestore for the given bot.

    Args:
        db (firestore.Client): Firestore client for database operations.
        bot_user_id (str): The bot user ID.
        task_id (str | None): The task ID to be updated, None if the task is cancelled.
        eta (datetime | None): The estimated time of arrival for the task.
    """
    bot_ref = db.collection("Bots").document(bot_user_id)
    update_data = {}
    if task_id is not None:
        update_data["proactive_messaging.current_task_id"] = task_id
        if eta:
            update_data["proactive_messaging.last_scheduled"] = eta.isoformat()
    else:
        # Remove the fields if the task is cancelled
        update_data["proactive_messaging.current_task_id"] = firestore.DELETE_FIELD
        update_data["proactive_messaging.last_scheduled"] = firestore.DELETE_FIELD

    bot_ref.update(update_data)

    logging.info("Firestore updated for bot %s: task_id=%s, eta=%s", bot_user_id, task_id, eta)

def get_current_task_id(db: firestore.Client, bot_user_id: str) -> str | None:
    """
    Retrieves the current task ID from Firestore for the given bot.

    Args:
        db (firestore.Client): Firestore client for database operations.
        bot_user_id (str): The bot user ID.

    Returns:
        str | None: The current task ID if it exists, otherwise None.
    """
    bot_ref = db.collection("Bots").document(bot_user_id)
    bot_doc = bot_ref.get()
    if bot_doc.exists:
        return bot_doc.to_dict().get("proactive_messaging", {}).get("current_task_id")
    return None

def cancel_current_proactive_message_task(
    context: ProactiveMessagingContext,
    celery_app: Celery,
    db: firestore.Client,
) -> None:
    """
    Cancels the current proactive messaging task and updates Firestore.

    Args:
        context (ProactiveMessagingContext): Context for proactive messaging.
        celery_app (Celery): The Celery application instance.
        db (firestore.Client): Firestore client for database operations.
    """
    current_task_id = get_current_task_id(db, context.bot_user_id)
    if current_task_id:
        celery_app.control.revoke(current_task_id)
        update_task_in_firestore(db, context.bot_user_id, None, None)
        logging.info("Current proactive message task cancelled: %s", current_task_id)
