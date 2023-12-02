from __future__ import annotations

import csv

from langchain.schema import AIMessage, BaseMessage, HumanMessage


class InvalidRoleError(Exception):
    """Exception raised when an invalid role is encountered in message processing."""


def load_prefix_messages_from_file(file_path: str) -> list[BaseMessage]:
    """
    Loads prefix messages from a CSV file and returns them as a list of BaseMessage objects.

    Each row in the CSV file should contain two columns: 'role' and 'content',
    where 'role' is either 'Human' or 'AI'.

    Args:
        file_path (str): The path to the CSV file containing the prefix messages.

    Returns:
        List[BaseMessage]: A list of BaseMessage objects representing the prefix messages.

    Raises:
        InvalidRoleError: If the role specified in the CSV file is neither 'AI' nor 'Human'.
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
                    f"Invalid role '{role}' in CSV file. Role must be either 'AI' or 'Human'."
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
