from __future__ import annotations

import logging
import os

from google.cloud import firestore

from config.app_config import AppConfig
from config.loaders.ini_loader import load_settings_from_ini_section
from config.settings.api_settings import APISettings
from config.settings.core_settings import CoreSettings
from config.settings.firebase_settings import FirebaseSettings
from config.settings.langsmith_settings import LangSmithSettings
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings


class SlackAppConfig(AppConfig):
    """
    Manages Slack application configuration settings, loading them from various
    sources like environment variables, INI files, and Firebase Firestore.

    Attributes:
        api_settings (APISettings): API related settings.
        core_settings (CoreSettings): Core application settings.
        firebase_settings (FirebaseSettings): Firebase integration settings.
        proactive_messaging_settings (ProactiveMessagingSettings): Settings for proactive messaging.
        langsmith_settings (LangSmithSettings): LangSmith feature settings.
    """

    def load_config_from_file(self, config_file: str) -> None:
        """Load configuration from a given file path."""
        self.api_settings = load_settings_from_ini_section(
            APISettings, config_file, "api"
        )
        self.core_settings = load_settings_from_ini_section(
            CoreSettings, config_file, "settings"
        )
        self.firebase_settings = load_settings_from_ini_section(
            FirebaseSettings, config_file, "firebase"
        )
        self.proactive_messaging_settings = load_settings_from_ini_section(
            ProactiveMessagingSettings, config_file, "proactive_messaging"
        )
        self.langsmith_settings = load_settings_from_ini_section(
            LangSmithSettings, config_file, "langsmith"
        )
        logging.info("Configuration loaded from file %s", config_file)

    def _validate_config(self) -> None:
        """Validate that required configuration variables are present."""
        super()._validate_config()

        if self.firebase_settings.enabled:
            if not self.api_settings.slack_bot_user_id:
                raise ValueError("Missing configuration for slack_bot_user_id")
        else:
            if not self.api_settings.slack_bot_token:
                raise ValueError("Missing configuration for slack_bot_token")
            if not self.api_settings.slack_app_token:
                raise ValueError("Missing configuration for slack_app_token")
            self.bot_token = self.api_settings.slack_bot_token
            self.app_token = self.api_settings.slack_app_token

    async def load_config_from_firebase(self, bot_user_id: str) -> None:
        """
        Load configuration from Firebase Firestore. Uses default values from self.DEFAULT_CONFIG
        if certain configuration values are missing, except for 'prefix_messages_content',
        which defaults to None.

        Args:
            bot_user_id (str): The unique identifier for the bot.
        """
        db = firestore.AsyncClient()
        bot_ref = db.collection("Bots").document(bot_user_id)
        bot = await bot_ref.get()
        if not bot.exists:
            raise FileNotFoundError(
                f"Bot with ID {bot_user_id} does not exist in Firebase."
            )

        self._apply_proactive_messaging_settings_from_bot(bot)
        self._apply_slack_tokens_from_bot(bot)

        self._validate_and_apply_tokens()

        companion_id = bot.get("CompanionId")
        companion_ref = db.collection("Companions").document(companion_id)
        companion = await companion_ref.get()
        if not companion.exists:
            raise FileNotFoundError(
                f"Companion with ID {companion_id} does not exist in Firebase."
            )

        self._apply_settings_from_companion(companion)

        logging.info(
            "Configuration loaded from Firebase Firestore for bot %s", bot_user_id
        )

    def load_config(self, config_file: (str | None) = None) -> None:
        """Load configuration from a given file and fall back to environment variables if the file does not exist."""
        if config_file:
            if os.path.exists(config_file):
                self.load_config_from_file(config_file)
            else:
                raise FileNotFoundError(f"Config file {config_file} does not exist.")
        elif os.path.exists("config.ini"):
            self.load_config_from_file("config.ini")
        else:
            # If no config file provided, load config from environment variables
            pass

        self._validate_config()
