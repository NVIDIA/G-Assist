"""
Type definitions for G-Assist Plugin SDK.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from enum import Enum


class LogLevel(Enum):
    """Log levels for plugin logging."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class Message:
    """A message in the conversation context."""
    role: str  # "user", "assistant", "system"
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "Message":
        return cls(role=data.get("role", "user"), content=data.get("content", ""))


@dataclass
class Context:
    """Conversation context passed to commands."""
    messages: List[Message] = field(default_factory=list)
    
    @classmethod
    def from_list(cls, data: List[Dict[str, str]]) -> "Context":
        return cls(messages=[Message.from_dict(m) for m in data])
    
    def last_user_message(self) -> Optional[str]:
        """Get the last user message content."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg.content
        return None
    
    def to_list(self) -> List[Dict[str, str]]:
        return [m.to_dict() for m in self.messages]


@dataclass
class SystemInfo:
    """System information passed to commands."""
    raw: str = ""
    
    @classmethod
    def from_string(cls, data: str) -> "SystemInfo":
        return cls(raw=data)


@dataclass
class CommandResult:
    """Result from a command execution."""
    success: bool = True
    data: Any = None
    keep_session: bool = False
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "keep_session": self.keep_session,
        }
        if self.data is not None:
            result["data"] = self.data
        if self.error_message:
            result["error_message"] = self.error_message
        return result


# JSON-RPC Types

@dataclass
class JsonRpcRequest:
    """JSON-RPC 2.0 Request."""
    method: str
    id: Optional[Union[int, str]] = None
    params: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"
    
    def to_dict(self) -> Dict[str, Any]:
        msg = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            msg["id"] = self.id
        if self.params is not None:
            msg["params"] = self.params
        return msg
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JsonRpcRequest":
        return cls(
            method=data.get("method", ""),
            id=data.get("id"),
            params=data.get("params"),
            jsonrpc=data.get("jsonrpc", "2.0")
        )
    
    def is_notification(self) -> bool:
        """Notifications have no id field."""
        return self.id is None


@dataclass
class JsonRpcResponse:
    """JSON-RPC 2.0 Response."""
    id: Union[int, str]
    result: Optional[Any] = None
    error_data: Optional[Dict[str, Any]] = None  # Renamed to avoid name conflicts
    jsonrpc: str = "2.0"
    
    def to_dict(self) -> Dict[str, Any]:
        msg = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error_data is not None:
            msg["error"] = self.error_data  # JSON key is still "error"
        else:
            msg["result"] = self.result
        return msg
    
    @classmethod
    def success(cls, id: Union[int, str], result: Any) -> "JsonRpcResponse":
        return cls(id=id, result=result, error_data=None)
    
    @classmethod
    def make_error(cls, id: Union[int, str], code: int, message: str, data: Any = None) -> "JsonRpcResponse":
        """Create an error response."""
        error_obj = {"code": code, "message": message}
        if data is not None:
            error_obj["data"] = data
        return cls(id=id, error_data=error_obj, result=None)


@dataclass
class JsonRpcNotification:
    """JSON-RPC 2.0 Notification (no id, no response expected)."""
    method: str
    params: Optional[Dict[str, Any]] = None
    jsonrpc: str = "2.0"
    
    def to_dict(self) -> Dict[str, Any]:
        msg = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            msg["params"] = self.params
        return msg


# Error codes (JSON-RPC 2.0 + custom)
class ErrorCode:
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom error codes
    PLUGIN_ERROR = -1
    TIMEOUT = -2
    RATE_LIMITED = -3

