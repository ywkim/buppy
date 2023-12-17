from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from config.settings.api_settings import APISettings
from config.settings.firebase_settings import FirebaseSettings
from config.slack_config import SlackAppConfig


class TestSlackAppConfig(unittest.TestCase):
    """
    Test class for SlackAppConfig configuration loading functions.

    Attributes:
        config_structure: dict structure of the configuration (i.e., sections and options).
    """

    def setUp(self) -> None:
        """Define test variables and set up the constants."""
        self.config_structure = {
            "api": {
                "openai_api_key",
                "slack_bot_token",
                "slack_app_token",
            },
            "settings": {
                "chat_model",
                "system_prompt",
                "temperature",
            },
        }
        self.app_config = SlackAppConfig()

    def test_load_config_from_env_vars(self) -> None:
        """Test load_config_from_env_vars() to verify correct reading of environment variables."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test",
                "SLACK_BOT_TOKEN": "test",
                "SLACK_APP_TOKEN": "test",
                "CHAT_MODEL": "gpt-4",
                "SYSTEM_PROMPT": "You are a helpful assistant.",
                "TEMPERATURE": "0",
                "FIREBASE_ENABLED": "False",
            },
        ):
            self.app_config.load_config_from_env_vars()

    def test_validation(self):
        """Test configuration validation logic."""
        self.app_config.api_settings = APISettings(
            slack_bot_user_id="test_id", openai_api_key="test_api_key"
        )
        self.app_config.firebase_settings = FirebaseSettings(enabled=True)
        self.app_config._validate_config()


if __name__ == "__main__":
    unittest.main()
