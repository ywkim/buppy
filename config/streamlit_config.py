from __future__ import annotations

import logging
from enum import Enum

import streamlit as st
from celery import Celery
from google.cloud import firestore
from google.oauth2 import service_account

from config.app_config import AppConfig
from config.loaders.streamlit_loader import load_settings_from_streamlit_secrets
from config.settings.api_settings import APISettings
from config.settings.celery_settings import CelerySettings
from config.settings.core_settings import CoreSettings
from config.settings.firebase_settings import FirebaseSettings
from config.settings.langsmith_settings import LangSmithSettings
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings


class EntityType(Enum):
    BOT = "bot"
    COMPANION = "companion"


class StreamlitAppConfig(AppConfig):
    """Manages application configuration for the Streamlit web chatbot."""

    def _load_config_from_streamlit_secrets(self):
        """Loads configuration from Streamlit secrets."""
        self.api_settings = load_settings_from_streamlit_secrets(APISettings, "api")
        self.core_settings = load_settings_from_streamlit_secrets(
            CoreSettings, "settings"
        )
        self.firebase_settings = load_settings_from_streamlit_secrets(
            FirebaseSettings, "firebase"
        )
        self.langsmith_settings = load_settings_from_streamlit_secrets(
            LangSmithSettings, "langsmith"
        )
        self.proactive_messaging_settings = load_settings_from_streamlit_secrets(
            ProactiveMessagingSettings, "proactive_messaging"
        )
        self.celery_settings = load_settings_from_streamlit_secrets(
            CelerySettings, "celery"
        )
        logging.info("Configuration loaded from Streamlit secrets")

    def initialize_firestore_client(self) -> firestore.Client:
        """
        Initializes a default Firestore client using Streamlit secrets or default credentials.

        Returns:
            firestore.Client: Initialized Firestore client.
        """
        service_account_info = st.secrets.get("firebase_service_account")
        if not service_account_info:
            logging.info(
                "Firebase service account details not found in Streamlit secrets. "
                "Using default credentials."
            )
            return firestore.Client()

        # Create a service account credential object
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info
        )
        project_id = service_account_info["project_id"]

        # Initialize and return the Firestore client with the credentials
        return firestore.Client(credentials=credentials, project=project_id)

    def initialize_celery_app(self):
        """Initializes Celery app with loaded configuration."""
        if self.celery_settings.broker_url:
            return Celery(
                'streamlit_admin_app',
                broker=self.celery_settings.broker_url,
            )
        return None

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

    def load_config(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._load_config_from_streamlit_secrets()
        self._validate_config()
        self._apply_langsmith_settings()
