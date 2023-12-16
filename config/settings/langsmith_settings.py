# pylint: disable=consider-alternative-union-syntax
from typing import Optional

from pydantic import BaseModel, root_validator


class LangSmithSettings(BaseModel):
    enabled: bool = False
    api_key: Optional[str] = None

    @root_validator(skip_on_failure=True)
    def check_api_key(cls, values):  # pylint: disable=no-self-argument
        if values.get("enabled") and not values.get("api_key"):
            raise ValueError("API key is required when LangSmith is enabled.")
        return values
