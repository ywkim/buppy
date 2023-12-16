import os
import json
from typing import Type
from pydantic import parse_obj_as

def load_settings_from_env():
    general_settings = GeneralSettings()
    firebase_settings = FirebaseSettings()
    proactive_messaging_settings = ProactiveMessagingSettings()
    return general_settings, firebase_settings, proactive_messaging_settings

def load_settings_from_file(file_path: str, model: Type[BaseModel]) -> BaseModel:
    with open(file_path, 'r') as file:
        data = json.load(file)
    return model.parse_obj(data)

# 비슷한 방식으로 Streamlit secrets 및 Firebase Firestore로부터 로드하는 함수 구현
def load_settings_from_firestore(document: firestore.DocumentSnapshot):
    # Firestore에서 설정을 로드하고 Pydantic 모델에 적용하는 로직
    ...
