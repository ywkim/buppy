from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import re
from typing import Any

import aiohttp
import emoji_data_python
import sentry_sdk
from aiohttp import ClientError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.say.async_say import AsyncSay
from slack_sdk.web.async_client import AsyncWebClient

from config.app_config import AppConfig, init_chat_model
from config.slack_config import SlackAppConfig
from utils.logging_utils import create_log_message
from utils.message_utils import prepare_chat_messages
from utils.proactive_messaging_utils import (
    ProactiveMessagingContext,
    calculate_next_schedule_time,
    generate_and_send_proactive_message,
)

ERROR_EMOJI = "bangbang"
EXCLUDED_EMOJIS = ["eyes", ERROR_EMOJI]

EMOJI_SYSTEM_PROMPT = "사용자의 슬랙 메시지에 대한 반응을 슬랙 Emoji로 표시하세요. 표현하기 어렵다면 :?:를 사용해 주세요."

sentry_sdk.init()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def schedule_next_proactive_message(
    context: ProactiveMessagingContext, scheduler: AsyncIOScheduler
):
    """
    Schedules the next proactive message.

    This function calculates the next time to send a proactive message based on the
    interval setting and schedules the message accordingly.
    """
    next_schedule_time = calculate_next_schedule_time(
        context.app_config.proactive_messaging_settings
    )
    scheduler.add_job(
        send_proactive_message,
        "date",
        run_date=next_schedule_time,
        args=[context, scheduler],
    )
    logging.info("Next proactive message scheduled for: %s", next_schedule_time)


async def send_proactive_message(
    context: ProactiveMessagingContext, scheduler: AsyncIOScheduler
):
    """
    Sends a proactive message to the specified Slack channel.

    This function generates a proactive message using the chat model based on the
    system prompt configured in the app settings. It then sends the generated message
    to the specified Slack channel and schedules the next proactive message.
    """
    if context.app_config.firebase_enabled:
        await context.app_config.load_config_from_firebase(context.bot_user_id)
        logging.info("Configuration updated from Firebase Firestore.")

    await generate_and_send_proactive_message(context)

    channel = context.app_config.proactive_slack_channel
    logging.info(
        create_log_message(
            "Proactive message sent to channel",
            channel=channel,
        )
    )

    # Schedule the next proactive message
    await schedule_next_proactive_message(context, scheduler)


def extract_image_url(message: dict[str, Any]) -> str | None:
    """
    Extracts the image URL from a Slack message object.

    Args:
    message (dict[str, Any]): The Slack message object.

    Returns:
    Optional[str]: The extracted image URL if present, otherwise None.
    """
    if "files" in message:
        for file in message["files"]:
            if file["mimetype"].startswith("image/"):
                return file.get("url_private") or file.get("url_private_download")

    return None


async def download_image(url: str, token: str) -> bytes:
    """
    Asynchronously downloads an image from a given URL with Slack authorization.
    Raises an exception if the download fails.

    Args:
    url (str): The URL of the image to download.
    token (str): Slack API token for authorization.

    Returns:
    bytes: The raw bytes of the image.

    Raises:
    ClientError: If the download fails or the response status is not 200.
    """
    headers = {"Authorization": f"Bearer {token}"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise ClientError(f"Failed to download image: {response.status}")
            return await response.read()


def encode_image_to_base64(image_data: bytes) -> str:
    """
    Encodes the given image data to a Base64 string.

    Args:
        image_data (bytes): The raw bytes of the image.

    Returns:
        str: The Base64 encoded string of the image.
    """
    return base64.b64encode(image_data).decode("utf-8")


def register_events_and_commands(app: AsyncApp, app_config: SlackAppConfig) -> None:
    """
    Registers event handlers with the Slack application.

    Args:
        app (AsyncApp): The Slack application to which the event handlers will be registered.
        app_config (SlackAppConfig): The application configuration.
    """

    @app.event("message")
    async def handle_message_events(body, logger):
        formatted_body = json.dumps(body, ensure_ascii=False, indent=4)
        logger.debug(formatted_body)

    @app.event("app_mention")
    async def handle_mention_events(
        body: dict[str, Any],
        client: AsyncWebClient,
        say: AsyncSay,
        logger: logging.Logger,
    ) -> None:
        """
        Handles events where the bot is mentioned.

        Args:
            body (dict[str, Any]): The request body of the event.
            client: The Slack client instance used for making API calls.
            say: Function to send a message to the channel where the event was invoked.
            logger (logging.Logger): Logger for logging events.
        """
        event = body["event"]
        channel_id = event["channel"]
        ts = event["ts"]
        thread_ts = event.get("thread_ts", None) or ts
        user_id = event["user"]
        bot_user_id = body["authorizations"][0]["user_id"]
        message_text = event["text"].replace(f"<@{bot_user_id}>", "").strip()

        logger.info(
            create_log_message(
                "Received a question from user",
                user_id=user_id,
                message_text=message_text,
            )
        )

        # Acknowledge the incoming message with 'eyes' emoji
        reaction = await client.reactions_add(
            name="eyes", channel=channel_id, timestamp=ts
        )
        logger.info(f"Added reaction to the message: {reaction}")

        try:
            # If Firebase is enabled, override the config with the one from Firebase
            if app_config.firebase_enabled:
                await app_config.load_config_from_firebase(bot_user_id)
                logging.info("Override configuration with Firebase settings")

            # Check if the mention contains a request for the configuration.
            if "config" in message_text.lower():
                # Fetching readable configuration and adding bot user ID.
                config_info = app_config.get_readable_config()
                config_info += f"\nBot User ID: {bot_user_id}"
                # Respond in thread with the configuration information.
                await say(
                    text=f"*Current Configuration*\n{config_info}", thread_ts=thread_ts
                )
            else:
                logger.info(
                    "Analyzing sentiment of the user message for emoji reaction"
                )
                emoji_reactions = await analyze_sentiment(message_text, app_config)
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
                thread_messages: list[dict[str, Any]] = thread_messages_response.get(
                    "messages", []
                )

                formatted_messages = await format_messages(
                    thread_messages, bot_user_id, app_config
                )
                logger.info(
                    create_log_message(
                        "Sending messages to OpenAI API",
                        messages=formatted_messages,
                    )
                )

                response_message = await ask_question(formatted_messages, app_config)
                logger.info(
                    create_log_message(
                        "Received response from OpenAI API",
                        response_message=response_message,
                    )
                )

                await say(text=response_message, thread_ts=thread_ts)
        except Exception:  # pylint: disable=broad-except
            logger.error("Error handling app_mention event: ", exc_info=True)
            await say(
                channel=user_id,
                text=f"Sorry, I encountered a problem while trying to process your request regarding the message: '{message_text}'. The engineering team has been notified.",
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


async def analyze_sentiment(message: str, app_config: AppConfig) -> list[str]:
    system_prompt = SystemMessage(content=EMOJI_SYSTEM_PROMPT)
    chat = init_chat_model(app_config)
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
        list[str]: A list of the valid emoji codes found in the input_string, without colons.
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

    return input_code in emoji_data_python.emoji_short_names


async def format_messages(
    thread_messages: list[dict[str, Any]], bot_user_id: str, app_config: SlackAppConfig
) -> list[BaseMessage]:
    """
    Formats messages from a Slack thread into a list of HumanMessage objects,
    downloading and encoding images as Base64 if enabled in the AppConfig.

    Args:
    thread_messages (list[dict[str, Any]]): list of messages from the Slack thread.
    bot_user_id (str): The user ID of the bot.
    app_config (AppConfig): The application configuration object.

    Returns:
    list[BaseMessage]: A list of formatted HumanMessage objects.
    """
    # Check if the messages are sorted in ascending order by 'ts'
    assert all(
        thread_messages[i]["ts"] <= thread_messages[i + 1]["ts"]
        for i in range(len(thread_messages) - 1)
    ), "Messages are not sorted in ascending order."

    formatted_messages: list[BaseMessage] = []

    for msg in thread_messages:
        role = "assistant" if msg.get("user") == bot_user_id else "user"
        text_content = msg.get("text", "").replace(f"<@{bot_user_id}>", "").strip()
        message_content: list[str | dict[str, Any]] = []

        # Append text content to message_content
        if text_content:
            message_content.append({"type": "text", "text": text_content})

        if app_config.vision_enabled:
            image_url = extract_image_url(msg)
            if image_url:
                image_data = await download_image(image_url, app_config.bot_token)
                base64_image = encode_image_to_base64(image_data)
                message_content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    }
                )

        if role == "user":
            formatted_messages.append(HumanMessage(content=message_content))
        else:
            formatted_messages.append(AIMessage(content=text_content))

    return formatted_messages


async def ask_question(
    formatted_messages: list[BaseMessage], app_config: AppConfig
) -> str:
    """
    Pass the formatted_messages to the Chat API and return the response content.

    Args:
        formatted_messages (list[BaseMessage]): list of formatted messages.
        app_config (AppConfig): Configuration parameters for the application.

    Returns:
        str: Content of the response from the Chat API.
    """
    chat = init_chat_model(app_config)
    prepared_messages = prepare_chat_messages(formatted_messages, app_config)
    resp = await chat.agenerate([prepared_messages])
    return resp.generations[0][0].text


async def main():
    logging.info("Starting bot")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config_file",
        help=(
            "Path to the configuration file. If no path is provided, will try to "
            "load from `config.ini` and environmental variables."
        ),
    )
    args = parser.parse_args()

    app_config = SlackAppConfig()
    app_config.load_config(args.config_file)

    # Load Firebase configuration if enabled
    if app_config.firebase_enabled:
        bot_user_id_from_config = app_config.api_settings.slack_bot_user_id
        if bot_user_id_from_config is None:
            raise ValueError("Bot User ID is not configured in API settings.")

        await app_config.load_config_from_firebase(bot_user_id_from_config)
        logging.info("Override configuration with Firebase settings")

    logging.info("Initializing AsyncApp and SocketModeHandler")
    app = AsyncApp(token=app_config.bot_token)
    handler = AsyncSocketModeHandler(app, app_config.app_token)

    # Fetch bot's user id from Slack API
    bot_auth_info = await app.client.auth_test()
    bot_user_id = bot_auth_info["user_id"]
    logging.info("Bot User ID from Slack API is %s", bot_user_id)

    if app_config.firebase_enabled:
        # Check if Bot User IDs match
        if bot_user_id_from_config != bot_user_id:
            raise ValueError(
                "Mismatch between Bot User ID from Slack API and Firebase configuration."
            )

    logging.info("Registering event and command handlers")
    register_events_and_commands(app, app_config)

    if app_config.proactive_messaging_enabled and not app_config.firebase_enabled:
        scheduler = AsyncIOScheduler()
        context = ProactiveMessagingContext(app, app_config, bot_user_id)
        await schedule_next_proactive_message(context, scheduler)
        scheduler.start()
        logging.info("Proactive messaging has been scheduled.")

    logging.info("Starting SocketModeHandler")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
