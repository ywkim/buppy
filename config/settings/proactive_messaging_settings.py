# pylint: disable=consider-alternative-union-syntax
from typing import Optional

from pydantic import BaseModel, root_validator


class ProactiveMessagingSettings(BaseModel):
    enabled: bool = False
    interval_days: Optional[float] = None
    system_prompt: Optional[str] = None
    slack_channel: Optional[str] = None
    temperature: float = 1.0

    @root_validator(skip_on_failure=True)
    def check_required_fields(cls, values):  # pylint: disable=no-self-argument
        if values.get("enabled", False):
            if "interval_days" not in values:
                raise ValueError("interval_days is required when enabled is True")
            if "system_prompt" not in values:
                raise ValueError("system_prompt is required when enabled is True")
            if "slack_channel" not in values:
                raise ValueError("slack_channel is required when enabled is True")
        return values
