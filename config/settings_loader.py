import os
import json
from typing import Type
from pydantic import parse_obj_as

def load_settings_from_env(model: Type[BaseModel]) -> BaseModel:
    env_vars = {k: v for k, v in os.environ.items() if k.startswith(model.__name__.upper())}
    return model.parse_obj(env_vars)

def load_settings_from_file(file_path: str, model: Type[BaseModel]) -> BaseModel:
    with open(file_path, 'r') as file:
        data = json.load(file)
    return model.parse_obj(data)

# 비슷한 방식으로 Streamlit secrets 및 Firebase Firestore로부터 로드하는 함수 구현
