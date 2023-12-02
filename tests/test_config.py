import os
import unittest
from unittest.mock import patch

from main import SlackAppConfig


class TestConfig(unittest.TestCase):
    """
    Test class for configuration loading functions.

    ...

    Attributes
    ----------
    config_structure : dict
        structure of the configuration (i.e., sections and options)
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

    def test_load_config_from_env_vars(self) -> None:
        """Test load_config_from_env_vars() function to verify if it correctly reads the environment variables."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test",
                "SLACK_BOT_TOKEN": "test",
                "SLACK_APP_TOKEN": "test",
                "CHAT_MODEL": "gpt-4",
                "SYSTEM_PROMPT": "You are a helpful assistant.",
                "TEMPERATURE": "0",
            },
        ):
            app_config = SlackAppConfig()
            app_config.load_config_from_env_vars()


if __name__ == "__main__":
    unittest.main()
