from __future__ import annotations

import argparse
import asyncio
import base64
import csv
import json
import logging
import os
import re
from configparser import ConfigParser
from typing import Any

import aiohttp
import emoji_data_python
from aiohttp import ClientError
from google.cloud import firestore
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp
from slack_bolt.context.say.async_say import AsyncSay
from slack_sdk.web.async_client import AsyncWebClient

ERROR_EMOJI = "bangbang"
EXCLUDED_EMOJIS = ["eyes", ERROR_EMOJI]

DEFAULT_CONFIG = {
    "settings": {
        "chat_model": "gpt-4",
        "system_prompt": "You are a helpful assistant.",
        "temperature": "0",
        "vision_enabled": "false",
    },
    "firebase": {"enabled": "false"},
}

EMOJI_SYSTEM_PROMPT = "사용자의 슬랙 메시지에 대한 반응을 슬랙 Emoji로 표시하세요. 표현하기 어렵다면 :?:를 사용해 주세요."

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class InvalidRoleError(Exception):
    """Raised when the role isn't AI or Human"""


class AppConfig:
    """Handles application configuration."""

    def __init__(self):
        """Initialize AppConfig."""
        self.config: ConfigParser = ConfigParser()
        self.config.read_dict(DEFAULT_CONFIG)

    @property
    def vision_enabled(self) -> bool:
        """Determines if vision (image analysis) feature is enabled."""
        return self.config.getboolean("settings", "vision_enabled", fallback=False)

    def load_config_from_file(self, config_file: str) -> None:
        """Load configuration from a given file path."""
        self.config.read(config_file)
        logging.info("Configuration loaded from file %s", config_file)

    def load_config_from_env_vars(self) -> None:
        """Load configuration from environment variables."""
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
                "vision_enabled": os.environ.get(
                    "VISION_ENABLED", DEFAULT_CONFIG["settings"]["vision_enabled"]
                ).lower()
                in {"true", "1", "yes"},
            },
            "firebase": {
                "enabled": os.environ.get(
                    "FIREBASE_ENABLED", DEFAULT_CONFIG["firebase"]["enabled"]
                ).lower()
                in {"true", "1", "yes"}
            },
        }
        self.config.read_dict(env_config)
        logging.info("Configuration loaded from environment variables")

    def _validate_config(self) -> None:
        """Validate that required configuration variables are present."""
        required_settings = ["openai_api_key", "slack_bot_token", "slack_app_token"]
        for setting in required_settings:
            assert setting in self.config["api"], f"Missing configuration for {setting}"

        self.bot_token = self.config.get("api", "slack_bot_token")
        self.app_token = self.config.get("api", "slack_app_token")

        required_firebase_settings = ["enabled"]
        for setting in required_firebase_settings:
            assert (
                setting in self.config["firebase"]
            ), f"Missing configuration for {setting}"

    async def load_config_from_firebase(self, bot_user_id: str) -> None:
        """
        Load configuration from Firebase Firestore. Uses default values from DEFAULT_CONFIG
        if certain configuration values are missing, except for 'prefix_messages_content',
        which defaults to None.

        Args:
            bot_user_id (str): The unique identifier for the bot.

        Raises:
            FileNotFoundError: If the bot or companion document does not exist in Firebase.
        """
        db = firestore.AsyncClient()
        bot_ref = db.collection("Bots").document(bot_user_id)
        bot = await bot_ref.get()
        if not bot.exists:
            raise FileNotFoundError(
                f"Bot with ID {bot_user_id} does not exist in Firebase."
            )
        companion_id = bot.get("CompanionId")
        companion_ref = db.collection("Companions").document(companion_id)
        companion = await companion_ref.get()
        if not companion.exists:
            raise FileNotFoundError(
                f"Companion with ID {companion_id} does not exist in Firebase."
            )

        # Retrieve settings and use defaults if necessary
        settings = {
            "chat_model": (
                safely_get_field(
                    companion, "chat_model", DEFAULT_CONFIG["settings"]["chat_model"]
                )
            ),
            "system_prompt": (
                safely_get_field(
                    companion,
                    "system_prompt",
                    DEFAULT_CONFIG["settings"]["system_prompt"],
                )
            ),
            "temperature": (
                safely_get_field(
                    companion, "temperature", DEFAULT_CONFIG["settings"]["temperature"]
                )
            ),
            "vision_enabled": (
                safely_get_field(
                    companion,
                    "vision_enabled",
                    DEFAULT_CONFIG["settings"]["vision_enabled"],
                )
            ),
        }

        # Add 'prefix_messages_content' only if it exists
        prefix_messages_content = safely_get_field(companion, "prefix_messages_content")
        if prefix_messages_content is not None:
            settings["prefix_messages_content"] = json.dumps(prefix_messages_content)

        # Apply the new configuration settings
        self.config.read_dict({"settings": settings})

        logging.info(
            "Configuration loaded from Firebase Firestore for bot %s", bot_user_id
        )

    def load_config(self, config_file: (str | None) = None) -> None:
        """Load configuration from a given file and fall back to environment variables if the file does not exist."""
        if config_file:
            if os.path.exists(config_file):
                self.load_config_from_file(config_file)
            else:
                raise FileNotFoundError(f"Config file {config_file} does not exist.")
        elif os.path.exists("config.ini"):
            self.load_config_from_file("config.ini")
        else:
            # If no config file provided, load config from environment variables
            self.load_config_from_env_vars()

        self._validate_config()

    def get_readable_config(self) -> str:
        """
        Retrieves a human-readable string of the current non-sensitive configuration.

        Returns:
            str: A string representing the current configuration excluding sensitive details.
        """
        readable_config = (
            f"Chat Model: {self.config.get('settings', 'chat_model')}\n"
            f"System Prompt: {self.config.get('settings', 'system_prompt')}\n"
            f"Temperature: {self.config.get('settings', 'temperature')}\n"
            f"Vision Enabled: {'Yes' if self.vision_enabled else 'No'}"
        )
        return readable_config


def custom_serializer(obj: Any) -> str:
    """직렬화를 위한 사용자 정의 함수.

    Args:
        obj (Any): 직렬화할 객체.

    Returns:
        str: 객체의 직렬화된 문자열 표현.

    Raises:
        TypeError: 직렬화할 수 없는 객체 타입일 경우.
    """
    if isinstance(obj, BaseMessage):
        return f"{obj.__class__.__name__}({obj})"
    if hasattr(obj, "__str__"):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def create_log_message(message: str, **kwargs: Any) -> str:
    """로그 메시지 생성 및 JSON 형식으로 변환.

    Args:
        message (str): 로그 메시지.
        **kwargs (Any): 추가 로그 매개변수.

    Returns:
        str: JSON 형식으로 변환된 로그 메시지.
    """
    log_entry = {"message": message, **kwargs}
    return json.dumps(
        log_entry, default=custom_serializer, ensure_ascii=False, indent=4
    )


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


def encode_image_to_base64(image_data: bytes) -> str | None:
    """
    Encodes image data to a Base64 string.

    Args:
    image_data (bytes): The raw bytes of the image.

    Returns:
    Optional[str]: The Base64 encoded string of the image, or None if the input is None.
    """
    if image_data is not None:
        return base64.b64encode(image_data).decode("utf-8")
    return None


def init_chat_model(config: ConfigParser) -> ChatOpenAI:
    """Initialize the langchain chat model."""
    chat = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=float(config.get("settings", "temperature")),
        openai_api_key=config.get("api", "openai_api_key"),
    )  # type: ignore
    return chat


def register_events_and_commands(app: AsyncApp, app_config: AppConfig) -> None:
    """
    Registers event handlers with the Slack application.

    Args:
        app (AsyncApp): The Slack application to which the event handlers will be registered.
        app_config (AppConfig): The application configuration.
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
            firebase_enabled = app_config.config.getboolean(
                "firebase", "enabled", fallback=False
            )
            if firebase_enabled:
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
                emoji_reactions = await analyze_sentiment(
                    message_text, app_config.config
                )
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

                response_message = await ask_question(
                    formatted_messages, app_config.config
                )
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
    thread_messages: list[dict[str, Any]], bot_user_id: str, app_config: AppConfig
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
        message_content: list[dict[str, Any]] = []

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


def load_prefix_messages_from_file(file_path: str) -> list[BaseMessage]:
    """
    Load prefix messages from a CSV file and return a list of message objects.

    Args:
    file_path (str): Path of the CSV file containing prefix messages.

    Returns:
    list[BaseMessage]: A list of message objects created from the file.

    Raises:
    InvalidRoleError: If the role in the CSV file isn't 'AI' or 'Human'.
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
            else:
                raise InvalidRoleError(
                    f"Invalid role {role} in CSV file. Role must be either 'AI' or 'Human'."
                )

    return messages


def format_prefix_messages_content(prefix_messages_json: str) -> list[BaseMessage]:
    """
    Format prefix messages content from json string to BaseMessage objects

    Args:
        prefix_messages_json (str): JSON string with prefix messages content

    Returns:
        list[BaseMessage]: list of BaseMessage instances

    Raises:
        InvalidRoleError: If the role in the content isn't 'assistant', 'user', or 'system'.
    """
    prefix_messages = json.loads(prefix_messages_json)
    formatted_messages: list[BaseMessage] = []

    for msg in prefix_messages:
        role = msg["role"]
        content = msg["content"]

        if role.lower() == "user":
            formatted_messages.append(HumanMessage(content=content))
        elif role.lower() == "system":
            formatted_messages.append(SystemMessage(content=content))
        elif role.lower() == "assistant":
            formatted_messages.append(AIMessage(content=content))
        else:
            raise InvalidRoleError(
                f"Invalid role {role} in prefix content message. Role must be 'assistant', 'user', or 'system'."
            )

    return formatted_messages


async def ask_question(
    formatted_messages: list[BaseMessage], config: ConfigParser
) -> str:
    """
    Pass the formatted_messages to the Chat API and return the response content.

    Args:
        formatted_messages (list[BaseMessage]): list of formatted messages.
        config (ConfigParser): Configuration parameters for the application.

    Returns:
        str: Content of the response from the Chat API.
    """
    system_prompt = SystemMessage(content=config.get("settings", "system_prompt"))

    # Check if 'message_file' setting presents. If it does, load prefix messages from file.
    # If not, check if 'prefix_messages_content' is not None, then parse it to create the list of prefix messages
    message_file_path = config.get("settings", "message_file", fallback=None)
    prefix_messages_content = config.get(
        "settings", "prefix_messages_content", fallback=None
    )

    prefix_messages: list[BaseMessage] = []

    if message_file_path:
        logging.info("Loading prefix messages from file %s", message_file_path)
        prefix_messages = load_prefix_messages_from_file(message_file_path)
    elif prefix_messages_content:
        logging.info("Parsing prefix messages from settings")
        prefix_messages = format_prefix_messages_content(prefix_messages_content)

    # Appending prefix messages before the main conversation
    formatted_messages = prefix_messages + formatted_messages

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

    app_config = AppConfig()
    app_config.load_config(args.config_file)

    logging.info("Initializing AsyncApp and SocketModeHandler")
    app = AsyncApp(token=app_config.bot_token)
    handler = AsyncSocketModeHandler(app, app_config.app_token)

    # Fetch bot's user id
    bot_auth_info = await app.client.auth_test()
    bot_user_id = bot_auth_info["user_id"]
    logging.info("Bot User ID is %s", bot_user_id)

    firebase_enabled = app_config.config.getboolean(
        "firebase", "enabled", fallback=False
    )
    if firebase_enabled:
        await app_config.load_config_from_firebase(bot_user_id)
        logging.info("Override configuration with Firebase settings")

    logging.info("Registering event and command handlers")
    register_events_and_commands(app, app_config)

    logging.info("Starting SocketModeHandler")
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
