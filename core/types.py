"""Shared application types."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class UserContext:
    user_id: str
    email: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatContext:
    user_id: str
    chat_id: Optional[str] = None
    mode: str = "chat"


@dataclass
class ToolResult:
    ok: bool
    content: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class APIErrorPayload:
    code: str
    message: str
    details: Optional[Any] = None