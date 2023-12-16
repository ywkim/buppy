from __future__ import annotations
from typing import Type
from pydantic import BaseModel
from configparser import ConfigParser
from pathlib import Path
from typing import Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

def load_settings_from_ini(model: Type[T], file_path: Path) -> T:
    """Load settings from an INI file into a Pydantic model.

    Args:
        model (Type[BaseModel]): The Pydantic model class.
        file_path (Path): Path to the INI file.

    Returns:
        T: An instance of the specified Pydantic model with loaded settings.
    """
    config = ConfigParser()
    config.read(file_path)

    # Extract settings from the INI file and convert them to the model fields format
    settings = {
        key: config.get(section, key)
        for section in config.sections()
        for key in config[section]
    }
    return model(**settings)
