from pydantic import BaseModel


class UserIdentificationSettings(BaseModel):
    enabled: bool = False
