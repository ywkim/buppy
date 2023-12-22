from __future__ import annotations

import json
import os

from celery import Celery
from cloudevents.http import from_http
from flask import Flask, request
from google.cloud import firestore

from event_handlers.proactive_event_handler import process_proactive_event

app = Flask(__name__)
celery_app = Celery("proactive_scheduler", broker=os.environ["CELERY_BROKER_URL"])
db = firestore.Client()


@app.route("/", methods=["POST"])
def handle_proactive_event():
    """
    Handles proactive messaging events triggered by Firestore document changes.
    """
    event_data = from_http(request.headers, request.get_data(), json.loads).data
    process_proactive_event(db, celery_app, event_data)

    return "OK", 200


if __name__ == "__main__":
    app.run(port=8080, host="0.0.0.0")
