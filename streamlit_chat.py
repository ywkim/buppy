from __future__ import annotations

import json
import logging
from collections.abc import Generator
from typing import Any

import streamlit as st
from google.cloud import firestore
from langchain.chat_models import ChatOpenAI
from langchain.schema import AIMessage, BaseMessage, HumanMessage, SystemMessage

from config.app_config import AppConfig, safely_get_field
from utils.logging_utils import create_log_message
from utils.message_utils import InvalidRoleError, load_prefix_messages_from_file

MAX_TOKENS = 1023

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class StreamlitAppConfig(AppConfig):
    """Manages application configuration for the Streamlit web chatbot."""

    def _load_config_from_streamlit_secrets(self):
        """Loads configuration from Streamlit secrets."""
        self.config.read_dict(st.secrets)

    def load_config_from_firebase(self, companion_id: str) -> None:
        """
        Load configuration from Firebase Firestore using the provided companion ID.

        Args:
            companion_id (str): The unique identifier for the companion.

        Raises:
            FileNotFoundError: If the companion document does not exist in Firebase.
        """
        db = firestore.Client()
        companion_ref = db.collection("Companions").document(companion_id)
        companion = companion_ref.get()
        if not companion.exists:
            raise FileNotFoundError(
                f"Companion with ID {companion_id} does not exist in Firebase."
            )

        # Retrieve settings and use defaults if necessary
        settings = {
            "chat_model": (
                safely_get_field(
                    companion,
                    "chat_model",
                    self.DEFAULT_CONFIG["settings"]["chat_model"],
                )
            ),
            "system_prompt": (
                safely_get_field(
                    companion,
                    "system_prompt",
                    self.DEFAULT_CONFIG["settings"]["system_prompt"],
                )
            ),
            "temperature": (
                safely_get_field(
                    companion,
                    "temperature",
                    self.DEFAULT_CONFIG["settings"]["temperature"],
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
            "Configuration loaded from Firebase Firestore for companion %s",
            companion_id,
        )

    def load_config(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._load_config_from_streamlit_secrets()
        self._validate_config()


def init_chat_model(app_config: AppConfig) -> ChatOpenAI:
    """
    Initialize the langchain chat model.

    Args:
        app_config (AppConfig): Application configuration object.

    Returns:
        ChatOpenAI: Initialized chat model.
    """
    config = app_config.config
    chat = ChatOpenAI(
        model=config.get("settings", "chat_model"),
        temperature=float(config.get("settings", "temperature")),
        openai_api_key=config.get("api", "openai_api_key"),
        openai_organization=config.get("api", "openai_organization", fallback=None),
        max_tokens=MAX_TOKENS,
    )  # type: ignore
    return chat


def display_messages(messages: list[dict[str, Any]]) -> None:
    """
    Displays chat messages in the Streamlit interface.

    This function iterates over a list of messages and displays them in the Streamlit chat interface.
    Each message is displayed with the appropriate role (user or assistant).

    Args:
        messages (list[dict[str, Any]]): A list of message dictionaries, where each message has a 'role' and 'content'.
    """
    for message in messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def handle_chat_interaction(app_config: AppConfig) -> None:
    """
    Displays the chat interface and handles user interactions in Streamlit.

    This function creates a user interface for the chatbot in a web browser using Streamlit.
    It maintains the session state to keep track of the conversation history and uses the
    chat model to generate responses to user inputs.

    Args:
        app_config (AppConfig): The application configuration object containing settings for the chat model.
    """
    # Initialize session state for conversation history
    if "thread_messages" not in st.session_state:
        st.session_state.thread_messages = []

    st.title("Buppy")

    # Display existing chat messages
    display_messages(st.session_state.thread_messages)

    # Accept user input and generate responses
    user_input = st.chat_input("Message Buppy...")
    logging.info(
        create_log_message(
            "Received a question from user",
            user_input=user_input,
        )
    )

    if user_input:
        user_message = {"role": "user", "content": user_input}
        st.session_state.thread_messages.append(user_message)
        display_messages([user_message])

        try:
            # If Firebase is enabled, override the config with the one from Firebase
            firebase_enabled = app_config.config.getboolean(
                "firebase", "enabled", fallback=False
            )
            if firebase_enabled:
                companion_id = st.secrets["COMPANION_ID"]
                if companion_id is None:
                    raise ValueError("COMPANION_ID is not defined in st.secrets")
                app_config.load_config_from_firebase(str(companion_id))
                logging.info("Override configuration with Firebase settings")

            # Format messages for chat model processing
            formatted_messages = format_messages(st.session_state.thread_messages)
            logging.info(
                create_log_message(
                    "Sending messages to OpenAI API",
                    messages=formatted_messages,
                )
            )

            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                response_message = ""

            # Generate response using chat model
            for message_chunk in ask_question(formatted_messages, app_config):
                logging.info(
                    create_log_message(
                        "Received response from OpenAI API",
                        message_chunk=message_chunk,
                    )
                )
                response_message += message_chunk
                message_placeholder.markdown(response_message + "▌")
            message_placeholder.markdown(response_message)

            assistant_message = {"role": "assistant", "content": response_message}
            st.session_state.thread_messages.append(assistant_message)
        except Exception:  # pylint: disable=broad-except
            logging.error("Error in chat interface: ", exc_info=True)
            error_message = (
                "Sorry, I encountered a problem while processing your request."
            )
            st.error(error_message)


def format_messages(thread_messages: list[dict[str, Any]]) -> list[BaseMessage]:
    """Formats messages for the chatbot's processing."""
    formatted_messages: list[BaseMessage] = []

    for msg in thread_messages:
        if msg["role"] == "user":
            formatted_messages.append(HumanMessage(content=msg["content"]))
        else:
            formatted_messages.append(AIMessage(content=msg["content"]))

    return formatted_messages


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


def ask_question(
    formatted_messages: list[BaseMessage], app_config: AppConfig
) -> Generator[str, None, None]:
    """
    Initialize a chat model and stream the chat conversation. This includes optional prefix messages loaded
    from a file or settings, followed by the main conversation messages. The function yields each chunk of
    the response content as it is received from the Chat API.

    Args:
        formatted_messages (list[BaseMessage]): List of formatted messages constituting the main conversation.
        app_config (AppConfig): Configuration parameters for the application.

    Yields:
        Generator[str, None, None]: Generator yielding each content chunk from the Chat API responses.
    """
    config = app_config.config
    system_prompt = SystemMessage(content=config.get("settings", "system_prompt"))

    # Check if 'message_file' setting presents. If it does, load prefix messages from file.
    # If not, check if 'prefix_messages_content' is not None, then parse it to create the list of prefix messages
    message_file_path = config.get("settings", "message_file", fallback=None)
    prefix_messages_content = config.get(
        "settings", "prefix_messages_content", fallback=None
    )

    prefix_messages: list[BaseMessage] = []

    if message_file_path:
        prefix_messages = load_prefix_messages_from_file(message_file_path)
        logging.info(
            "Loading %d prefix messages from file %s",
            len(prefix_messages),
            message_file_path,
        )
    elif prefix_messages_content:
        prefix_messages = format_prefix_messages_content(prefix_messages_content)
        logging.info("Parsing %d prefix messages from settings", len(prefix_messages))

    # Appending prefix messages before the main conversation
    formatted_messages = prefix_messages + formatted_messages

    chat = init_chat_model(app_config)
    for chunk in chat.stream([system_prompt, *formatted_messages]):
        yield str(chunk.content)


def main():
    """Main function to run the Streamlit chatbot app."""
    logging.info("Starting Streamlit chatbot app")

    app_config = StreamlitAppConfig()
    app_config.load_config()

    firebase_enabled = app_config.config.getboolean(
        "firebase", "enabled", fallback=False
    )
    if firebase_enabled:
        companion_id = st.secrets.get("COMPANION_ID")
        if companion_id is None:
            raise ValueError("COMPANION_ID is not defined in st.secrets")
        app_config.load_config_from_firebase(str(companion_id))
        logging.info("Override configuration with Firebase settings")

    # Display chat interface
    handle_chat_interaction(app_config)


if __name__ == "__main__":
    main()
