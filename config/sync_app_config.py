from __future__ import annotations

import logging
from abc import abstractmethod
from enum import Enum

from celery import Celery
from google.api_core.exceptions import InvalidArgument
from google.cloud import firestore

from config.app_config import AppConfig


class EntityType(Enum):
    BOT = "Bots"
    COMPANION = "Companions"


class SyncAppConfig(AppConfig):
    """
    Manages application configurations, specifically loading settings synchronously from Firebase Firestore.
    This class is tailored for environments like Celery workers or Streamlit apps where synchronous operations are preferred.
    """

    @abstractmethod
    def initialize_firestore_client(self) -> firestore.Client:
        """
        Abstract method to initializes a default Firestore client.
        This method should be implemented in derived classes to load configurations
        from specific sources.
        Returns:
            firestore.Client: Initialized Firestore client.
        """

    def load_config_from_firebase(
        self,
        entity_id: str,
        entity_type: EntityType = EntityType.BOT,
        db: firestore.Client | None = None,
    ) -> None:
        """
        Load configuration from Firestore for a given entity (bot or companion).
        Defaults to loading bot configuration and uses a default Firestore client
        if not provided.

        Args:
            entity_id (str): Unique identifier for the entity.
            entity_type (EntityType): Type of the entity (BOT or COMPANION). Defaults to BOT.
            db (firestore.Client | None): Firestore client for database operations.
                                          If None, a default client is initialized.

        Raises:
            FileNotFoundError: If the entity document does not exist in Firestore.
        """
        if db is None:
            db = self.initialize_firestore_client()

        collection_name = "Bots" if entity_type == EntityType.BOT else "Companions"
        entity_ref = db.collection(collection_name).document(entity_id)
        logging.info("Attempting to fetch Firestore document: %s", entity_ref.path)
        entity = entity_ref.get()

        if not entity.exists:
            raise FileNotFoundError(
                f"{entity_type.value.capitalize()} with ID {entity_id} does not exist in Firestore."
            )

        if entity_type == EntityType.BOT:
            self._apply_proactive_messaging_settings_from_bot(entity)
            self._apply_slack_tokens_from_bot(entity)

            self._validate_and_apply_tokens()

            companion_id = entity.get("CompanionId")
            companion_ref = db.collection("Companions").document(companion_id)
            companion = companion_ref.get()
            if not companion.exists:
                raise FileNotFoundError(
                    f"Companion with ID {companion_id} does not exist in Firestore."
                )

            self._apply_settings_from_companion(companion)

        elif entity_type == EntityType.COMPANION:
            self._apply_settings_from_companion(entity)

        logging.info(
            "Configuration loaded from Firestore for %s %s",
            entity_type.value,
            entity_id,
        )

    def initialize_celery_app(self, name: str) -> Celery:
        """Initializes Celery app with loaded configuration."""
        # Use the broker URL from settings or the default one
        broker_url = self.celery_settings.broker_url
        celery_app = Celery(name, broker=broker_url)
        logging.info("Celery app initialized with broker URL: %s", broker_url)
        return celery_app
