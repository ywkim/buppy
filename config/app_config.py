from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Any

from google.cloud import firestore
from langchain.chat_models import ChatOpenAI

from config.settings.api_settings import APISettings
from config.settings.core_settings import CoreSettings
from config.settings.firebase_settings import FirebaseSettings
from config.settings.langsmith_settings import LangSmithSettings
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings

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
    Application configuration manager.

    Manages configuration settings for the application using Pydantic models
    and loaders to obtain settings from various sources such as environment
    variables, Firestore, and INI files.
    """

    def __init__(self):
        """Initialize AppConfig with default settings."""
        self.api_settings = APISettings()
        self.core_settings = CoreSettings()
        self.firebase_settings = FirebaseSettings()
        self.langsmith_settings = LangSmithSettings()
        self.proactive_messaging_settings = ProactiveMessagingSettings()

    @property
    def vision_enabled(self) -> bool:
        return self.core_settings.vision_enabled

    @property
    def firebase_enabled(self) -> bool:
        return self.firebase_settings.enabled

    @property
    def langsmith_enabled(self) -> bool:
        """Determines if LangSmith feature is enabled."""
        return self.langsmith_settings.enabled

    @property
    def langsmith_api_key(self) -> str:
        """Retrieves the LangSmith API key."""
        api_key = self.langsmith_settings.api_key
        if api_key is None:
            raise ValueError("LangSmith API key is not set")
        return api_key

    @property
    def proactive_messaging_enabled(self) -> bool:
        return self.proactive_messaging_settings.enabled

    @property
    def proactive_message_interval_days(self) -> float:
        interval_days = self.proactive_messaging_settings.interval_days
        if interval_days is None:
            raise ValueError("Proactive messaging interval days is not set")
        return interval_days

    @property
    def proactive_system_prompt(self) -> str:
        system_prompt = self.proactive_messaging_settings.system_prompt
        if system_prompt is None:
            raise ValueError("Proactive system prompt is not set")
        return system_prompt

    @property
    def proactive_slack_channel(self) -> str:
        slack_channel = self.proactive_messaging_settings.slack_channel
        if slack_channel is None:
            raise ValueError("Proactive Slack channel is not set")
        return slack_channel

    @property
    def proactive_message_temperature(self) -> float:
        return self.proactive_messaging_settings.temperature

    def _validate_config(self) -> None:
        """Validate that required configuration variables are present."""
        assert (
            self.api_settings.openai_api_key
        ), "Missing configuration for openai_api_key"

        if self.langsmith_enabled:
            assert self.langsmith_api_key, "Missing configuration for LangSmith API key"

    def _apply_settings_from_companion(
        self, companion: firestore.DocumentSnapshot
    ) -> None:
        """
        Applies settings from the given companion Firestore document to the core settings
        of the application.

        Args:
            companion (firestore.DocumentSnapshot): Firestore document snapshot
                                                   containing companion settings.
        """
        settings_data = companion.to_dict() or {}

        # Special handling for 'prefix_messages_content' field
        if "prefix_messages_content" in settings_data:
            settings_data["prefix_messages_content"] = json.dumps(
                settings_data["prefix_messages_content"]
            )

        self.core_settings = CoreSettings(**settings_data)

    def _apply_langsmith_settings(self):
        """
        Applies LangSmith settings if enabled.
        Sets LangSmith API key as an environment variable.
        """
        if self.langsmith_enabled:
            os.environ["LANGCHAIN_API_KEY"] = self.langsmith_api_key
            os.environ["LANGCHAIN_TRACING_V2"] = "true"

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
        return (
            f"Chat Model: {self.core_settings.chat_model}\n"
            f"System Prompt: {self.core_settings.system_prompt}\n"
            f"Temperature: {self.core_settings.temperature}\n"
            f"Vision Enabled: {'Yes' if self.vision_enabled else 'No'}"
        )


def init_chat_model(app_config: AppConfig) -> ChatOpenAI:
    """
    Initialize the langchain chat model.

    Args:
        app_config (AppConfig): Application configuration object.

    Returns:
        ChatOpenAI: Initialized chat model.
    """
    chat = ChatOpenAI(
        model=app_config.core_settings.chat_model,
        temperature=app_config.core_settings.temperature,
        openai_api_key=app_config.api_settings.openai_api_key,
        openai_organization=app_config.api_settings.openai_organization,
        max_tokens=MAX_TOKENS,
    )  # type: ignore
    return chat


def init_proactive_chat_model(app_config: AppConfig) -> ChatOpenAI:
    """
    Initializes a chat model specifically for proactive messaging.

    This function creates a chat model instance using settings configured for
    proactive messaging, including the temperature setting which influences the
    creativity of the generated messages.

    Args:
        app_config (AppConfig): The configuration object containing settings
                                     for proactive messaging.

    Returns:
        ChatOpenAI: An initialized chat model for proactive messaging.
    """
    proactive_temp = app_config.proactive_messaging_settings.temperature
    chat = ChatOpenAI(
        model=app_config.core_settings.chat_model,
        temperature=proactive_temp,
        openai_api_key=app_config.api_settings.openai_api_key,
        openai_organization=app_config.api_settings.openai_organization,
        max_tokens=MAX_TOKENS,
    )  # type: ignore
    return chat
