from __future__ import annotations
from typing import Type
from pydantic import BaseModel
from configparser import ConfigParser
import os

def load_settings_from_ini(model: Type[BaseModel], file_path: str) -> BaseModel:
    """
    Load settings from an INI file and return an instance of the specified Pydantic model.

    Args:
        model (Type[BaseModel]): The Pydantic model class to instantiate.
        file_path (str): The path to the INI file.

    Returns:
        BaseModel: An instance of the specified Pydantic model with loaded settings.

    Raises:
        FileNotFoundError: If the specified INI file does not exist.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"INI file {file_path} does not exist.")

    parser = ConfigParser()
    parser.read(file_path)

    # Assuming the INI file has a single section that contains all the settings
    section = parser.sections()[0]
    settings = {key: parser.get(section, key) for key in parser.options(section)}
    return model(**settings)
