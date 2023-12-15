from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from langchain.schema import SystemMessage
from slack_bolt.async_app import AsyncApp

from config.app_config import init_proactive_chat_model
from config.slack_config import SlackAppConfig


class ProactiveMessagingContext:
    """
    Represents the context for proactive messaging.

    Attributes:
        app (AsyncApp): The Slack app instance.
        app_config (SlackAppConfig): The application configuration.
        bot_user_id (str): The user ID of the bot.
    """

    def __init__(self, app: AsyncApp, app_config: SlackAppConfig, bot_user_id: str):
        self.app = app
        self.app_config = app_config
        self.bot_user_id = bot_user_id


def should_reschedule(old_config: dict[str, Any], new_config: dict[str, Any]) -> bool:
    """
    Determines if the interval in proactive messaging settings has changed.

    Args:
        old_config (dict[str, Any]): The old configuration settings.
        new_config (dict[str, Any]): The new configuration settings.

    Returns:
        bool: True if the interval settings have changed, False otherwise.
    """
    old_interval = old_config["interval_days"]
    new_interval = new_config["interval_days"]
    return old_interval != new_interval


def calculate_next_schedule_time(config: dict[str, Any]) -> datetime:
    """
    Calculates the next schedule time for a proactive message.

    Args:
        config (dict[str, Any]): Proactive messaging configuration.

    Returns:
        datetime: The calculated next schedule time.
    """
    interval_days = config["interval_days"]
    return datetime.now() + timedelta(days=interval_days * random.random() * 2)


async def generate_and_send_proactive_message(context: ProactiveMessagingContext):
    """
    Generates a proactive message using the chat model based on the system prompt
    and sends the generated message to the specified Slack channel.

    Args:
        context (ProactiveMessagingContext): Context containing app, app_config, and bot_user_id.
    """
    # Initialize chat model and generate message
    chat = init_proactive_chat_model(context.app_config)
    system_prompt = SystemMessage(content=context.app_config.proactive_system_prompt)
    resp = await chat.agenerate([[system_prompt]])
    message = resp.generations[0][0].text

    # Send the generated message to the specified Slack channel
    channel = context.app_config.proactive_slack_channel
    await context.app.client.chat_postMessage(channel=channel, text=message)
