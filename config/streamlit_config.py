import logging

import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account

from config.app_config import AppConfig
from config.loaders.streamlit_loader import load_settings_from_streamlit_secrets
from config.settings.api_settings import APISettings
from config.settings.core_settings import CoreSettings
from config.settings.firebase_settings import FirebaseSettings
from config.settings.langsmith_settings import LangSmithSettings
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings


class StreamlitAppConfig(AppConfig):
    """Manages application configuration for the Streamlit web chatbot."""

    def _load_config_from_streamlit_secrets(self):
        """Loads configuration from Streamlit secrets."""
        self.api_settings = load_settings_from_streamlit_secrets("api", APISettings)
        self.core_settings = load_settings_from_streamlit_secrets(
            "settings", CoreSettings
        )
        self.firebase_settings = load_settings_from_streamlit_secrets(
            "firebase", FirebaseSettings
        )
        self.langsmith_settings = load_settings_from_streamlit_secrets(
            "langsmith", LangSmithSettings
        )
        self.proactive_messaging_settings = load_settings_from_streamlit_secrets(
            "proactive_messaging", ProactiveMessagingSettings
        )
        logging.info("Configuration loaded from Streamlit secrets")

    def _initialize_firebase_client(self) -> firestore.Client:
        """
        Initializes and returns a Firebase Firestore client using the service account details from Streamlit secrets.

        Returns:
            firestore.Client: The initialized Firestore client.

        Raises:
            ValueError: If the required service account details are not provided in Streamlit secrets.
        """
        service_account_info = st.secrets.get("firebase_service_account")
        if not service_account_info:
            logging.info(
                "Firebase service account details not found in Streamlit secrets. Using default credentials."
            )
            return firestore.Client()

        # Create a service account credential object
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info
        )

        project_id = service_account_info["project_id"]

        # Initialize and return the Firestore client with the credentials
        return firestore.Client(credentials=credentials, project=project_id)

    def load_config_from_firebase(self, companion_id: str) -> None:
        """
        Load configuration from Firebase Firestore using the provided companion ID.

        Args:
            companion_id (str): The unique identifier for the companion.

        Raises:
            FileNotFoundError: If the companion document does not exist in Firebase.
        """
        db = self._initialize_firebase_client()
        companion_ref = db.collection("Companions").document(companion_id)
        companion = companion_ref.get()
        if not companion.exists:
            raise FileNotFoundError(
                f"Companion with ID {companion_id} does not exist in Firebase."
            )

        self._apply_settings_from_companion(companion)

    def load_config(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._load_config_from_streamlit_secrets()
        self._validate_config()
        self._apply_langsmith_settings()
