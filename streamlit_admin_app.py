from __future__ import annotations

import csv
import logging
from io import StringIO
from typing import Any

import streamlit as st

from celery_tasks.proactive_messaging_task import (
    cancel_current_proactive_message_task,
    schedule_proactive_message_task,
)
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
        self.celery_app = self.app_config.initialize_celery_app('streamlit_admin_app')


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



def proactive_task_panel(admin_app: StreamlitAdminApp, proactive_settings, bot_id: str):
    """Renders the proactive task management panel in Streamlit."""
    st.subheader("Proactive Messaging Task Management")

    # Retrieve current task info
    task_id = proactive_settings.get("current_task_id")
    scheduled_time = proactive_settings.get("last_scheduled")

    if task_id:
        st.text(f"Scheduled Time: {scheduled_time}")
        if st.button("Cancel Current Task"):
            cancel_current_proactive_message_task(
                bot_id,
                admin_app.celery_app,
                admin_app.db
            )
            st.success("Current task cancelled.")
    else:
        st.write("No task currently scheduled.")
        if st.button("Schedule New Task"):
            schedule_proactive_message_task(
                proactive_settings,
                bot_id,
                admin_app.celery_app,
                admin_app.db
            )
            st.success("New task scheduled.")

def handle_entity_tab(admin_app: StreamlitAdminApp, entity_type: EntityType):
    """
    Handles the UI and logic for a specific entity tab (bot or companion).

    Args:
        admin_app: The instance of StreamlitAdminApp.
        entity_type: The type of entity (BOT or COMPANION).
    """
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
                value=proactive_settings.get("interval_days", 0.0),
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

            proactive_task_panel(admin_app, proactive_settings, entity_id_to_upload)

    elif entity_type == EntityType.COMPANION:
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

        edited_prefix_messages = (
            load_prefix_messages_from_csv(prefix_messages_str)
            if prefix_messages_str
            else []
        )

    # Entity data upload logic
    if entity_id_to_upload and st.button(f"Upload {entity_type.name.title()} Data"):
        if entity_type == EntityType.BOT:
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
            }

        elif entity_type == EntityType.COMPANION:
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
                "vision_enabled": vision_enabled,
                "prefix_messages_content": edited_prefix_messages,
            }

        # Uploading data to Firestore
        admin_app.upload_entity_data(entity_type, entity_id_to_upload, entity_data)
        st.success(
            f"{entity_type.name.capitalize()} '{entity_id_to_upload}' data updated successfully."
        )

def main():
    """
    The main function to run the Streamlit admin app.

    This function sets up the Streamlit interface and handles user interactions
    for administering chatbot configurations.
    """
    st.title("Admin")

    admin_app = StreamlitAdminApp()

    tab1, tab2 = st.tabs(["Companions", "Bots"])

    with tab1:
        handle_entity_tab(admin_app, EntityType.COMPANION)

    with tab2:
        handle_entity_tab(admin_app, EntityType.BOT)

if __name__ == "__main__":
    main()
