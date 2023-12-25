from pydantic_settings import BaseSettings


class FirebaseSettings(BaseSettings):
    enabled: bool = False

    class Config:
        env_prefix = "FIREBASE_"
