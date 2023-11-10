import argparse
import configparser
import os
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
    return response['user_id']

def load_prefix_messages_from_csv(file_path: str) -> str:
    """
    Load prefix messages from a CSV file and return them as a JSON string.

    This function reads a CSV file containing messages with their roles and
    content. It then converts these messages into a format suitable for storing
    in Firestore, specifically as a JSON string of message objects.

    Each message object in the CSV file should have a role ('AI', 'Human', 'System')
    and content. These roles are converted to their corresponding roles ('assistant',
    'user', 'system') in the Firestore format.

    Args:
        file_path (str): The path to the CSV file containing the prefix messages.

    Returns:
        str: A JSON string representing the list of messages.

    Raises:
        FileNotFoundError: If the CSV file is not found at the specified path.
        ValueError: If an invalid role is encountered in the CSV file.
    """

    # Role mappings from CSV to Firestore format
    role_mappings = {
        'AI': 'assistant',
        'Human': 'user',
        'System': 'system'
    }

    try:
        # Read the CSV file and convert each row into a message object
        with open(file_path, mode='r', encoding='utf-8') as file:
            reader = csv.reader(file)
            messages: List[Dict[str, str]] = []

            for row in reader:
                role, content = row
                if role not in role_mappings:
                    raise ValueError(f"Invalid role '{role}' in CSV file. Must be one of {list(role_mappings.keys())}.")

                firestore_role = role_mappings[role]
                messages.append({'role': firestore_role, 'content': content})

        # Convert the list of message objects to a JSON string
        return json.dumps(messages)

    except FileNotFoundError:
        raise FileNotFoundError(f"The file at path '{file_path}' was not found.")

def upload_companion_data(db: firestore.Client, companion_id: str, companion_data: dict):
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

def main():
    parser = argparse.ArgumentParser(description="Upload companion and bot data to Firestore.")
    parser.add_argument('ini_file', type=str, help='Path to the INI configuration file.')
    args = parser.parse_args()

    # Parse INI file
    config = configparser.ConfigParser()
    config.read(args.ini_file)

    # Extract the base name without extension for default Companion ID
    companion_id_default = os.path.splitext(os.path.basename(args.ini_file))[0]

    # Initialize Firestore client with the specified project ID
    db = firestore.Client(project='alola-discord-bots')

    # Get default Bot User ID
    bot_id_default = None
    if 'slack_bot_token' in config['api']:
        bot_id_default = get_bot_user_id(config['api']['slack_bot_token'])

    # Prompt for Companion ID and Bot ID
    companion_id = prompt("Enter Companion ID: ", default=companion_id_default)
    bot_id = prompt("Enter Slack Bot ID (Optional): ", default=bot_id_default)

    # Prepare companion data
    companion_data = {
        "chat_model": config.get('settings', 'chat_model', fallback=None),
        "system_prompt": config.get('settings', 'system_prompt', fallback=None),
        "temperature": config.getfloat('settings', 'temperature', fallback=None),
    }
    # Add 'prefix_messages_content' if 'message_file' is specified
    if 'message_file' in config['settings']:
        companion_data["prefix_messages_content"] = load_prefix_messages_from_csv(config['settings']['message_file'])

    # Remove fields that are None
    companion_data = {k: v for k, v in companion_data.items() if v is not None}

    # Upload companion data
    upload_companion_data(db, companion_id, companion_data)

    # Upload bot data if Bot ID is provided
    if bot_id:
        bot_data = {"CompanionId": companion_id}
        upload_bot_data(db, bot_id, bot_data)

    print("Data upload completed successfully.")

if __name__ == "__main__":
    main()
