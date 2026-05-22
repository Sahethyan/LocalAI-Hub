import json
from typing import Any


def format_sse(event: str, data: str) -> str:
    """Format one Server-Sent Event frame (event + data, blank line terminator)."""
    return f"event: {event}\ndata: {data}\n\n"


def format_sse_json(event: str, payload: Any) -> str:
    return format_sse(event, json.dumps(payload, ensure_ascii=False))
