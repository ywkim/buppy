from __future__ import annotations

import asyncio
import logging
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
    task_function = create_proactive_message_task(celery_app)
    task = task_function.apply_async(args=[context], eta=next_schedule_time)
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


def create_proactive_message_task(celery_app: Celery) -> Any:
    """
    Registers a Celery task for sending proactive messages using the given Celery app.

    Args:
        celery_app (Celery): The Celery application instance to register the task with.

    Returns:
        The Celery task function.
    """

    @celery_app.task(name="schedule_proactive_message")
    def schedule_proactive_message(context: ProactiveMessagingContext) -> None:
        """
        Synchronous wrapper for the asynchronous 'generate_and_send_proactive_message' function.
        This function is registered as a Celery task to handle the asynchronous operation.

        Args:
            context (ProactiveMessagingContext): Context containing app, app_config, and bot_user_id.
        """
        asyncio.run(generate_and_send_proactive_message(context))

    return schedule_proactive_message


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


def update_task_id_in_firestore(
    db_client: firestore.Client, bot_id: str, task_id: str
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


def extract_proactive_config(document: Document) -> dict | None:
    """
    Extracts the proactive messaging configuration from Firestore fields.

    Args:
        document (Document): Firestore document.

    Returns:
        dict | None: The extracted proactive messaging configuration, or None if not found.
    """
    fields = document.fields
    if "proactive_messaging" in fields:
        return dict(fields["proactive_messaging"].map_value.fields)
    return None
