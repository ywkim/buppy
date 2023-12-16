from pydantic_settings import BaseSettings


class CoreSettings(BaseSettings):
    chat_model: str = "gpt-4"
    system_prompt: str = "You are a helpful assistant."
    temperature: float = 0.0
    vision_enabled: bool = False
