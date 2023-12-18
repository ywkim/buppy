from __future__ import annotations

from typing import TypeVar

import streamlit as st
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def load_settings_from_streamlit_secrets(section: str, settings_class: type[T]):
    """
    Loads settings from a specified section of Streamlit secrets into a Pydantic model.
    If the section does not exist, a default model instance is returned.

    Args:
        section (str): The section in Streamlit secrets to load settings from.
        settings_class (type[T]): The Pydantic model class to which settings will be loaded.

    Returns:
        T: An instance of the specified Pydantic model class with settings loaded.
    """
    section_data = st.secrets.get(section)
    if section_data is None:
        return settings_class()
    return settings_class(**section_data)
