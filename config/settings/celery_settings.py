from pydantic_settings import BaseSettings


class CelerySettings(BaseSettings):
    broker_url: str = "pyamqp://guest:guest@localhost//"

    class Config:
        env_prefix = "CELERY_"
