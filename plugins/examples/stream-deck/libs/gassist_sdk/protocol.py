"""
Protocol handling for G-Assist Plugin SDK (V2 Only).

Uses JSON-RPC 2.0 with length-prefixed framing:
- 4-byte big-endian length header
- UTF-8 JSON payload
"""

import json
import struct
import sys
import threading
import logging
from typing import Any, Dict, Optional
from ctypes import windll, byref, create_string_buffer, c_ulong

from .types import JsonRpcRequest, JsonRpcResponse, JsonRpcNotification

logger = logging.getLogger("gassist_sdk.protocol")


class ProtocolError(Exception):
    """Raised when a protocol error occurs."""
    pass


class ConnectionClosed(Exception):
    """Raised when the connection is closed."""
    pass


class Protocol:
    """
    Protocol V2 handler using JSON-RPC 2.0 with length-prefixed framing.
    
    Message format:
    [4-byte big-endian length][JSON payload]
    
    On Windows, uses kernel32 ReadFile/WriteFile for reliable pipe I/O.
    """
    
    # Maximum message size (10MB)
    MAX_MESSAGE_SIZE = 10 * 1024 * 1024
    
    def __init__(self):
        self._write_lock = threading.Lock()
        self._read_lock = threading.Lock()
        self._closed = False
        
        # Windows kernel32 for pipe I/O
        if sys.platform == "win32":
            self._kernel32 = windll.kernel32
            self._stdin_handle = self._kernel32.GetStdHandle(-10)  # STD_INPUT_HANDLE
            self._stdout_handle = self._kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        else:
            self._kernel32 = None
    
    def read_message(self) -> Optional[JsonRpcRequest]:
        """
        Read a length-prefixed JSON-RPC message from stdin.
        
        Returns None if connection is closed.
        Raises ProtocolError on invalid data.
        """
        if self._closed:
            raise ConnectionClosed("Connection is closed")
        
        with self._read_lock:
            try:
                # Read 4-byte length header
                header = self._read_bytes(4)
                if header is None or len(header) < 4:
                    raise ConnectionClosed("Connection closed while reading header")
                
                length = struct.unpack(">I", header)[0]
                
                if length > self.MAX_MESSAGE_SIZE:
                    raise ProtocolError(f"Message too large: {length} bytes")
                
                if length == 0:
                    raise ProtocolError("Empty message")
                
                # Read JSON payload
                payload = self._read_bytes(length)
                if payload is None or len(payload) < length:
                    raise ConnectionClosed("Connection closed while reading payload")
                
                # Parse JSON
                try:
                    data = json.loads(payload.decode("utf-8"))
                except json.JSONDecodeError as e:
                    raise ProtocolError(f"Invalid JSON: {e}")
                
                # Validate JSON-RPC
                if not isinstance(data, dict):
                    raise ProtocolError("Message must be a JSON object")
                
                if data.get("jsonrpc") != "2.0":
                    raise ProtocolError("Invalid JSON-RPC version - must be 2.0")
                
                if "method" not in data:
                    raise ProtocolError("Missing 'method' field")
                
                return JsonRpcRequest.from_dict(data)
                
            except ConnectionClosed:
                self._closed = True
                raise
            except ProtocolError:
                raise
            except Exception as e:
                raise ProtocolError(f"Read error: {e}")
    
    def write_message(self, message: Dict[str, Any]) -> bool:
        """
        Write a length-prefixed JSON-RPC message to stdout.
        
        Returns True on success, False on failure.
        """
        if self._closed:
            return False
        
        with self._write_lock:
            try:
                # Ensure JSON-RPC 2.0 format
                if "jsonrpc" not in message:
                    message["jsonrpc"] = "2.0"
                
                # Serialize to JSON - use default handler to catch non-serializable objects
                def safe_serialize(obj):
                    """Handle non-serializable objects by converting to string."""
                    logger.warning(f"NON-SERIALIZABLE OBJECT: type={type(obj).__name__}, repr={repr(obj)[:200]}")
                    return f"<non-serializable: {type(obj).__name__}>"
                
                payload = json.dumps(message, ensure_ascii=False, default=safe_serialize).encode("utf-8")
                
                # DEBUG: Log exactly what we're sending
                logger.info(f"SENDING MESSAGE: {payload[:500]}")
                
                if len(payload) > self.MAX_MESSAGE_SIZE:
                    logger.error(f"Message too large to send: {len(payload)} bytes")
                    return False
                
                # Create length-prefixed message
                header = struct.pack(">I", len(payload))
                full_message = header + payload
                
                # Write to stdout
                return self._write_bytes(full_message)
                
            except Exception as e:
                logger.error(f"Write error: {e}")
                return False
    
    def send_response(self, response: JsonRpcResponse) -> bool:
        """Send a JSON-RPC response."""
        return self.write_message(response.to_dict())
    
    def send_notification(self, notification: JsonRpcNotification) -> bool:
        """Send a JSON-RPC notification (no response expected)."""
        return self.write_message(notification.to_dict())
    
    def close(self):
        """Close the protocol connection."""
        self._closed = True
    
    def _read_bytes(self, count: int) -> Optional[bytes]:
        """Read exactly `count` bytes from stdin."""
        if sys.platform == "win32" and self._kernel32:
            return self._read_bytes_win32(count)
        else:
            return self._read_bytes_posix(count)
    
    def _read_bytes_win32(self, count: int) -> Optional[bytes]:
        """Read bytes using Windows kernel32."""
        result = b""
        remaining = count
        
        while remaining > 0:
            buffer = create_string_buffer(remaining)
            bytes_read = c_ulong(0)
            
            success = self._kernel32.ReadFile(
                self._stdin_handle,
                buffer,
                remaining,
                byref(bytes_read),
                None
            )
            
            if not success or bytes_read.value == 0:
                if len(result) > 0:
                    return result
                return None
            
            result += buffer.raw[:bytes_read.value]
            remaining -= bytes_read.value
        
        return result
    
    def _read_bytes_posix(self, count: int) -> Optional[bytes]:
        """Read bytes using standard I/O."""
        result = b""
        remaining = count
        
        while remaining > 0:
            data = sys.stdin.buffer.read(remaining)
            if not data:
                if len(result) > 0:
                    return result
                return None
            result += data
            remaining -= len(data)
        
        return result
    
    def _write_bytes(self, data: bytes) -> bool:
        """Write bytes to stdout."""
        if sys.platform == "win32" and self._kernel32:
            return self._write_bytes_win32(data)
        else:
            return self._write_bytes_posix(data)
    
    def _write_bytes_win32(self, data: bytes) -> bool:
        """Write bytes using Windows kernel32."""
        bytes_written = c_ulong(0)
        
        success = self._kernel32.WriteFile(
            self._stdout_handle,
            data,
            len(data),
            byref(bytes_written),
            None
        )
        
        if success and bytes_written.value == len(data):
            # Flush the pipe to ensure data is sent immediately
            self._kernel32.FlushFileBuffers(self._stdout_handle)
            return True
        return False
    
    def _write_bytes_posix(self, data: bytes) -> bool:
        """Write bytes using standard I/O."""
        try:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
            return True
        except Exception:
            return False
