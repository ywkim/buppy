from __future__ import annotations

import os
import json

from flask import Flask, request
from cloudevents.http import from_http
from google.cloud import firestore

from celery import Celery
from firestore_managers.proactive_messaging_manager import update_proactive_messaging_settings
from celery_tasks.proactive_messaging_task import schedule_proactive_message
from utils.proactive_messaging_utils import should_reschedule

app = Flask(__name__)
celery_app = Celery("proactive_scheduler", broker=os.environ["CELERY_BROKER_URL"])
db = firestore.Client()

@app.route("/", methods=["POST"])
def handle_proactive_event():
    """
    Handles proactive messaging events triggered by Firestore document changes.
    """
    event_data = from_http(request.headers, request.get_data(), json.loads).data
    process_proactive_event(event_data)

    return "OK", 200

def process_proactive_event(event_data: dict) -> None:
    """
    Processes proactive messaging events after parsing the data from the event.

    Args:
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

if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
