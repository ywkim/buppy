from __future__ import annotations

import logging
from collections.abc import Generator
from typing import Any

import streamlit as st
from google.cloud import firestore
from google.oauth2 import service_account
from langchain.schema import AIMessage, BaseMessage, HumanMessage

from config.app_config import AppConfig, init_chat_model
from utils.logging_utils import create_log_message
from utils.message_utils import prepare_chat_messages

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class StreamlitAppConfig(AppConfig):
    """Manages application configuration for the Streamlit web chatbot."""

    def _load_config_from_streamlit_secrets(self):
        """Loads configuration from Streamlit secrets."""
        self.config.read_dict(
            {
                key: value
                for key, value in st.secrets.items()
                if key != "firebase_service_account"
            }
        )

    def _initialize_firebase_client(self) -> firestore.Client:
        """
        Initializes and returns a Firebase Firestore client using the service account details from Streamlit secrets.

        Returns:
            firestore.Client: The initialized Firestore client.

        Raises:
            ValueError: If the required service account details are not provided in Streamlit secrets.
        """
        service_account_info = st.secrets.get("firebase_service_account")
        if not service_account_info:
            logging.info(
                "Firebase service account details not found in Streamlit secrets. Using default credentials."
            )
            return firestore.Client()

        # Create a service account credential object
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info
        )

        project_id = service_account_info["project_id"]

        # Initialize and return the Firestore client with the credentials
        return firestore.Client(credentials=credentials, project=project_id)

    def load_config_from_firebase(self, companion_id: str) -> None:
        """
        Load configuration from Firebase Firestore using the provided companion ID.

        Args:
            companion_id (str): The unique identifier for the companion.

        Raises:
            FileNotFoundError: If the companion document does not exist in Firebase.
        """
        db = self._initialize_firebase_client()
        companion_ref = db.collection("Companions").document(companion_id)
        companion = companion_ref.get()
        if not companion.exists:
            raise FileNotFoundError(
                f"Companion with ID {companion_id} does not exist in Firebase."
            )

        self._apply_settings_from_companion(companion)

    def load_config(self) -> None:
        """Load configuration from Streamlit secrets."""
        self._load_config_from_streamlit_secrets()
        self._validate_config()


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
        st.title(st.session_state.companion_id)
    else:
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
                companion_id = st.session_state.companion_id
                app_config.load_config_from_firebase(companion_id)
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

    firebase_enabled = app_config.config.getboolean(
        "firebase", "enabled", fallback=False
    )
    if firebase_enabled:
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
        app_config.load_config_from_firebase(companion_id)
        logging.info("Override configuration with Firebase settings")

    # Display chat interface
    handle_chat_interaction(app_config)


if __name__ == "__main__":
    main()