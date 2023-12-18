from __future__ import annotations

import os
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def load_env_value(env_var: str, default: T, cast_type: Callable[[str], T]) -> T:
    """
    Loads an environment variable, casting it to a specified type, or returns
    a default value if the variable is not set.

    Args:
        env_var (str): The name of the environment variable.
        default (T): The default value to use if the environment variable is not set.
        cast_type (Callable[[str], T]): A function to cast the environment variable's value.

    Returns:
        T: The value of the environment variable cast to the specified type, or the default value.
    """
    value = os.getenv(env_var)
    if value is None:
        return default
    if cast_type is bool:
        return value.lower() in {"true", "1", "yes"}  # type: ignore
    return cast_type(value)
