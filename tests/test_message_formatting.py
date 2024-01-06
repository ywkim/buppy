from __future__ import annotations

import unittest
from unittest.mock import AsyncMock

from langchain.schema import AIMessage, HumanMessage

from config.slack_config import SlackAppConfig
from main import format_messages


class TestMessageFormatting(unittest.IsolatedAsyncioTestCase):
    async def test_format_messages_with_user_identification_enabled(self) -> None:
        """Test format_messages function with user identification enabled."""
        app_config = SlackAppConfig()
        app_config.user_identification_settings.enabled = True

        thread_messages = [
            {
                "type": "message",
                "user": "U456DEF",
                "text": "Hello there!",
                "ts": "1629390000.000100",
            },
            {
                "type": "message",
                "user": "U123ABC",
                "text": "Hi!",
                "ts": "1629390000.000200",
            },
        ]

        async_client = AsyncMock()
        async_client.users_info = AsyncMock(
            return_value={
                "user": {
                    "id": "U123ABC",
                    "name": "testuser",
                    "profile": {"display_name": "displaytestuser"},
                }
            }
        )

        result = await format_messages(
            thread_messages, "U123ABC", app_config, async_client
        )

        self.assertIsInstance(result[0], HumanMessage)
        self.assertIsInstance(result[1], AIMessage)
        first_message_content = result[0].content[0]
        if isinstance(first_message_content, dict):
            self.assertIn("text", first_message_content)
            self.assertIn("testuser", first_message_content["text"])
        else:
            self.fail("First content item is not a dictionary.")

    async def test_format_messages_with_user_identification_disabled(self) -> None:
        """Test format_messages function with user identification disabled."""
        app_config = SlackAppConfig()
        app_config.user_identification_settings.enabled = False

        thread_messages = [
            {
                "type": "message",
                "user": "U123ABC",
                "text": "Hello there!",
                "ts": "1629390000.000100",
            },
            {
                "type": "message",
                "user": "U456DEF",
                "text": "Hi!",
                "ts": "1629390000.000200",
            },
        ]

        async_client = AsyncMock()
        result = await format_messages(
            thread_messages, "U123ABC", app_config, async_client
        )

        self.assertIsInstance(result[0], AIMessage)
        self.assertIsInstance(result[1], HumanMessage)
        self.assertEqual(result[0].content, "Hello there!")
        second_message_content = result[1].content[0]
        if isinstance(second_message_content, dict):
            self.assertEqual(second_message_content.get("text"), "Hi!")
        else:
            self.fail("Second content item is not a dictionary.")


if __name__ == "__main__":
    unittest.main()
