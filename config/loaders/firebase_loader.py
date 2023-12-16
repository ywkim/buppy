from __future__ import annotations

from google.cloud import firestore
from typing import Type

def load_settings_from_firestore(
    document: firestore.DocumentSnapshot,
    settings_class: Type
) -> Type:
    """
    Loads settings from a Firestore document snapshot into a Pydantic model.

    Args:
        document (firestore.DocumentSnapshot): Firestore document snapshot.
        settings_class (Type): The Pydantic model class for the settings.

    Returns:
        An instance of the settings class with values loaded from Firestore.
    """
    settings_data = document.to_dict() or {}
    return settings_class(**settings_data)
