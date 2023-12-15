from __future__ import annotations
from typing import Dict
from datetime import datetime, timedelta
import random
import logging
from config.app_config import (
    AppConfig,
    init_chat_model,
    init_proactive_chat_model,
    safely_get_field,
)
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

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

def should_reschedule(old_config: Dict[str, Any], new_config: Dict[str, Any]) -> bool:
    """
    Determines if the interval in proactive messaging settings has changed.

    Args:
        old_config (Dict[str, Any]): The old configuration settings.
        new_config (Dict[str, Any]): The new configuration settings.

    Returns:
        bool: True if the interval settings have changed, False otherwise.
    """
    old_interval = old_config.get('interval_days', 0)
    new_interval = new_config.get('interval_days', 0)
    return old_interval != new_interval

def calculate_next_schedule_time(config: Dict[str, Any]) -> datetime:
    """
    Calculates the next schedule time for a proactive message.

    Args:
        config (Dict[str, Any]): Proactive messaging configuration.

    Returns:
        datetime: The calculated next schedule time.
    """
    interval_days = config.getfloat("interval_days")
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
