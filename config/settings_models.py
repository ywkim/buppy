from pydantic import BaseModel, Field

class GeneralSettings(BaseModel):
    chat_model: str = Field(default="gpt-4")
    system_prompt: str = Field(default="You are a helpful assistant.")
    temperature: float = Field(default=0)
    vision_enabled: bool = Field(default=False)

class FirebaseSettings(BaseModel):
    enabled: bool = Field(default=False)

class ProactiveMessagingSettings(BaseModel):
    enabled: bool = Field(default=False)
    temperature: float = Field(default=1)
