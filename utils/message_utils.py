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
