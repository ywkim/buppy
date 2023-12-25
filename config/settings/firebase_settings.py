from pydantic import BaseSettings

class FirebaseSettings(BaseSettings):
    enabled: bool = False

    class Config:
        env_prefix = "FIREBASE_"
