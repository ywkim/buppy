from __future__ import annotations
from typing import Type
from pydantic import BaseModel
from configparser import ConfigParser
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def load_settings_from_ini_section(config_file: str, section: str, model: Type[T]) -> T:
    """
    Loads settings from a specified section of an INI file into a Pydantic model.

    Args:
        config_file (str): The path to the INI configuration file.
        section (str): The section in the INI file to load settings from.
        model (Type[T]): The Pydantic model class to which settings will be loaded.

    Returns:
        T: An instance of the specified Pydantic model class with settings loaded.

    Raises:
        KeyError: If the specified section is not found in the INI file.
    """
    parser = ConfigParser()
    parser.read(config_file)

    if section not in parser:
        raise KeyError(f"Section '{section}' not found in the INI file.")

    # Converting the settings in the section to a dictionary
    settings = {key: eval(value) for key, value in parser.items(section)}

    # Creating an instance of the Pydantic model with the settings
    return model(**settings)
