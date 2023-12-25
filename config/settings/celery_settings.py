# pylint: disable=consider-alternative-union-syntax
from typing import Optional

from pydantic_settings import BaseSettings


class CelerySettings(BaseSettings):
    broker_url: Optional[str] = "pyamqp://guest:guest@localhost//"
