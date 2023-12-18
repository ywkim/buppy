from __future__ import annotations

from configparser import ConfigParser
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def load_settings_from_ini_section(config_file: str, section: str, model: type[T]) -> T:
    """
    Loads settings from a specified section of an INI file into a Pydantic model.
    If the section does not exist, returns an instance of the model with default values.

    Args:
        config_file (str): The path to the INI configuration file.
        section (str): The section in the INI file to load settings from.
        model (type[T]): The Pydantic model class to which settings will be loaded.

    Returns:
        T: An instance of the specified Pydantic model class with settings loaded.
    """
    parser = ConfigParser()
    parser.read(config_file)

    if section not in parser:
        return model()

    # Convert the settings in the section to a dictionary
    settings = dict(parser.items(section))

    # Create an instance of the Pydantic model with the settings
    return model(**settings)
