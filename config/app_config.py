from __future__ import annotations

import json
from abc import ABC, abstractmethod
from configparser import ConfigParser
from typing import Any

from google.cloud import firestore
from langchain.chat_models import ChatOpenAI

MAX_TOKENS = 1023


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


class AppConfig(ABC):
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

    def _validate_config(self) -> None:
        """Validate that required configuration variables are present."""
        required_settings = ["openai_api_key"]
        for setting in required_settings:
            assert setting in self.config["api"], f"Missing configuration for {setting}"

        required_firebase_settings = ["enabled"]
        for setting in required_firebase_settings:
            assert (
                setting in self.config["firebase"]
            ), f"Missing configuration for {setting}"

    def _apply_settings_from_companion(
        self, companion: firestore.DocumentSnapshot
    ) -> None:
        """
        Applies settings from the given companion Firestore document to the provided app configuration.

        Args:
            app_config (AppConfig): The application configuration object.
            companion (firestore.DocumentSnapshot): Firestore document snapshot containing companion settings.
        """
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

    @abstractmethod
    def load_config(self):
        """
        Abstract method to load configuration.

        This method should be implemented in derived classes to load configurations
        from specific sources.
        """

    def get_readable_config(self) -> str:
        """
        Retrieves a human-readable string of the current non-sensitive configuration.

        Returns:
            str: A string representing the current configuration excluding sensitive details.
        """
        readable_config = (
            f"Chat Model: {self.config.get('settings', 'chat_model')}\n"
            f"System Prompt: {self.config.get('settings', 'system_prompt')}\n"
            f"Temperature: {self.config.get('settings', 'temperature')}"
        )
        return readable_config


def init_chat_model(app_config: AppConfig) -> ChatOpenAI:
    """
    Initialize the langchain chat model.

    Args:
        app_config (AppConfig): Application configuration object.

    Returns:
        ChatOpenAI: Initialized chat model.
    """
    config = app_config.config
    chat = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=float(config.get("settings", "temperature")),
        openai_api_key=config.get("api", "openai_api_key"),
        openai_organization=config.get("api", "openai_organization", fallback=None),
        max_tokens=MAX_TOKENS,
    )  # type: ignore
    return chat
