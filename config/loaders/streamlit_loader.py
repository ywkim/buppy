import streamlit as st
from typing import Type
from pydantic import BaseModel

def load_settings_from_streamlit_secrets(settings_class: Type[BaseModel]) -> BaseModel:
    return settings_class.parse_obj(st.secrets)
