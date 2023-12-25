from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from celery import Celery
from google.cloud import firestore

from config.celery_config import CeleryWorkerConfig
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from utils.logging_utils import create_log_message
from utils.proactive_messaging_utils import (
    calculate_next_schedule_time,
    generate_and_send_proactive_message_sync,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def create_proactive_message_task(celery_app: Celery) -> Any:
    """
    Registers a Celery task for sending proactive messages using the given Celery app.

    Returns:
        The Celery task function.
    """

    @celery_app.task(name="schedule_proactive_message")
    def schedule_proactive_message(bot_user_id: str) -> None:
        """
        Sends a proactive message and schedules the next message. This function
        is registered as a Celery task to handle the asynchronous operation.

        Args:
            bot_user_id (str): The user ID of the bot.
        """
        app_config = CeleryWorkerConfig()
        app_config.load_config()
        celery_app = app_config.initialize_celery_app("proactive_messaging_task")
        db = app_config.initialize_firestore_client()
        app_config.load_config_from_firebase(bot_user_id, db=db)
        client = app_config.initialize_slack_client(bot_user_id)
        logging.info("Configuration updated from Firebase Firestore.")

        generate_and_send_proactive_message_sync(client, app_config)

        channel = app_config.proactive_slack_channel
        logging.info(
            create_log_message(
                "Proactive message sent to channel",
                channel=channel,
            )
        )

        # Schedule the next proactive message
        schedule_proactive_message_task(
            app_config.proactive_messaging_settings, bot_user_id, celery_app, db
        )

    return schedule_proactive_message


def schedule_proactive_message_task(
    settings: ProactiveMessagingSettings,
    bot_user_id: str,
    celery_app: Celery,
    db: firestore.Client,
) -> None:
    """
    Schedules a proactive messaging task and updates the task ID in Firestore.

    Args:
        settings (ProactiveMessagingSettings): Configuration settings for proactive messaging.
        bot_user_id (str): The user ID of the bot.
        celery_app (Celery): The Celery application instance.
        db (firestore.Client): Firestore client for database operations.
    """
    next_schedule_time = calculate_next_schedule_time(settings)
    task_function = create_proactive_message_task(celery_app)
    task = task_function.apply_async(args=[bot_user_id], eta=next_schedule_time)

    # Update the task ID in Firestore
    update_task_in_firestore(db, bot_user_id, task.id, next_schedule_time)

    logging.info(
        "Proactive message scheduled for %s with task ID %s",
        next_schedule_time,
        task.id,
    )


def update_task_in_firestore(
    db: firestore.Client,
    bot_user_id: str,
    task_id: str | None,
    eta: datetime | None = None,
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

    logging.info(
        "Firestore updated for bot %s: task_id=%s, eta=%s", bot_user_id, task_id, eta
    )


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
    bot_user_id: str,
    celery_app: Celery,
    db: firestore.Client,
) -> None:
    """
    Cancels the current proactive messaging task and updates Firestore.

    Args:
        bot_user_id (str): The user ID of the bot.
        celery_app (Celery): The Celery application instance.
        db (firestore.Client): Firestore client for database operations.
    """
    current_task_id = get_current_task_id(db, bot_user_id)
    if current_task_id:
        celery_app.control.revoke(current_task_id)
        update_task_in_firestore(db, bot_user_id, None, None)
        logging.info("Current proactive message task cancelled: %s", current_task_id)
