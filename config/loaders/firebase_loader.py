from __future__ import annotations

from typing import TypeVar

from google.cloud import firestore
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


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
    settings_data = document.get(section, {})
    return settings_class.parse_obj(settings_data)
