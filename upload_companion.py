from __future__ import annotations

import argparse
import configparser
import csv
import json
import os
from typing import Any

from google.cloud import firestore
from prompt_toolkit import prompt
from slack_bolt import App


def get_bot_user_id(slack_bot_token: str) -> str:
    """
    Retrieve the Bot User ID using Slack Bolt with the given Slack bot token.

    Args:
        slack_bot_token (str): The Slack bot token.

    Returns:
        str: The Bot User ID.
    """
    app = App(token=slack_bot_token)
    response = app.client.auth_test()
    return response["user_id"]


def load_prefix_messages_from_csv(file_path: str) -> list[dict[str, str]]:
    """
    Load prefix messages from a CSV file and return them as a list of dictionaries.

    This function reads a CSV file containing messages with their roles and
    content. It then converts these messages into a format suitable for storing
    directly in Firestore.

    Each message object in the CSV file should have a role ('AI', 'Human', 'System')
    and content. These roles are converted to their corresponding roles in the Firestore.

    Args:
        file_path (str): The path to the CSV file containing the prefix messages.

    Returns:
        list[dict[str, str]]: A list of dictionaries representing the messages.

    Raises:
        FileNotFoundError: If the CSV file is not found at the specified path.
        ValueError: If an invalid role is encountered in the CSV file.
    """

    # Define the mapping of CSV roles to Firestore roles
    role_mappings = {"AI": "assistant", "Human": "user", "System": "system"}

    messages: list[dict[str, str]] = []

    with open(file_path, mode="r", encoding="utf-8") as file:
        reader = csv.reader(file)
        for row in reader:
            role, content = row
            if role not in role_mappings:
                raise ValueError(
                    f"Invalid role '{role}' in CSV file. Must be one of {list(role_mappings.keys())}."
                )

            firestore_role = role_mappings[role]
            messages.append({"role": firestore_role, "content": content})

    return messages


def upload_companion_data(
    db: firestore.Client, companion_id: str, companion_data: dict
):
    """
    Upload companion data to Firestore.

    Args:
        db (firestore.Client): Firestore client instance.
        companion_id (str): The ID of the companion.
        companion_data (dict): The companion data to upload.
    """
    companions_ref = db.collection("Companions")
    companions_ref.document(companion_id).set(companion_data)


def upload_bot_data(db: firestore.Client, bot_id: str, bot_data: dict):
    """
    Upload bot data to Firestore.

    Args:
        db (firestore.Client): Firestore client instance.
        bot_id (str): The ID of the bot.
        bot_data (dict): The bot data to upload.
    """
    bots_ref = db.collection("Bots")
    bots_ref.document(bot_id).set(bot_data)


def upload_proactive_messaging_settings(
    db: firestore.Client, bot_id: str, proactive_messaging_config: dict
):
    """
    Uploads proactive messaging settings to Firestore for the specified bot.

    Args:
        db (firestore.Client): Firestore client instance.
        bot_id (str): The ID of the bot to which the settings will be uploaded.
        proactive_messaging_config (dict): The proactive messaging configuration.

    This function uploads the provided proactive messaging settings to the Firestore
    document corresponding to the given bot ID. It ensures that the bot's behavior
    in sending proactive messages is configured according to these settings.
    """
    bot_ref = db.collection("Bots").document(bot_id)
    bot_ref.set({"proactive_messaging": proactive_messaging_config}, merge=True)


def document_exists(db: firestore.Client, collection: str, document_id: str) -> bool:
    """
    Check if a document exists in the specified Firestore collection.

    Args:
        db (firestore.Client): Firestore client instance.
        collection (str): The name of the collection.
        document_id (str): The ID of the document to check.

    Returns:
        bool: True if the document exists, False otherwise.
    """
    doc_ref = db.collection(collection).document(document_id)
    return doc_ref.get().exists


def main():
    parser = argparse.ArgumentParser(
        description="Upload companion and bot data to Firestore."
    )
    parser.add_argument(
        "ini_file", type=str, help="Path to the INI configuration file."
    )
    args = parser.parse_args()

    # Parse INI file
    config = configparser.ConfigParser()
    config.read(args.ini_file)

    # Extract the base name without extension for default Companion ID
    companion_id_default = os.path.splitext(os.path.basename(args.ini_file))[0]

    # Initialize Firestore client with the specified project ID
    db = firestore.Client(project="alola-discord-bots")

    # Get default Bot User ID
    bot_id_default = ""
    if "slack_bot_token" in config["api"]:
        bot_id_default = get_bot_user_id(config["api"]["slack_bot_token"])

    # Prompt for Companion ID and Bot ID
    companion_id = prompt("Enter Companion ID: ", default=companion_id_default)
    bot_id = prompt("Enter Slack Bot ID (Optional): ", default=bot_id_default)

    # Add 'prefix_messages_content' if 'message_file' is specified
    prefix_messages = None
    if "message_file" in config["settings"]:
        prefix_messages = load_prefix_messages_from_csv(
            config["settings"]["message_file"]
        )

    # Prepare companion data
    companion_data = {
        "chat_model": config.get("settings", "chat_model", fallback=None),
        "system_prompt": config.get("settings", "system_prompt", fallback=None),
        "temperature": config.getfloat("settings", "temperature", fallback=None),
        "vision_enabled": config.getboolean(
            "settings", "vision_enabled", fallback=None
        ),
        "prefix_messages_content": prefix_messages,
    }

    # Remove fields that are None
    companion_data = {k: v for k, v in companion_data.items() if v is not None}

    # Upload companion data
    upload_companion_data(db, companion_id, companion_data)
    if document_exists(db, "Companions", companion_id):
        print(f"Companion data for '{companion_id}' uploaded successfully.")
        for key, value in companion_data.items():
            if key == "prefix_messages_content":
                assert isinstance(value, list)
                print(f"  - {key}: {len(value)} messages uploaded")
            else:
                print(f"  - {key}: {value}")
    else:
        print(f"Failed to upload companion data for '{companion_id}'.")

    # Upload bot data if Bot ID is provided
    if bot_id:
        bot_data: dict[str, Any] = {
            "CompanionId": companion_id,
            "slack_bot_token": config["api"]["slack_bot_token"],
            "slack_app_token": config["api"]["slack_app_token"],
        }

        # Extract proactive messaging settings from INI file
        proactive_enabled = config.getboolean(
            "proactive_messaging", "enabled", fallback=None
        )
        proactive_messaging_config: dict[str, Any] = {"enabled": proactive_enabled}

        if proactive_enabled:
            proactive_messaging_config["interval_days"] = config.getfloat(
                "proactive_messaging", "interval_days"
            )
            proactive_messaging_config["system_prompt"] = config.get(
                "proactive_messaging", "system_prompt"
            )
            proactive_messaging_config["slack_channel"] = config.get(
                "proactive_messaging", "slack_channel"
            )

            # Add temperature setting if present
            if config.has_option("proactive_messaging", "temperature"):
                proactive_messaging_config["temperature"] = config.getfloat(
                    "proactive_messaging", "temperature"
                )

            bot_data["proactive_messaging"] = proactive_messaging_config

        upload_bot_data(db, bot_id, bot_data)

        if document_exists(db, "Bots", bot_id):
            print(f"Bot data for '{bot_id}' uploaded successfully.")
            print(json.dumps(bot_data, indent=4, ensure_ascii=False))
        else:
            print(f"Failed to upload bot data for '{bot_id}'.")

    print("Data upload completed successfully.")


if __name__ == "__main__":
    main()
