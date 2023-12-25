from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

import streamlit as st
from langchain.schema import AIMessage, BaseMessage, HumanMessage

from config.app_config import AppConfig, init_chat_model
from config.streamlit_config import EntityType, StreamlitAppConfig
from utils.logging_utils import create_log_message
from utils.message_utils import prepare_chat_messages

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


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


def handle_chat_interaction(app_config: StreamlitAppConfig) -> None:
    """
    Manages the chat interaction, including displaying the chat interface and handling user inputs and responses.

    This function creates a user interface for the chatbot in a web browser using Streamlit.
    It maintains the session state to keep track of the conversation history and uses the
    chat model to generate responses to user inputs.

    Args:
        app_config (StreamlitAppConfig): The configuration object for the app.
    """
    # Initialize session state for conversation history
    if "thread_messages" not in st.session_state:
        st.session_state.thread_messages = []

    if "companion_id" in st.session_state:
        companion_name = st.session_state.companion_id
    else:
        companion_name = "Buppy"

    st.title(companion_name)

    # Display existing chat messages
    display_messages(st.session_state.thread_messages)

    # Accept user input and generate responses
    user_input = st.chat_input(f"Message {companion_name}...")
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
            if app_config.firebase_enabled:
                companion_id = st.session_state.companion_id
                app_config.load_config_from_firebase(companion_id, EntityType.COMPANION)
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
    chat = init_chat_model(app_config)
    prepared_messages = prepare_chat_messages(formatted_messages, app_config)
    for chunk in chat.stream(prepared_messages):
        yield str(chunk.content)


def display_companion_id_input() -> str | None:
    """
    Displays an input field in the Streamlit sidebar for the user to enter or change the companion_id.

    Returns:
        Optional[str]: The entered Companion ID, or None if not entered.
    """
    st.sidebar.title("Companion ID Settings")
    companion_id = st.sidebar.text_input("Enter Companion ID", key="companion_id_input")
    return companion_id


def main():
    """Main function to run the Streamlit chatbot app."""
    logging.info("Starting Streamlit chatbot app")

    app_config = StreamlitAppConfig()
    app_config.load_config()

    if app_config.firebase_enabled:
        companion_id = display_companion_id_input()
        if not companion_id:
            st.markdown("👈 상단 왼쪽 모서리에 있는 사이드바를 열어 Companion ID를 입력해 주세요.")
            return
        if (
            "companion_id" not in st.session_state
            or st.session_state.companion_id != companion_id
        ):
            st.session_state.companion_id = companion_id
            st.session_state.thread_messages = []
        app_config.load_config_from_firebase(companion_id, EntityType.COMPANION)
        logging.info("Override configuration with Firebase settings")

    # Display chat interface
    handle_chat_interaction(app_config)


if __name__ == "__main__":
    main()
