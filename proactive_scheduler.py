from __future__ import annotations

import os

from celery import Celery
from cloudevents.http import from_http
from flask import Flask, request
from google.cloud import firestore
from google.cloud.firestore import Transaction

from utils.proactive_messaging_utils import (
    ProactiveMessagingContext,
    calculate_next_schedule_time,
    generate_and_send_proactive_message,
    should_reschedule,
)

app = Flask(__name__)
celery_app = Celery("proactive_scheduler", broker=os.environ["CELERY_BROKER_URL"])

db = firestore.Client()


@firestore.transactional
def update_proactive_messaging_settings(
    transaction: Transaction, bot_ref: firestore.DocumentReference
):
    bot_doc = bot_ref.get(transaction=transaction).to_dict()
    current_task_id = bot_doc.get("current_task_id", None)

    context = ProactiveMessagingContext(app, proactive_config, bot_id)
    next_schedule_time = calculate_next_schedule_time(proactive_config)
    task = celery_app.send_task(
        generate_and_send_proactive_message.name, args=[context], eta=next_schedule_time
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
        revoke_existing_tasks(current_task_id)


@app.route("/", methods=["POST"])
def handle_proactive_event():
    """
    Handles proactive messaging events triggered by Firestore document changes.
    """
    event = from_http(request.headers, request.get_data(), json.loads)
    data = event.data
    bot_id = data["id"]

    bot_ref = db.collection("Bots").document(bot_id)

    if "proactive_messaging" in bot_doc:
        proactive_config = bot_doc["proactive_messaging"]

        # 변경 여부 확인
        if should_reschedule(
            data["oldValue"]["fields"]["proactive_messaging"], proactive_config
        ):
            transaction = db.transaction()
            update_proactive_messaging_settings(transaction, bot_ref)

    return "OK", 200


def update_task_id_in_firestore(bot_id: str, task_id: str):
    """
    Updates the current task ID in Firestore for the given bot.

    Args:
        bot_id (str): The bot ID for which to update the task ID.
        task_id (str): The new task ID to be stored.
    """
    bot_ref = db.collection("Bots").document(bot_id)
    bot_ref.update({"proactive_messaging.current_task_id": task_id})


def revoke_existing_tasks(task_id: str):
    """
    Revokes the existing proactive messaging task.

    Args:
        task_id (str): The ID of the task to be revoked.
    """
    if task_id:
        celery_app.control.revoke(task_id)


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
