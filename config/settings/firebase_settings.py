from pydantic import BaseModel

class FirebaseSettings(BaseModel):
    enabled: bool = False
