from __future__ import annotations

import argparse
import asyncio
import configparser
import csv
import logging
import os
import re
from configparser import ConfigParser
from typing import Any

import emoji
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

ERROR_EMOJI = "bangbang"
EXCLUDED_EMOJIS = ["eyes", ERROR_EMOJI]

DEFAULT_CONFIG = {
    "settings": {
        "chat_model": "gpt-4",
        "system_prompt": "You are a helpful assistant.",
        "temperature": "0",
    },
}

EMOJI_SYSTEM_PROMPT = "사용자의 슬랙 메시지에 대한 반응을 표준 Emoji로 표시하세요. 표현하기 어렵다면 :?:를 사용해 주세요."

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def load_config_from_file(config_file: str) -> ConfigParser:
    config = ConfigParser()
    config.read_dict(DEFAULT_CONFIG)
    config.read(config_file)
    return config


def load_config_from_env_vars() -> ConfigParser:
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
    config = ConfigParser()
    config.read_dict(env_config)
    return config


def load_config(config_file: (str | None) = None) -> ConfigParser:
    """Load configuration from a given file and fall back to environment variables if the file does not exist."""
    if config_file:
        if os.path.exists(config_file):
            return load_config_from_file(config_file)
        raise FileNotFoundError(f"Config file {config_file} does not exist.")

    if os.path.exists("config.ini"):
        return load_config_from_file("config.ini")

    # If no config file provided, load config from environment variables
    return load_config_from_env_vars()


def init_chat_model(config: ConfigParser) -> ChatOpenAI:
    """Initialize the langchain chat model."""
    chat = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=float(config.get("settings", "temperature")),
        openai_api_key=config.get("api", "openai_api_key"),
    )  # type: ignore
    return chat


def register_events_and_commands(app: AsyncApp, config: ConfigParser) -> None:
    @app.event("message")
    async def handle_message_events(body, logger):
        logger.info(body)

    @app.event("app_mention")
    async def handle_mention_events(
        body: dict[str, Any], client, say, logger: logging.Logger
    ):
        """
        Handle events where the bot is mentioned.
        Fetch the thread messages, format them and call the Chat API to get a response.
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
            logger.info("Analyzing sentiment of the user message for emoji reaction")
            emoji_reactions = await analyze_sentiment(message_text, config)
            emoji_reactions = [
                emoji for emoji in emoji_reactions if emoji not in EXCLUDED_EMOJIS
            ]
            logger.info(f"Suggested emoji reactions are: {emoji_reactions}")

            for emoji_reaction in emoji_reactions:
                reaction_response = await client.reactions_add(
                    name=emoji_reaction, channel=channel_id, timestamp=ts
                )
                logger.info(f"Added emoji reaction: {reaction_response}")

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

            # Add error emoji reaction to user's message
            response = await client.reactions_add(
                name=ERROR_EMOJI, channel=channel_id, timestamp=ts
            )
            logger.info(f"Added error emoji reaction: {response}")

        response = await client.reactions_remove(
            name="eyes", channel=channel_id, timestamp=ts
        )
        logger.info(f"Remove reaction to the message: {response}")


async def analyze_sentiment(message: str, config: ConfigParser) -> list[str]:
    system_prompt = SystemMessage(content=EMOJI_SYSTEM_PROMPT)
    chat = init_chat_model(config)
    formatted_message = HumanMessage(content=message)
    resp = await chat.agenerate([[system_prompt, formatted_message]])
    response_message = resp.generations[0][0].text
    emoji_codes = get_valid_emoji_codes(response_message)
    return emoji_codes


def get_valid_emoji_codes(input_string: str) -> list[str]:
    """
    This function takes a string contains emoji codes, validates each emoji code
    and returns a list of valid emoji codes, without colons.

    Args:
        input_string (str): A string that may contain emoji codes.

    Returns:
        List[str]: A list of the valid emoji codes found in the input_string, without colons.
    """

    # Find all substrings in the input_string that match the emoji code pattern.
    potential_codes = re.findall(r"(:[a-zA-Z0-9_+-]+:)", input_string)

    # Validate each emoji code and return only the valid ones without colons.
    valid_codes = [
        code.strip(":")
        for code in potential_codes
        if is_valid_emoji_code(code.strip(":"))
    ]

    return valid_codes


def is_valid_emoji_code(input_code: str) -> bool:
    """
    This function takes a potential emoji code (without colons),
    examines its validity, and returns a boolean result.

    Args:
        input_code (str): A potential emoji code (without colons).

    Returns:
        bool: True if input_code is a valid emoji code, otherwise False.
    """

    # Convert the potential emoji code to unicode.
    unicode_conversion = emoji.emojize(f":{input_code}:", language="alias")

    # Check if the conversion is successful by comparing it with the input_code.
    return unicode_conversion != f":{input_code}:"


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


def load_additional_messages_from_file(file_path: str) -> list[BaseMessage]:
    """
    Load additional messages from a CSV file and return a list of message objects.

    Args:
    file_path (str): Path of the CSV file containing additional messages.

    Returns:
    List[BaseMessage]: A list of message objects created from the file.
    """
    messages: list[BaseMessage] = []

    with open(file_path, "r", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            role, content = row
            if role == "Human":
                messages.append(HumanMessage(content=content))
            elif role == "AI":
                messages.append(AIMessage(content=content))

    return messages


async def ask_question(
    formatted_messages: list[BaseMessage], config: ConfigParser
) -> str:
    """
    Pass the formatted_messages to the Chat API and return the response content.

    Args:
    formatted_messages (List[BaseMessage]): List of formatted messages.
    config (ConfigParser): Configuration parameters for the application.

    Returns:
    str: Content of the response from the Chat API.
    """
    system_prompt = SystemMessage(content=config.get("settings", "system_prompt"))

    # Try to load additional messages from a file if provided in the settings.
    message_file_path = config.get("settings", "message_file", fallback=None)
    if message_file_path:
        logging.info("Loading additional messages from file %s", message_file_path)
        additional_messages = load_additional_messages_from_file(message_file_path)
        formatted_messages = additional_messages + formatted_messages
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
