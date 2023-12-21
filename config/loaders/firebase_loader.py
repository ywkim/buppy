from __future__ import annotations

from typing import Any, TypeVar

from google.cloud import firestore
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def safely_get_field(
    document: firestore.DocumentSnapshot,
    field_path: str,
    default: (Any | None) = None,
) -> Any:
    """
    Safely retrieves a value from the document snapshot of Firestore using a
    field path. Returns a default value if the field path
    does not exist within the document.

    Args:
        document (DocumentSnapshot): The snapshot of the Firestore document.
        field_path (str): A dot-delimited path to a field in the Firestore document.
        default (Optional[Any]): The default value to return if the field doesn't exist.

    Returns:
        Any: The value retrieved from the document for the field path, if it exists;
             otherwise, the default value.
    """
    try:
        value = document.get(field_path)
        if value is None:
            return default
        return value
    except KeyError:
        return default


def load_settings_from_firestore(
    settings_class: type[T], document: firestore.DocumentSnapshot, section: str
) -> T:
    """
    Extracts settings from a Firestore document snapshot and applies them to a given Pydantic model.

    Args:
        settings_class (type[T]): The Pydantic model class to apply settings to.
        document (firestore.DocumentSnapshot): Firestore document snapshot containing settings.
        section (str): Section in the Firestore document containing the relevant settings.

    Returns:
        T: An instance of the specified Pydantic model with applied settings.
    """
    settings_data = safely_get_field(document, section, {})
    return settings_class.parse_obj(settings_data)
