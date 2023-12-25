from __future__ import annotations

from google.cloud import firestore
from slack_sdk import WebClient

from config.sync_app_config import SyncAppConfig


class CeleryWorkerConfig(SyncAppConfig):
    """
    Application configuration manager for Celery worker.
    """

    def initialize_firestore_client(self) -> firestore.Client:
        """
        Initializes a default Firestore client using Streamlit secrets or default credentials.

        Returns:
            firestore.Client: Initialized Firestore client.
        """
        return firestore.Client()

    def initialize_slack_client(self) -> WebClient:
        client = WebClient(token=self.bot_token)
        return client

    def load_config(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._validate_config()
        self._apply_langsmith_settings()
