# pylint: disable=consider-alternative-union-syntax
from typing import Optional

from pydantic_settings import BaseSettings


class APISettings(BaseSettings):
    openai_api_key: Optional[str] = None
    openai_organization: Optional[str] = None
    slack_bot_user_id: Optional[str] = None
    slack_bot_token: Optional[str] = None
    slack_app_token: Optional[str] = None
