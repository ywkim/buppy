from pydantic import BaseModel

class ProactiveMessagingSettings(BaseModel):
    enabled: bool = False
    temperature: float = 1.0
    interval_days: float
    system_prompt: str
    slack_channel: str
