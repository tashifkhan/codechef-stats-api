from typing import Any, Dict, Optional

from pydantic import BaseModel

from models.canonical.constants import PLATFORM


def make_envelope(
    username: str,
    data: Any,
    legacy: Optional[Any] = None,
    cached: bool = False,
    status: str = "success",
    message: str = "retrieved",
    platform: str = PLATFORM,
) -> Dict[str, Any]:
    envelope: Dict[str, Any] = {}
    if legacy is not None:
        envelope.update(legacy.model_dump() if isinstance(legacy, BaseModel) else dict(legacy))
    envelope.setdefault("status", status)
    envelope.setdefault("message", message)
    envelope["platform"] = platform
    envelope["username"] = username
    envelope["cached"] = cached
    envelope["data"] = data.model_dump() if isinstance(data, BaseModel) else data
    return envelope
