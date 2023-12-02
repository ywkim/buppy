from __future__ import annotations

import json
import logging
import os
from configparser import ConfigParser
from typing import Any

from google.cloud import firestore


def safely_get_field(
    document: firestore.DocumentSnapshot,
    field_path: str,
    default: (Any | None) = None,
) -> Any:
    """
    Safely retrieves a value from the document snapshot of Firestore using a
    field path. Returns a default value if the field path
    does not exist within the document.

    Args:
        document (DocumentSnapshot): The snapshot of the Firestore document.
        field_path (str): A dot-delimited path to a field in the Firestore document.
        default (Optional[Any]): The default value to return if the field doesn't exist.

    Returns:
        Any: The value retrieved from the document for the field path, if it exists;
             otherwise, the default value.
    """
    try:
        value = document.get(field_path)
        if value is None:
            return default
        return value
    except KeyError:
        return default


class AppConfig:
    """
    Manages the application configuration settings.

    This class is responsible for loading configuration settings from various sources
    including environment variables, files, and Firebase Firestore.

    Attributes:
        config (ConfigParser): A ConfigParser object holding the configuration.
    """

    DEFAULT_CONFIG = {
        "settings": {
            "chat_model": "gpt-4",
            "system_prompt": "You are a helpful assistant.",
            "temperature": "0",
            "vision_enabled": "false",
        },
        "firebase": {"enabled": "false"},
    }

    def __init__(self):
        """Initialize AppConfig with default settings."""
        self.config: ConfigParser = ConfigParser()
        self.config.read_dict(self.DEFAULT_CONFIG)

    @property
    def vision_enabled(self) -> bool:
        """Determines if vision (image analysis) feature is enabled."""
        return self.config.getboolean("settings", "vision_enabled", fallback=False)

    def load_config_from_file(self, config_file: str) -> None:
        """Load configuration from a given file path."""
        self.config.read(config_file)
        logging.info("Configuration loaded from file %s", config_file)

    def load_config_from_env_vars(self) -> None:
        """Load configuration from environment variables."""
        env_config: dict[str, dict[str, Any]] = {
            "api": {
                "openai_api_key": os.environ.get("OPENAI_API_KEY"),
                "slack_bot_token": os.environ.get("SLACK_BOT_TOKEN"),
                "slack_app_token": os.environ.get("SLACK_APP_TOKEN"),
            },
            "settings": {
                "chat_model": os.environ.get(
                    "CHAT_MODEL", self.DEFAULT_CONFIG["settings"]["chat_model"]
                ),
                "system_prompt": os.environ.get(
                    "SYSTEM_PROMPT", self.DEFAULT_CONFIG["settings"]["system_prompt"]
                ),
                "temperature": os.environ.get(
                    "TEMPERATURE", self.DEFAULT_CONFIG["settings"]["temperature"]
                ),
                "vision_enabled": os.environ.get(
                    "VISION_ENABLED", self.DEFAULT_CONFIG["settings"]["vision_enabled"]
                ).lower()
                in {"true", "1", "yes"},
            },
            "firebase": {
                "enabled": os.environ.get(
                    "FIREBASE_ENABLED", self.DEFAULT_CONFIG["firebase"]["enabled"]
                ).lower()
                in {"true", "1", "yes"}
            },
        }

        openai_org = os.environ.get("OPENAI_ORGANIZATION", None)
        if openai_org is not None:
            env_config["api"]["openai_organization"] = openai_org

        self.config.read_dict(env_config)
        logging.info("Configuration loaded from environment variables")

    def _validate_config(self) -> None:
        """Validate that required configuration variables are present."""
        required_settings = ["openai_api_key", "slack_bot_token", "slack_app_token"]
        for setting in required_settings:
            assert setting in self.config["api"], f"Missing configuration for {setting}"

        self.bot_token = self.config.get("api", "slack_bot_token")
        self.app_token = self.config.get("api", "slack_app_token")

        required_firebase_settings = ["enabled"]
        for setting in required_firebase_settings:
            assert (
                setting in self.config["firebase"]
            ), f"Missing configuration for {setting}"

    async def load_config_from_firebase(self, bot_user_id: str) -> None:
        """
        Load configuration from Firebase Firestore. Uses default values from self.DEFAULT_CONFIG
        if certain configuration values are missing, except for 'prefix_messages_content',
        which defaults to None.

        Args:
            bot_user_id (str): The unique identifier for the bot.

        Raises:
            FileNotFoundError: If the bot or companion document does not exist in Firebase.
        """
        db = firestore.AsyncClient()
        bot_ref = db.collection("Bots").document(bot_user_id)
        bot = await bot_ref.get()
        if not bot.exists:
            raise FileNotFoundError(
                f"Bot with ID {bot_user_id} does not exist in Firebase."
            )
        companion_id = bot.get("CompanionId")
        companion_ref = db.collection("Companions").document(companion_id)
        companion = await companion_ref.get()
        if not companion.exists:
            raise FileNotFoundError(
                f"Companion with ID {companion_id} does not exist in Firebase."
            )

        # Retrieve settings and use defaults if necessary
        settings = {
            "chat_model": (
                safely_get_field(
                    companion,
                    "chat_model",
                    self.DEFAULT_CONFIG["settings"]["chat_model"],
                )
            ),
            "system_prompt": (
                safely_get_field(
                    companion,
                    "system_prompt",
                    self.DEFAULT_CONFIG["settings"]["system_prompt"],
                )
            ),
            "temperature": (
                safely_get_field(
                    companion,
                    "temperature",
                    self.DEFAULT_CONFIG["settings"]["temperature"],
                )
            ),
            "vision_enabled": (
                safely_get_field(
                    companion,
                    "vision_enabled",
                    self.DEFAULT_CONFIG["settings"]["vision_enabled"],
                )
            ),
        }

        # Add 'prefix_messages_content' only if it exists
        prefix_messages_content = safely_get_field(companion, "prefix_messages_content")
        if prefix_messages_content is not None:
            settings["prefix_messages_content"] = json.dumps(prefix_messages_content)

        # Apply the new configuration settings
        self.config.read_dict({"settings": settings})

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

    def get_readable_config(self) -> str:
        """
        Retrieves a human-readable string of the current non-sensitive configuration.

        Returns:
            str: A string representing the current configuration excluding sensitive details.
        """
        readable_config = (
            f"Chat Model: {self.config.get('settings', 'chat_model')}\n"
            f"System Prompt: {self.config.get('settings', 'system_prompt')}\n"
            f"Temperature: {self.config.get('settings', 'temperature')}\n"
            f"Vision Enabled: {'Yes' if self.vision_enabled else 'No'}"
        )
        return readable_config
