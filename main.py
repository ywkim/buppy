from __future__ import annotations

import argparse
import asyncio
import configparser
import logging
import os
from typing import Any

from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

DEFAULT_CONFIG = {
    "settings": {
        "chat_model": "gpt-4",
        "system_prompt": "You are a helpful assistant.",
        "temperature": "0",
    },
}

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_config_from_file(config_file: str) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.read_dict(DEFAULT_CONFIG)
    config.read(config_file)
    return config


def load_config_from_env_vars():
    env_config: dict[str, dict[str, Any]] = {
        "api": {
            "openai_api_key": os.environ.get("OPENAI_API_KEY"),
            "slack_bot_token": os.environ.get("SLACK_BOT_TOKEN"),
            "slack_app_token": os.environ.get("SLACK_APP_TOKEN"),
        },
        "settings": {
            "chat_model": os.environ.get(
                "CHAT_MODEL", DEFAULT_CONFIG["settings"]["chat_model"]
            ),
            "system_prompt": os.environ.get(
                "SYSTEM_PROMPT", DEFAULT_CONFIG["settings"]["system_prompt"]
            ),
            "temperature": os.environ.get(
                "TEMPERATURE", DEFAULT_CONFIG["settings"]["temperature"]
            ),
        },
    }
    config = configparser.ConfigParser()
    config.read_dict(env_config)
    return config


def load_config(config_file: (str | None) = None) -> configparser.ConfigParser:
    """Load configuration from a given file and fall back to environment variables if the file does not exist."""
    if config_file:
        if os.path.exists(config_file):
            return load_config_from_file(config_file)
        raise FileNotFoundError(f"Config file {config_file} does not exist.")

    if os.path.exists("config.ini"):
        return load_config_from_file("config.ini")

    # If no config file provided, load config from environment variables
    return load_config_from_env_vars()


def init_chat_model(config: configparser.ConfigParser) -> ChatOpenAI:
    """Initialize the langchain chat model."""
    chat = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=float(config.get("settings", "temperature")),
        openai_api_key=config.get("api", "openai_api_key"),
    )  # type: ignore
    return chat


def register_events_and_commands(
    app: AsyncApp, config: configparser.ConfigParser
) -> None:
    @app.event("message")
    async def handle_message_events(body, logger):
        logger.info(body)

    @app.event("app_mention")
    async def handle_mention_events(
        body: dict[str, Any], client, say, logger: logging.Logger
    ):
        """
        Handle events where the bot is mentioned. Fetch the thread messages, format them and call the Chat API to get a response.
        Then send the response to the thread.
        """
        event = body["event"]
        channel_id = event["channel"]
        ts = event["ts"]
        thread_ts = event.get("thread_ts", None) or ts
        user = event["user"]
        bot_user_id = body["authorizations"][0]["user_id"]
        message_text = event["text"].replace(f"<@{bot_user_id}>", "").strip()

        logger.info(f"Received a question from {user}: {message_text}")

        # Acknowledge the incoming message with 'eyes' emoji
        reaction = await client.reactions_add(
            name="eyes", channel=channel_id, timestamp=ts
        )
        logger.info(f"Added reaction to the message: {reaction}")

        try:
            thread_messages_response = await client.conversations_replies(
                channel=channel_id, ts=thread_ts
            )
            thread_messages = thread_messages_response.get("messages", [])

            formatted_messages = format_messages(thread_messages, bot_user_id)
            logger.info(f"Sending {formatted_messages} messages to OpenAI API")
            response_message = await ask_question(formatted_messages, config)
            logger.info(f"Received {response_message} from OpenAI API")
            await say(text=response_message, thread_ts=thread_ts)
        except Exception:  # pylint: disable=broad-except
            logger.error("Error handling app_mention event: ", exc_info=True)
            await say(
                text="Sorry, I encountered a problem while trying to process your request. The engineering team has been notified.",
                thread_ts=thread_ts,
            )

        response = await client.reactions_remove(
            name="eyes", channel=channel_id, timestamp=ts
        )
        logger.info(f"Remove reaction to the message: {response}")


def format_messages(
    thread_messages: list[dict[str, Any]], bot_user_id: str
) -> list[BaseMessage]:
    """
    Format messages in a thread. Messages from the bot (designated by bot_user_id)
    are considered as messages from the 'assistant' and everything else as from the 'user'.
    """
    # Check if the messages are sorted in ascending order by 'ts'
    assert all(
        thread_messages[i]["ts"] <= thread_messages[i + 1]["ts"]
        for i in range(len(thread_messages) - 1)
    ), "Messages are not sorted in ascending order."

    formatted_messages: list[BaseMessage] = []

    for msg in thread_messages:
        role = "assistant" if msg.get("user") == bot_user_id else "user"
        content = msg["text"]
        if role == "user":
            content = content.replace(f"<@{bot_user_id}>", "").strip()
            formatted_messages.append(HumanMessage(content=content))
        else:
            formatted_messages.append(AIMessage(content=content))

    return formatted_messages


async def ask_question(formatted_messages: list[BaseMessage], config) -> str:
    """
    Pass the formatted_messages to the Chat API and return the response content.
    """
    system_prompt = SystemMessage(content=config.get("settings", "system_prompt"))
    chat = init_chat_model(config)
    resp = await chat.agenerate([[system_prompt, *formatted_messages]])
    return resp.generations[0][0].text


async def main():
    logging.info("Starting bot")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file",
        help="Path to the configuration file. If no path is provided, will try to load from `config.ini` and environmental variables.",
    )
    args = parser.parse_args()

    config = load_config(args.config_file)

    try:
        slack_bot_token = config.get("api", "slack_bot_token")
        slack_app_token = config.get("api", "slack_app_token")
    except configparser.NoOptionError as e:
        logging.error(
            "Configuration error: %s. Please provide the required api keys either in a config file or as environment variables.",
            e,
        )
        raise SystemExit from e

    logging.info("Initializing AsyncApp and SocketModeHandler")
    app = AsyncApp(token=slack_bot_token)
    handler = AsyncSocketModeHandler(app, slack_app_token)

    logging.info("Registering event and command handlers")
    register_events_and_commands(app, config)

    logging.info("Starting SocketModeHandler")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
