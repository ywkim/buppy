from langchain.schema import BaseMessage
import json

def custom_serializer(obj: object) -> str:
    """
    Custom serializer for complex objects.

    Args:
        obj (object): Object to serialize.

    Returns:
        str: Serialized string representation of the object.
    """
    if isinstance(obj, BaseMessage):
        return f"{obj.__class__.__name__}({obj})"
    if hasattr(obj, "__str__"):
        return str(obj)
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def create_log_message(message: str, **kwargs) -> str:
    """
    Create a log message in JSON format.

    Args:
        message (str): Log message.
        **kwargs: Additional parameters for the log message.

    Returns:
        str: Log message in JSON format.
    """
    log_entry = {"message": message, **kwargs}
    return json.dumps(
        log_entry, default=custom_serializer, ensure_ascii=False, indent=4
    )
