"""
Protocol V2 Implementation for Plugin Communication

Protocol V2 uses JSON-RPC 2.0 with length-prefixed framing:
- 4-byte big-endian length header
- UTF-8 JSON payload

This mirrors the C++ PluginProtocolV2.h implementation.
"""

import json
import struct
from typing import Optional, Any, Dict, Union
from dataclasses import dataclass, field
from enum import IntEnum


# ============================================================================
# Protocol Constants (matching C++ PluginProtocolV2.h)
# ============================================================================

# Maximum message size (10MB)
MAX_MESSAGE_SIZE = 10 * 1024 * 1024

# Ping timeout (plugin must respond within this time)
PING_TIMEOUT_MS = 1000

# Input acknowledgment timeout
INPUT_ACK_TIMEOUT_MS = 2000

# Command execution timeout
EXECUTE_TIMEOUT_MS = 30000

# Ping interval (how often engine sends ping)
PING_INTERVAL_MS = 2000

# Heartbeat timeout (5 seconds)
HEARTBEAT_TIMEOUT_MS = 5000


# ============================================================================
# JSON-RPC Error Codes
# ============================================================================

class JsonRpcErrorCode(IntEnum):
    """JSON-RPC 2.0 error codes"""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    
    # Custom error codes
    PLUGIN_ERROR = -1
    TIMEOUT = -2
    RATE_LIMITED = -3


class ProtocolError(Exception):
    """Protocol-related errors"""
    pass


# ============================================================================
# Message Types
# ============================================================================

@dataclass
class JsonRpcRequest:
    """
    JSON-RPC 2.0 Request (engine -> plugin)
    
    Used for sending commands to plugins that expect responses.
    """
    method: str
    id: Optional[int] = None  # None for notifications
    params: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary"""
        msg = {
            "jsonrpc": "2.0",
            "method": self.method
        }
        if self.id is not None:
            msg["id"] = self.id
        if self.params:
            msg["params"] = self.params
        return msg
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())
    
    def is_notification(self) -> bool:
        """Check if this is a notification (no response expected)"""
        return self.id is None


@dataclass
class JsonRpcResponse:
    """
    JSON-RPC 2.0 Response (plugin -> engine)
    
    Contains either a result or an error.
    """
    id: int
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None
    
    def is_error(self) -> bool:
        """Check if this response is an error"""
        return self.error is not None
    
    @classmethod
    def from_dict(cls, msg: Dict[str, Any]) -> 'JsonRpcResponse':
        """Parse from dictionary"""
        return cls(
            id=msg.get("id", 0),
            result=msg.get("result"),
            error=msg.get("error")
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'JsonRpcResponse':
        """Parse from JSON string"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class JsonRpcNotification:
    """
    JSON-RPC 2.0 Notification (plugin -> engine, no response expected)
    
    Used for streaming data, completion signals, errors, and logs.
    """
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, msg: Dict[str, Any]) -> 'JsonRpcNotification':
        """Parse from dictionary"""
        return cls(
            method=msg.get("method", ""),
            params=msg.get("params", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> 'JsonRpcNotification':
        """Parse from JSON string"""
        return cls.from_dict(json.loads(json_str))


@dataclass
class JsonRpcError:
    """
    JSON-RPC 2.0 Error object
    """
    code: int
    message: str
    data: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "code": self.code,
            "message": self.message
        }
        if self.data is not None:
            result["data"] = self.data
        return result


# ============================================================================
# Message Framing
# ============================================================================

def frame_message(message: Union[Dict[str, Any], str]) -> bytes:
    """
    Encode a message with length-prefix framing.
    
    Format: 4-byte big-endian length header + UTF-8 JSON payload
    
    Args:
        message: JSON message (dict or string)
        
    Returns:
        Framed message as bytes
    """
    if isinstance(message, dict):
        payload = json.dumps(message).encode('utf-8')
    else:
        payload = message.encode('utf-8')
    
    length = len(payload)
    
    if length > MAX_MESSAGE_SIZE:
        raise ProtocolError(f"Message too large: {length} bytes (max: {MAX_MESSAGE_SIZE})")
    
    # Big-endian 4-byte length header
    header = struct.pack('>I', length)
    
    return header + payload


def decode_length(header: bytes) -> int:
    """
    Decode length from 4-byte header.
    
    Args:
        header: 4-byte header buffer
        
    Returns:
        Message length in bytes
    """
    if len(header) < 4:
        raise ProtocolError(f"Header too short: {len(header)} bytes (expected 4)")
    
    return struct.unpack('>I', header[:4])[0]


def parse_message(data: bytes) -> Dict[str, Any]:
    """
    Parse a JSON message from bytes.
    
    Args:
        data: UTF-8 encoded JSON
        
    Returns:
        Parsed JSON as dictionary
    """
    try:
        return json.loads(data.decode('utf-8'))
    except json.JSONDecodeError as e:
        raise ProtocolError(f"Invalid JSON: {e}")
    except UnicodeDecodeError as e:
        raise ProtocolError(f"Invalid UTF-8: {e}")


def is_valid_jsonrpc(msg: Dict[str, Any]) -> bool:
    """
    Validate JSON-RPC 2.0 message format.
    
    Args:
        msg: Parsed JSON message
        
    Returns:
        True if valid JSON-RPC 2.0 format
    """
    return msg.get("jsonrpc") == "2.0"


def classify_message(msg: Dict[str, Any]) -> str:
    """
    Classify a JSON-RPC message type.
    
    Args:
        msg: Parsed JSON message
        
    Returns:
        One of: "request", "response", "notification", "unknown"
    """
    if not is_valid_jsonrpc(msg):
        return "unknown"
    
    has_id = "id" in msg
    has_method = "method" in msg
    has_result_or_error = "result" in msg or "error" in msg
    
    if has_id and has_result_or_error and not has_method:
        return "response"
    elif has_method and has_id:
        return "request"
    elif has_method and not has_id:
        return "notification"
    else:
        return "unknown"


# ============================================================================
# Request Builders
# ============================================================================

def build_initialize_request(request_id: int, engine_version: str = "1.0.0") -> JsonRpcRequest:
    """Build an initialize request"""
    return JsonRpcRequest(
        method="initialize",
        id=request_id,
        params={
            "protocol_version": "2.0",
            "engine_version": engine_version
        }
    )


def build_execute_request(
    request_id: int,
    function: str,
    arguments: Dict[str, Any],
    context: Optional[list] = None,
    system_info: Optional[str] = None
) -> JsonRpcRequest:
    """Build an execute request"""
    params = {
        "function": function,
        "arguments": arguments
    }
    if context is not None:
        params["context"] = context
    if system_info is not None:
        params["system_info"] = system_info
    
    return JsonRpcRequest(
        method="execute",
        id=request_id,
        params=params
    )


def build_shutdown_request(request_id: int) -> JsonRpcRequest:
    """Build a shutdown request"""
    return JsonRpcRequest(
        method="shutdown",
        id=request_id,
        params={}
    )


def build_ping_request(request_id: int, timestamp: Optional[int] = None) -> JsonRpcRequest:
    """Build a ping request"""
    import time
    return JsonRpcRequest(
        method="ping",
        id=request_id,
        params={"timestamp": timestamp or int(time.time() * 1000)}
    )


def build_input_request(request_id: int, content: str, timestamp: Optional[int] = None) -> JsonRpcRequest:
    """Build a user input request"""
    import time
    return JsonRpcRequest(
        method="input",
        id=request_id,
        params={
            "content": content,
            "timestamp": timestamp or int(time.time() * 1000)
        }
    )

