from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

from celery import Celery
from cloudevents.http import CloudEvent
from google.cloud import firestore
from google.cloud.firestore import Transaction
from google.events.cloud.firestore import Document, DocumentEventData
from slack_sdk.web.async_client import AsyncWebClient

from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from config.slack_config import SlackAppConfig
from utils.proactive_messaging_utils import (
    ProactiveMessagingContext,
    calculate_next_schedule_time,
    generate_and_send_proactive_message,
    should_reschedule,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def execute_proactive_messaging_update(
    transaction: Transaction,
    bot_ref: firestore.DocumentReference,
    proactive_config: ProactiveMessagingSettings,
    celery_app: Celery,
    context: ProactiveMessagingContext,
) -> None:
    """
    Handles the logic for updating proactive messaging settings and scheduling tasks.

    Args:
        transaction (Transaction): Firestore transaction.
        bot_ref (DocumentReference): Reference to the Firestore document for the bot.
        proactive_config (ProactiveMessagingSettings): Proactive messaging configuration.
        celery_app (Celery): Celery application instance for task scheduling.
        context (ProactiveMessagingContext): Context for proactive messaging.
    """
    bot_doc = next(transaction.get(bot_ref)).to_dict()
    current_task_id = bot_doc.get("current_task_id", None)

    next_schedule_time = calculate_next_schedule_time(proactive_config)
    task_function = create_proactive_message_task(celery_app, None)
    task = task_function.apply_async(args=[context], eta=next_schedule_time)
    try:
        transaction.update(
            bot_ref,
            {
                "proactive_messaging.current_task_id": task.id,
            },
        )
        logging.info(
            "Proactive messaging updated for bot %s. Task ID: %s", bot_ref.id, task.id
        )
    except Exception as e:
        celery_app.control.revoke(task.id)
        raise e
    finally:
        revoke_existing_tasks(celery_app, current_task_id)


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
    next_schedule_time = calculate_next_schedule_time(context.app_config)
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
    execute_proactive_messaging_update(
        transaction,
        bot_ref,
        context.app_config.proactive_messaging_settings,
        celery_app,
        context,
    )


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
    db: firestore.Client, celery_app: Celery, cloud_event: CloudEvent
) -> None:
    """
    Processes a proactive messaging event triggered by Firestore document changes.

    Args:
        db (firestore.Client): Firestore client for database operations.
        celery_app (CeleryApp): Celery application instance for task scheduling.
        cloud_event (CloudEvent): The CloudEvent data representing the Firestore event.

    This function processes Firestore document changes, checks proactive messaging
    configurations, and schedules tasks accordingly using Celery.
    """
    firestore_payload = DocumentEventData()
    firestore_payload._pb.ParseFromString(cloud_event.data)

    bot_id = extract_bot_id(firestore_payload.value.name)
    bot_ref = db.collection("Bots").document(bot_id)
    bot_doc = bot_ref.get()

    if not bot_doc.exists:
        logging.error("Bot document with ID %s does not exist.", bot_id)
        return

    proactive_config_current = extract_proactive_config(firestore_payload.value)
    proactive_config_old = extract_proactive_config(firestore_payload.old_value)

    if proactive_config_current is None or proactive_config_old is None:
        logging.warning("Proactive messaging settings not found in CloudEvent payload.")
        return

    if should_reschedule(proactive_config_old, proactive_config_current):
        transaction = db.transaction()
        app_config = SlackAppConfig()
        app_config.load_config_from_firebase_sync(db, bot_id)
        client = AsyncWebClient(token=app_config.bot_token)
        context = ProactiveMessagingContext(client, app_config, bot_id)
        update_proactive_messaging_settings(transaction, celery_app, context, bot_ref)
    logging.info("Proactive event processed for bot %s", bot_id)


def extract_bot_id(document_path: str) -> str:
    """
    Extracts the bot ID from the Firestore document path.

    Args:
        document_path (str): The Firestore document path.

    Returns:
        str: The extracted bot ID.
    """
    path_parts = document_path.split("/")
    return path_parts[path_parts.index("Bots") + 1]


def extract_proactive_config(document: Document) -> ProactiveMessagingSettings | None:
    """
    Extracts the proactive messaging configuration from Firestore fields and returns
    a ProactiveMessagingSettings object.

    Args:
        document (Document): Firestore document.

    Returns:
        ProactiveMessagingSettings | None: The extracted proactive messaging configuration object,
        or None if not found.
    """
    fields = document.fields
    if "proactive_messaging" in fields:
        config_data = dict(fields["proactive_messaging"].map_value.fields)
        return ProactiveMessagingSettings(**config_data)
    return None
