from __future__ import annotations

import streamlit as st
from typing import List, Dict
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

def main():
    """
    The main function to run the Streamlit admin app.

    This function sets up the Streamlit interface and handles user interactions
    for administering chatbot configurations.
    """
    st.title("Admin")

    admin_app = StreamlitAdminApp()

    # Select Companion ID
    companion_ids = admin_app.get_companion_ids()
    selected_companion_id = st.selectbox("Select Companion ID", companion_ids)

    # Input fields for companion data
    chat_model = st.text_input("Chat Model")
    system_prompt = st.text_area("System Prompt")
    temperature = st.number_input("Temperature", min_value=0.0, max_value=1.0, step=0.01)

    # Upload button
    if st.button("Upload Data"):
        companion_data = {
            "chat_model": chat_model,
            "system_prompt": system_prompt,
            "temperature": temperature,
        }
        admin_app.upload_companion_data(selected_companion_id, companion_data)

if __name__ == "__main__":
    main()
