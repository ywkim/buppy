from __future__ import annotations

import json
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
            return_value={"user": {"id": "U123ABC", "name": "testuser"}}
        )

        result = await format_messages(
            thread_messages, "U123ABC", app_config, async_client
        )

        self.assertIsInstance(result[0], HumanMessage)
        self.assertIsInstance(result[1], AIMessage)
        self.assertIn("testuser", result[0].content[0]["text"])

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
        self.assertEqual(result[1].content[0]["text"], "Hi!")


if __name__ == "__main__":
    unittest.main()
