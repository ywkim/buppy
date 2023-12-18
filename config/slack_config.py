from __future__ import annotations

import logging
import os
from typing import Any

from google.cloud import firestore

from config.app_config import AppConfig, safely_get_field
from config.loaders.env_loader import load_env_value
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
            config_file, "api", APISettings
        )
        self.core_settings = load_settings_from_ini_section(
            config_file, "settings", CoreSettings
        )
        self.firebase_settings = load_settings_from_ini_section(
            config_file, "firebase", FirebaseSettings
        )
        self.proactive_messaging_settings = load_settings_from_ini_section(
            config_file, "proactive_messaging", ProactiveMessagingSettings
        )
        self.langsmith_settings = load_settings_from_ini_section(
            config_file, "langsmith", LangSmithSettings
        )
        logging.info("Configuration loaded from file %s", config_file)

    def load_config_from_env_vars(self) -> None:
        """
        Load configuration from environment variables.

        This method loads the Firebase and API related settings from the
        environment variables. It validates the configurations based on the
        enabled/disabled status of certain features.
        """
        # Load Firebase settings
        self.firebase_settings.enabled = load_env_value(
            "FIREBASE_ENABLED", self.firebase_settings.enabled, bool
        )

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

    def _apply_proactive_messaging_settings_from_bot(
        self, bot_document: firestore.DocumentSnapshot
    ) -> None:
        """
        Applies proactive messaging settings from the provided bot document snapshot.

        This method extracts the proactive messaging settings from the Firestore
        document snapshot of the bot and applies them to the current configuration.
        It ensures that the proactive messaging feature and its related settings
        (interval days, system prompt, and Slack channel) are configured according
        to the bot's settings in Firestore.

        Args:
            bot_document (firestore.DocumentSnapshot): A snapshot of the Firestore
                                                      document for the bot.
        """
        if safely_get_field(
            bot_document,
            "proactive_messaging.enabled",
            default=self.proactive_messaging_settings.enabled,
        ):
            proactive_messaging_settings: dict[str, Any] = {
                "enabled": True,
                "interval_days": bot_document.get("proactive_messaging.interval_days"),
                "system_prompt": bot_document.get("proactive_messaging.system_prompt"),
                "slack_channel": bot_document.get("proactive_messaging.slack_channel"),
                "temperature": safely_get_field(
                    bot_document,
                    "proactive_messaging.temperature",
                    default=self.proactive_messaging_settings.temperature,
                ),
            }
            self.proactive_messaging_settings = ProactiveMessagingSettings(
                **proactive_messaging_settings
            )

    def _apply_slack_tokens_from_bot(
        self, bot_document: firestore.DocumentSnapshot
    ) -> None:
        """
        Applies the Slack bot and app tokens from the provided bot document snapshot.

        Args:
            bot_document (firestore.DocumentSnapshot): A snapshot of the Firestore document for the bot.
        """
        slack_bot_token = bot_document.get("slack_bot_token")
        slack_app_token = bot_document.get("slack_app_token")

        # Update API settings with fetched tokens
        self.api_settings.slack_bot_token = slack_bot_token
        self.api_settings.slack_app_token = slack_app_token

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

        # Ensure that the tokens are not None before assignment
        if self.api_settings.slack_bot_token is not None:
            self.bot_token = self.api_settings.slack_bot_token
        else:
            raise ValueError("Slack bot token is missing in API settings.")

        if self.api_settings.slack_app_token is not None:
            self.app_token = self.api_settings.slack_app_token
        else:
            raise ValueError("Slack app token is missing in API settings.")

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
            self.load_config_from_env_vars()

        self._validate_config()
