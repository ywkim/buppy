from config.settings.core_settings import CoreSettings
from config.settings.firebase_settings import FirebaseSettings
from config.settings.proactive_messaging_settings import ProactiveMessagingSettings
from config.settings.langsmith_settings import LangSmithSettings
import os
from typing import Type
from pydantic import BaseModel

def load_settings_from_env() -> tuple[CoreSettings, FirebaseSettings, ProactiveMessagingSettings, LangSmithSettings]:
    core_settings = CoreSettings(
        chat_model=os.environ.get("CHAT_MODEL", "gpt-4"),
        system_prompt=os.environ.get("SYSTEM_PROMPT", "You are a helpful assistant."),
        temperature=float(os.environ.get("TEMPERATURE", 0.0)),
        vision_enabled=os.environ.get("VISION_ENABLED", "False").lower() in ["true", "1", "yes"]
    )

    firebase_settings = FirebaseSettings(
        enabled=os.environ.get("FIREBASE_ENABLED", "False").lower() in ["true", "1", "yes"]
    )

    proactive_messaging_settings = ProactiveMessagingSettings(
        enabled=os.environ.get("PROACTIVE_MESSAGING_ENABLED", "False").lower() in ["true", "1", "yes"],
        temperature=float(os.environ.get("PROACTIVE_MESSAGING_TEMPERATURE", 1.0)),
        interval_days=float(os.environ.get("PROACTIVE_MESSAGING_INTERVAL_DAYS")),
        system_prompt=os.environ.get("PROACTIVE_MESSAGING_SYSTEM_PROMPT"),
        slack_channel=os.environ.get("PROACTIVE_MESSAGING_SLACK_CHANNEL")
    )

    langsmith_settings = LangSmithSettings(
        enabled=os.environ.get("LANGSMITH_ENABLED", "False").lower() in ["true", "1", "yes"],
        api_key=os.environ.get("LANGSMITH_API_KEY")
    )

    return core_settings, firebase_settings, proactive_messaging_settings, langsmith_settings
