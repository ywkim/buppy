import os
from typing import Type, TypeVar
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

def load_settings_from_env(model: Type[T]) -> T:
    return model(**os.environ)

def load_settings_from_file(file_path: str, model: Type[BaseModel]) -> BaseModel:
    with open(file_path, 'r') as file:
        data = json.load(file)
    return model.parse_obj(data)

# 비슷한 방식으로 Streamlit secrets 및 Firebase Firestore로부터 로드하는 함수 구현
def load_settings_from_firestore(document: firestore.DocumentSnapshot):
    # Firestore에서 설정을 로드하고 Pydantic 모델에 적용하는 로직
    ...
