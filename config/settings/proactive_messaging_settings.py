# pylint: disable=consider-alternative-union-syntax
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, root_validator, validator

class ProactiveMessagingSettings(BaseModel):
    enabled: bool = False
    interval_days: Optional[float] = None
    system_prompt: Optional[str] = None
    slack_channel: Optional[str] = None
    temperature: float = 1.0
    current_task_id: Optional[str] = None
    last_scheduled: Optional[datetime] = None

    @root_validator(skip_on_failure=True)
    def check_required_fields(cls, values):  # pylint: disable=no-self-argument
        if values.get("enabled", False):
            required_fields = ["interval_days", "system_prompt", "slack_channel"]
            for field in required_fields:
                if field not in values or values[field] is None:
                    raise ValueError(f"{field} is required when enabled is True")
        return values

    @validator('last_scheduled', pre=True)
    def parse_last_scheduled(cls, value):  # pylint: disable=no-self-argument
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value
