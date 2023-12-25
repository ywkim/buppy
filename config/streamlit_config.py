from __future__ import annotations

import logging
from enum import Enum

import streamlit as st
from celery import Celery
from google.cloud import firestore
from google.oauth2 import service_account

from config.loaders.streamlit_loader import load_settings_from_streamlit_secrets
from config.settings.api_settings import APISettings
from config.settings.celery_settings import CelerySettings
from config.settings.core_settings import CoreSettings
from config.settings.firebase_settings import FirebaseSettings
from config.settings.langsmith_settings import LangSmithSettings
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from config.sync_app_config import SyncAppConfig


class EntityType(Enum):
    BOT = "bot"
    COMPANION = "companion"


class StreamlitAppConfig(SyncAppConfig):
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

    def load_config(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._load_config_from_streamlit_secrets()
        self._validate_config()
        self._apply_langsmith_settings()
