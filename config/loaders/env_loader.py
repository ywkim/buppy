import os
from typing import Type
from pydantic import BaseModel

def load_settings_from_env(settings_class: Type[BaseModel]) -> BaseModel:
    return settings_class.parse_obj(os.environ)
