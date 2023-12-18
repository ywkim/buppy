from __future__ import annotations

from configparser import ConfigParser
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def load_settings_from_ini_section(
    settings_class: type[T], config_file: str, section: str
) -> T:
    """
    Loads settings from a specified section of an INI file into a Pydantic model.
    If the section does not exist, returns an instance of the model with default values.

    Args:
        settings_class (type[T]): The Pydantic model class to which settings will be loaded.
        config_file (str): The path to the INI configuration file.
        section (str): The section in the INI file to load settings from.

    Returns:
        T: An instance of the specified Pydantic model class with settings loaded.
    """
    parser = ConfigParser()
    parser.read(config_file)

    if section not in parser:
        return settings_class()

    settings = dict(parser.items(section))
    return settings_class(**settings)
