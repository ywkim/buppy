from __future__ import annotations

import csv
import logging
from io import StringIO
from typing import Any

import pytz
import streamlit as st

from celery_tasks.proactive_messaging_task import (
    cancel_current_proactive_message_task,
    schedule_proactive_message_task,
)
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from config.streamlit_config import StreamlitAppConfig
from config.sync_app_config import EntityType


class StreamlitAdminApp:
    """
    A Streamlit web app for administering a chatbot application.

    This class encapsulates the functionalities required for administering
    the chatbot settings, such as updating configurations and monitoring chatbot data.

    Attributes:
        app_config (StreamlitAppConfig): The application configuration object.
        db (firestore.Client): The Firestore client for database interactions.
    """

    def __init__(self):
        """Initializes the StreamlitAdminApp with necessary configurations."""
        self.app_config = StreamlitAppConfig()
        self.app_config.load_config()
        self.db = self.app_config.initialize_firestore_client()
        self.celery_app = self.app_config.initialize_celery_app("streamlit_admin_app")

    def get_entity_data(
        self, entity_type: EntityType, entity_id: str
    ) -> dict[str, Any]:
        """
        Retrieves data for a given entity (bot or companion) from Firestore.

        Args:
            entity_type: The type of entity (BOT or COMPANION).
            entity_id: The unique identifier of the entity.

        Returns:
            The data of the entity as a dictionary.

        Raises:
            ValueError: If the entity document does not exist.
        """
        entity_ref = self.db.collection(entity_type.value).document(entity_id)
        entity = entity_ref.get()
        if entity.exists:
            entity_data = entity.to_dict()
            assert entity_data is not None
            return entity_data
        raise ValueError(
            f"{entity_type.name} document with ID {entity_id} does not exist."
        )

    def upload_entity_data(
        self, entity_type: EntityType, entity_id: str, entity_data: dict[str, str]
    ) -> None:
        """
        Uploads data to Firestore for a given entity (bot or companion).

        Args:
            entity_type: The type of entity (BOT or COMPANION).
            entity_id: The unique identifier of the entity.
            entity_data: The data to upload.
        """
        entity_ref = self.db.collection(entity_type.value).document(entity_id)
        entity_ref.set(entity_data)
        logging.info("Uploaded %s data for ID %s", entity_type.name, entity_id)

    def get_entity_ids(self, entity_type: EntityType) -> list[str]:
        """
        Retrieves all IDs for a given entity type (bot or companion) from Firestore.

        Returns:
            A list of entity IDs.
        """
        entity_ref = self.db.collection(entity_type.value)
        entities = entity_ref.stream()
        return [entity.id for entity in entities]


def load_prefix_messages_from_csv(csv_content: str) -> list[dict[str, str]]:
    """
    Load prefix messages from a CSV string and return them as a list of dictionaries.

    Args:
        csv_content (str): The string content of the CSV file.

    Returns:
        list[dict[str, str]]: A list of dictionaries representing the messages.

    The CSV file should contain messages with their roles ('AI', 'Human', 'System')
    and content. These roles are mapped to Firestore roles ('assistant', 'user', 'system').
    """
    role_mappings = {"AI": "assistant", "Human": "user", "System": "system"}

    messages: list[dict[str, str]] = []

    reader = csv.reader(StringIO(csv_content))

    for row in reader:
        role, content = row
        if role not in role_mappings:
            raise ValueError(
                f"Invalid role '{role}' in CSV content. Must be one of {list(role_mappings.keys())}."
            )

        firestore_role = role_mappings[role]
        messages.append({"role": firestore_role, "content": content})

    return messages


def format_prefix_messages_for_display(messages: list[dict[str, str]]) -> str:
    """
    Formats the prefix messages as a string for display in a text area.

    Args:
        messages (list[dict[str, str]]): The list of prefix messages.

    Returns:
        str: The formatted string representation of the messages in CSV format.
    """
    output = StringIO()
    writer = csv.writer(output)
    role_mappings = {"assistant": "AI", "user": "Human", "system": "System"}

    for message in messages:
        # Convert Firestore role back to CSV role
        csv_role = role_mappings.get(message["role"], message["role"])
        writer.writerow([csv_role, message["content"]])

    return output.getvalue().strip()


def proactive_task_panel(
    admin_app: StreamlitAdminApp,
    proactive_settings: ProactiveMessagingSettings,
    bot_id: str,
):
    """Renders the proactive task management panel in Streamlit."""
    # Retrieve current task info
    task_id = proactive_settings.current_task_id
    scheduled_time_utc = proactive_settings.last_scheduled

    if task_id:
        if scheduled_time_utc and scheduled_time_utc.tzinfo is None:
            scheduled_time_utc = scheduled_time_utc.replace(tzinfo=pytz.utc)
        # Convert UTC time to local time (e.g., KST)
        kst = pytz.timezone("Asia/Seoul")
        scheduled_time_local = (
            scheduled_time_utc.astimezone(kst) if scheduled_time_utc else None
        )
        scheduled_time_str = (
            scheduled_time_local.strftime("%Y-%m-%d %H:%M:%S")
            if scheduled_time_local
            else "N/A"
        )
        st.text(f"Scheduled Time (KST): {scheduled_time_str}")
        if st.button("Cancel Current Task"):
            cancel_current_proactive_message_task(
                bot_id, admin_app.celery_app, admin_app.db
            )
            st.rerun()
    else:
        st.write("No task currently scheduled.")
        if st.button("Schedule New Task"):
            schedule_proactive_message_task(
                proactive_settings, bot_id, admin_app.celery_app, admin_app.db
            )
            st.rerun()


def handle_proactive_task_tab(admin_app: StreamlitAdminApp):
    """Handles the UI and logic for the proactive task management tab."""
    st.subheader("Proactive Messaging Task Management for Bots")

    bot_ids = admin_app.get_entity_ids(EntityType.BOT)
    selected_bot_id = st.selectbox("Select Bot ID", bot_ids)

    if selected_bot_id:
        existing_data = admin_app.get_entity_data(EntityType.BOT, selected_bot_id)
        proactive_settings_data: dict[str, Any] = existing_data.get(
            "proactive_messaging", {}
        )
        proactive_settings = ProactiveMessagingSettings(**proactive_settings_data)

        # Display current proactive settings in a user-friendly format
        if proactive_settings.enabled:
            with st.expander("Current Proactive Messaging Settings"):
                st.write(f"Enabled: {proactive_settings.enabled}")
                if proactive_settings.enabled:
                    st.write(f"Interval Days: {proactive_settings.interval_days}")
                    st.write(f"System Prompt: {proactive_settings.system_prompt}")
                    st.write(f"Slack Channel: {proactive_settings.slack_channel}")
                    st.write(f"Temperature: {proactive_settings.temperature}")
                    task_id = proactive_settings.current_task_id
                    scheduled_time = proactive_settings.last_scheduled
                    scheduled_time_str = (
                        scheduled_time.strftime("%Y-%m-%d %H:%M:%S")
                        if scheduled_time
                        else "N/A"
                    )
                    st.write(f"Current Task ID: {task_id or 'N/A'}")
                    st.write(f"Last Scheduled: {scheduled_time_str}")

            proactive_task_panel(admin_app, proactive_settings, selected_bot_id)
        else:
            st.warning("Proactive messaging is currently disabled for this bot.")
            st.info("Enable proactive messaging in the Bot settings to schedule tasks.")


def handle_entity_tab(admin_app: StreamlitAdminApp, entity_type: EntityType):
    """
    Handles the UI and logic for a specific entity tab (bot or companion).
    This function now delegates specific UI components to helper functions.

    Args:
        admin_app: The instance of StreamlitAdminApp.
        entity_type: The type of entity (BOT or COMPANION).
    """
    st.subheader(f"{entity_type.name.title()} Management")

    entity_ids = admin_app.get_entity_ids(entity_type)
    new_entity_option = f"Add New {entity_type.name.title()}"
    selected_entity_id = st.selectbox(
        f"Select {entity_type.name.title()} ID", [new_entity_option] + entity_ids
    )

    entity_id_to_upload = None
    existing_data: dict[str, Any] = {}
    if selected_entity_id == new_entity_option or selected_entity_id is None:
        entity_id_to_upload = st.text_input(f"Enter New {entity_type.name.title()} ID")
    else:
        entity_id_to_upload = selected_entity_id
        existing_data = admin_app.get_entity_data(entity_type, selected_entity_id)

    # Entity Specific UI Components
    if entity_type == EntityType.BOT:
        entity_data = handle_bot_settings(existing_data, admin_app)
    elif entity_type == EntityType.COMPANION:
        entity_data = handle_companion_settings(existing_data)

    if entity_id_to_upload and st.button(f"Upload {entity_type.name.title()} Data"):
        # Uploading data to Firestore
        admin_app.upload_entity_data(entity_type, entity_id_to_upload, entity_data)
        st.success(
            f"{entity_type.name.capitalize()} '{entity_id_to_upload}' data updated successfully."
        )


def handle_bot_settings(
    existing_data: dict[str, Any], admin_app: StreamlitAdminApp
) -> dict[str, Any]:
    """
    Handles the UI components specific to the Bot entity.

    Args:
        existing_data: The existing data of the bot entity.
        admin_app: The instance of StreamlitAdminApp.

    Returns:
        The updated bot entity data.
    """
    # Bot-specific UI
    slack_bot_token = st.text_input(
        "Slack Bot Token", value=existing_data.get("slack_bot_token", "")
    )
    slack_app_token = st.text_input(
        "Slack App Token", value=existing_data.get("slack_app_token", "")
    )

    # Fetch and display all available companion IDs
    companion_ids = admin_app.get_entity_ids(EntityType.COMPANION)
    companion_id_index = None
    if "CompanionId" in existing_data:
        existing_companion_id = existing_data["CompanionId"]
        if existing_companion_id in companion_ids:
            companion_id_index = companion_ids.index(existing_companion_id)
    selected_companion_id = st.selectbox(
        "Select Companion ID", options=companion_ids, index=companion_id_index
    )

    # User Identification Settings UI
    user_identification_enabled = st.checkbox(
        "User Identification Enabled",
        value=existing_data.get("user_identification", {}).get("enabled", False),
        help="사용자 식별 기능을 활성화하려면 이 옵션을 선택하세요. 이 기능은 사용자의 고유 식별 정보를 사용하여 각 사용자의 메시지를 구분합니다.",
    )

    # Proactive Messaging Settings
    proactive_settings = existing_data.get("proactive_messaging", {})
    proactive_enabled = st.checkbox(
        "Proactive Messaging Enabled",
        value=proactive_settings.get("enabled", False),
    )

    # Determine if proactive settings should be editable
    proactive_editable = proactive_enabled

    # Proactive Messaging Settings UI
    with st.expander("Proactive Messaging Settings", expanded=proactive_enabled):
        proactive_interval_days = st.number_input(
            "Interval Days",
            min_value=0.0,
            max_value=365.0,  # Maximum limit, adjust as needed
            value=proactive_settings.get("interval_days", 0.0),
            step=0.0001,
            format="%.4f",
            key="proactive_interval_days",
            disabled=not proactive_editable,
        )
        proactive_system_prompt = st.text_area(
            "System Prompt",
            value=proactive_settings.get("system_prompt", ""),
            key="proactive_system_prompt",
            disabled=not proactive_editable,
        )
        proactive_slack_channel = st.text_input(
            "Slack Channel",
            value=proactive_settings.get("slack_channel", ""),
            key="proactive_slack_channel",
            disabled=not proactive_editable,
        )
        proactive_temperature = st.number_input(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=proactive_settings.get("temperature", 1.0),
            key="proactive_temperature",
            disabled=not proactive_editable,
        )

    # Preparing Bot data for upload
    entity_data = {
        "CompanionId": selected_companion_id,
        "slack_bot_token": slack_bot_token,
        "slack_app_token": slack_app_token,
        "proactive_messaging": {
            "enabled": proactive_enabled,
            "interval_days": proactive_interval_days,
            "system_prompt": proactive_system_prompt,
            "slack_channel": proactive_slack_channel,
            "temperature": proactive_temperature,
        }
        if proactive_enabled
        else {"enabled": False},
        "user_identification": {"enabled": user_identification_enabled},
    }

    return entity_data


def handle_companion_settings(existing_data: dict[str, Any]) -> dict[str, Any]:
    """
    Handles the UI components specific to the Companion entity.

    Args:
        existing_data: The existing data of the companion entity.


    Returns:
        The updated companion entity data.
    """
    # Companion-specific UI
    # Core Settings: Chat Model, System Prompt, Temperature
    chat_models = ["gpt-4", "gpt-4-1106-preview", "gpt-3.5-turbo"]
    existing_model = existing_data.get("chat_model", "gpt-4")
    if existing_model not in chat_models:
        chat_models.append(existing_model)
    chat_model_index = chat_models.index(existing_model)
    chat_model = st.selectbox("Chat Model", chat_models, index=chat_model_index)

    # System prompt
    system_prompt = st.text_area(
        "System Prompt", value=existing_data.get("system_prompt", "")
    )

    # Temperature
    temperature = st.number_input(
        "Temperature",
        min_value=0.0,
        max_value=2.0,
        value=existing_data.get("temperature", 1.0),
    )

    # Prequency Penalty
    tooltip_text = "빈도 페널티 설정: 양수값을 설정하면 텍스트의 반복을 줄이고, 다양성을 증가시킵니다."
    frequency_penalty = st.number_input(
        "Frequency Penalty",
        min_value=-2.0,
        max_value=2.0,
        value=existing_data.get("frequency_penalty", 0.0),
        help=tooltip_text,
    )

    vision_enabled = existing_data.get("vision_enabled", False)
    st.checkbox("Vision Enabled", value=vision_enabled, disabled=True)

    # Prefix Messages
    existing_prefix_messages_str = format_prefix_messages_for_display(
        existing_data.get("prefix_messages_content", [])
    )
    prefix_messages_str = st.text_area(
        "Edit Prefix Messages (CSV format: Role,Content)",
        value=existing_prefix_messages_str,
    )

    # Preparing Companion data for upload
    edited_prefix_messages = (
        load_prefix_messages_from_csv(prefix_messages_str)
        if prefix_messages_str
        else []
    )
    entity_data = {
        "chat_model": chat_model,
        "system_prompt": system_prompt,
        "temperature": temperature,
        "frequency_penalty": frequency_penalty,
        "vision_enabled": vision_enabled,
        "prefix_messages_content": edited_prefix_messages,
    }

    return entity_data


def main():
    """
    The main function to run the Streamlit admin app.

    This function sets up the Streamlit interface and handles user interactions
    for administering chatbot configurations.
    """
    st.title("Admin")

    admin_app = StreamlitAdminApp()

    tab1, tab2, tab3 = st.tabs(["Companions", "Bots", "Proactive Tasks"])

    with tab1:
        handle_entity_tab(admin_app, EntityType.COMPANION)

    with tab2:
        handle_entity_tab(admin_app, EntityType.BOT)

    with tab3:
        handle_proactive_task_tab(admin_app)


if __name__ == "__main__":
    main()
