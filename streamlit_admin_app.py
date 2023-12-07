from __future__ import annotations

import streamlit as st
from typing import List, Dict, Optional
import csv
from config.streamlit_config import StreamlitAppConfig

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
        self.db = self.app_config._initialize_firebase_client()

    def get_companion_data(self, companion_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieves companion data from Firestore.

        Args:
            companion_id (str): The unique identifier of the companion.

        Returns:
            Optional[Dict[str, str]]: The data of the companion if found, otherwise None.
        """
        companion_ref = self.db.collection("Companions").document(companion_id)
        companion = companion_ref.get()
        if companion.exists:
            return companion.to_dict()
        return None

    def upload_companion_data(self, companion_id: str, companion_data: Dict[str, str]) -> None:
        """
        Uploads companion data to Firestore.

        Args:
            companion_id (str): The unique identifier of the companion.
            companion_data (Dict[str, str]): The companion data to upload.
        """
        companions_ref = self.db.collection("Companions")
        companions_ref.document(companion_id).set(companion_data)
        st.success(f"Companion '{companion_id}' data successfully uploaded.")

    def get_companion_ids(self) -> List[str]:
        """
        Retrieves all companion IDs from Firestore.

        Returns:
            List[str]: A list of companion IDs.
        """
        companions_ref = self.db.collection("Companions")
        companions = companions_ref.stream()
        return [companion.id for companion in companions]

    def load_prefix_messages_from_csv(self, uploaded_file) -> List[Dict[str, str]]:
        """
        Loads prefix messages from an uploaded CSV file and returns them as a list of dictionaries.

        Args:
            uploaded_file: The file-like object uploaded through Streamlit's file_uploader.

        Returns:
            List[Dict[str, str]]: A list of dictionaries representing the messages.

        The CSV file should contain messages with their roles ('AI', 'Human', 'System')
        and content. These roles are mapped to Firestore roles ('assistant', 'user', 'system').
        """
        role_mappings = {"AI": "assistant", "Human": "user", "System": "system"}

        messages: list[dict[str, str]] = []

        reader = csv.reader(uploaded_file)
        for row in reader:
            role, content = row
            if role not in role_mappings:
                raise ValueError(
                    f"Invalid role '{role}' in CSV file. Must be one of {list(role_mappings.keys())}."
                )
            firestore_role = role_mappings[role]
            messages.append({"role": firestore_role, "content": content})

        return messages


def main():
    """
    The main function to run the Streamlit admin app.

    This function sets up the Streamlit interface and handles user interactions
    for administering chatbot configurations.
    """
    st.title("Admin")

    admin_app = StreamlitAdminApp()

    chat_models = ["gpt-4", "gpt-4-1106-preview", "gpt-3.5-turbo"]

    # Companion ID selection and existing data pre-fill logic
    companion_ids = admin_app.get_companion_ids()
    new_companion_option = "Add New Companion"
    selected_companion_id = st.selectbox("Select Companion ID", [new_companion_option] + companion_ids)

    # Pre-fill Existing Companion Data
    existing_data = {}
    if selected_companion_id != new_companion_option:
        existing_data = admin_app.get_companion_data(selected_companion_id) or {}

    # Adjust the chat_models list based on existing data
    existing_model = existing_data.get("chat_model", "gpt-4")
    if existing_model not in chat_models:
        chat_models.append(existing_model)
    chat_model_index = chat_models.index(existing_model)

    chat_model = st.selectbox("Chat Model", chat_models, index=chat_model_index)

    system_prompt = st.text_area("System Prompt", value=existing_data.get("system_prompt", ""))
    temperature = st.number_input("Temperature", min_value=0.0, max_value=2.0, step=0.01,
                                  value=existing_data.get("temperature", 1.0))

    # CSV File Uploader for Prefix Messages
    uploaded_file = st.file_uploader("Upload CSV for Prefix Messages", type="csv")
    prefix_messages_content = []
    if uploaded_file is not None:
        prefix_messages_content = admin_app.load_prefix_messages_from_csv(uploaded_file)

    # Companion data upload logic
    if st.button("Upload Data"):
        companion_data = {
            "chat_model": chat_model,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "vision_enabled": False,
            "prefix_messages_content": prefix_messages_content
        }
        companion_id_to_upload = selected_companion_id if selected_companion_id != new_companion_option else st.text_input("Enter New Companion ID")
        if companion_id_to_upload:
            admin_app.upload_companion_data(companion_id_to_upload, companion_data)

if __name__ == "__main__":
    main()
