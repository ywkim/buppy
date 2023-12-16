import json
from typing import Type
from pydantic import BaseModel

def load_settings_from_file(settings_class: Type[BaseModel], file_path: str) -> BaseModel:
    with open(file_path, 'r') as file:
        settings = json.load(file)
    return settings_class.parse_obj(settings)
