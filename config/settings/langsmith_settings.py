from pydantic import BaseModel

class LangSmithSettings(BaseModel):
    enabled: bool = False
    api_key: str
