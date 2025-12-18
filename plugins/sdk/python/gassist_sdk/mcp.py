"""
MCP (Model Context Protocol) support for G-Assist Plugin SDK.

Implements the MCP specification for connecting to MCP servers:
https://modelcontextprotocol.io/specification/2025-06-18

Features:
- Full MCP lifecycle: initialize, initialized notification, shutdown
- Transport layer: HTTP (with SSE support) and stdio
- Server features: Tools, Resources, Prompts
- Session management with automatic refresh
- Dynamic function discovery and registration

Example:
    from gassist_sdk import MCPPlugin
    from gassist_sdk.mcp import MCPClient, FunctionDef, sanitize_name

    plugin = MCPPlugin(
        name="stream-deck",
        version="1.0.0",
        mcp_url="http://localhost:9090/mcp"
    )

    @plugin.discoverer
    def discover_actions(mcp: MCPClient) -> List[FunctionDef]:
        result = mcp.call_tool("get_executable_actions")
        return [
            FunctionDef(
                name=sanitize_name(f"streamdeck_{a['title']}"),
                description=f"Execute '{a['title']}'",
                executor=lambda aid=a['id']: mcp.call_tool("execute_action", {"id": aid})
            )
            for a in result.get("actions", [])
        ]

    plugin.run()  # Auto-discovers at startup
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union

logger = logging.getLogger("gassist_sdk.mcp")

# Try to import requests for HTTP transport
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    requests = None
    HAS_REQUESTS = False
    logger.warning("requests library not available - HTTP MCP transport disabled")


# =============================================================================
# MCP PROTOCOL CONSTANTS
# =============================================================================

MCP_PROTOCOL_VERSION = "2024-11-05"


# =============================================================================
# MCP ERRORS
# =============================================================================

class MCPError(Exception):
    """Raised when an MCP operation fails."""
    
    def __init__(self, message: str, code: int = -1, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


# =============================================================================
# FUNCTION DEFINITION (for dynamic discovery)
# =============================================================================

def sanitize_name(name: str) -> str:
    """
    Convert a name to a valid function identifier.
    
    Examples:
        "Open Webpage" -> "open_webpage"
        "Play Audio (Test)" -> "play_audio_test"
    """
    clean = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower())
    clean = clean.strip('_')
    clean = re.sub(r'_+', '_', clean)
    return clean


@dataclass
class FunctionDef:
    """
    Definition of a dynamically discovered function.
    
    Attributes:
        name: Function name (sanitized to valid identifier)
        description: Human-readable description for LLM
        tags: List of tags for function matching
        executor: Callable that executes the function (returns result)
        properties: Parameter definitions (for manifest)
        required: Required parameters
    """
    name: str
    description: str
    tags: List[str] = field(default_factory=list)
    executor: Callable[[], Any] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    required: List[str] = field(default_factory=list)
    
    def to_manifest_function(self) -> Dict[str, Any]:
        """Convert to manifest function format."""
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "properties": self.properties,
            "required": self.required
        }


# =============================================================================
# FUNCTION REGISTRY
# =============================================================================

class FunctionRegistry:
    """
    Registry for dynamically discovered functions.
    
    Handles caching to disk and manifest updates.
    """
    
    def __init__(self, plugin_name: str, plugin_dir: str = None, source_dir: str = None):
        """
        Initialize function registry.
        
        Args:
            plugin_name: Plugin name (for cache file naming)
            plugin_dir: Plugin directory (defaults to PROGRAMDATA location)
            source_dir: Source directory where plugin.py lives (for local manifest)
        """
        self.plugin_name = plugin_name
        self.source_dir = source_dir
        
        if plugin_dir:
            self.plugin_dir = plugin_dir
        else:
            self.plugin_dir = os.path.join(
                os.environ.get("PROGRAMDATA", "."),
                "NVIDIA Corporation", "nvtopps", "rise", "plugins", plugin_name
            )
        
        self.cache_file = os.path.join(self.plugin_dir, "discovered_functions.json")
        self.manifest_file = os.path.join(self.plugin_dir, "manifest.json")
        
        self._functions: Dict[str, FunctionDef] = {}
        self._base_functions: List[Dict[str, Any]] = []
        self._mcp_config: Optional[Dict[str, Any]] = None
    
    def set_base_functions(self, functions: List[Dict[str, Any]]):
        """Set the base (static) functions that are always available."""
        self._base_functions = functions
    
    def set_mcp_config(self, config: Dict[str, Any]):
        """Set MCP configuration for manifest."""
        self._mcp_config = config
    
    def register(self, func: FunctionDef):
        """Register a discovered function."""
        self._functions[func.name] = func
        logger.debug(f"Registered function: {func.name}")
    
    def register_all(self, functions: List[FunctionDef]):
        """Register multiple discovered functions."""
        for func in functions:
            self.register(func)
    
    def get(self, name: str) -> Optional[FunctionDef]:
        """Get a registered function by name."""
        return self._functions.get(name)
    
    def all_functions(self) -> List[FunctionDef]:
        """Get all registered functions."""
        return list(self._functions.values())
    
    def save_cache(self):
        """Save discovered functions to cache file."""
        cache = {}
        for name, func in self._functions.items():
            cache[name] = {
                "name": func.name,
                "description": func.description,
                "tags": func.tags,
                "properties": func.properties,
                "required": func.required
            }
        
        try:
            os.makedirs(self.plugin_dir, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(cache, f, indent=2)
            logger.info(f"Saved {len(cache)} functions to cache")
        except Exception as e:
            logger.error(f"Failed to save function cache: {e}")
    
    def load_cache(self) -> Dict[str, Dict[str, Any]]:
        """Load functions from cache file."""
        try:
            if os.path.isfile(self.cache_file):
                with open(self.cache_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load function cache: {e}")
        return {}
    
    def update_manifest(self, version: str = "1.0.0", description: str = ""):
        """Update manifest with discovered functions."""
        functions = list(self._base_functions)
        
        for func in self._functions.values():
            functions.append(func.to_manifest_function())
        
        manifest = {
            "manifestVersion": 1,
            "name": self.plugin_name,
            "version": version,
            "description": description or f"Plugin with {len(self._functions)} discovered functions",
            "executable": "plugin.py",
            "persistent": True,
            "protocol_version": "2.0",
            "functions": functions
        }
        
        # Add MCP configuration if set
        if self._mcp_config:
            manifest["mcp"] = self._mcp_config
        
        # Write to deploy directory
        try:
            os.makedirs(self.plugin_dir, exist_ok=True)
            with open(self.manifest_file, "w") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Updated manifest at {self.manifest_file} with {len(functions)} functions")
        except Exception as e:
            logger.error(f"Failed to update manifest: {e}")
        
        # Also write to source directory if available
        if self.source_dir:
            try:
                source_manifest = os.path.join(self.source_dir, "manifest.json")
                with open(source_manifest, "w") as f:
                    json.dump(manifest, f, indent=2)
                logger.info(f"Updated source manifest at {source_manifest}")
            except Exception as e:
                logger.debug(f"Could not update source manifest: {e}")


# =============================================================================
# MCP TRANSPORT LAYER
# =============================================================================

class MCPTransport(ABC):
    """
    Abstract base class for MCP transports.
    
    MCP supports multiple transports per the spec:
    - stdio: For subprocess communication
    - HTTP with SSE: For network communication
    """
    
    @abstractmethod
    def send(self, message: Dict[str, Any]) -> None:
        """Send a JSON-RPC message."""
        pass
    
    @abstractmethod
    def receive(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        """Receive a JSON-RPC message."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the transport."""
        pass
    
    @property
    @abstractmethod
    def is_open(self) -> bool:
        """Check if transport is open."""
        pass


class StdioTransport(MCPTransport):
    """
    Stdio transport for MCP communication with subprocess servers.
    
    Per MCP spec: Uses newline-delimited JSON messages over stdin/stdout.
    """
    
    def __init__(self, command: List[str], env: Dict[str, str] = None):
        """
        Initialize stdio transport.
        
        Args:
            command: Command to spawn MCP server (e.g., ["node", "server.js"])
            env: Environment variables for the subprocess
        """
        self._command = command
        self._env = {**os.environ, **(env or {})}
        self._process: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """Start the subprocess."""
        try:
            self._process = subprocess.Popen(
                self._command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
                bufsize=0
            )
            logger.info(f"Started MCP server: {' '.join(self._command)}")
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    def send(self, message: Dict[str, Any]) -> None:
        if not self._process or not self._process.stdin:
            raise MCPError("Transport not open")
        
        with self._lock:
            try:
                data = json.dumps(message) + "\n"
                self._process.stdin.write(data.encode("utf-8"))
                self._process.stdin.flush()
            except Exception as e:
                raise MCPError(f"Send failed: {e}")
    
    def receive(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        if not self._process or not self._process.stdout:
            raise MCPError("Transport not open")
        
        try:
            line = self._process.stdout.readline()
            if not line:
                return None
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise MCPError(f"Invalid JSON from server: {e}")
        except Exception as e:
            raise MCPError(f"Receive failed: {e}")
    
    def close(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
    
    @property
    def is_open(self) -> bool:
        return self._process is not None and self._process.poll() is None


class HTTPTransport(MCPTransport):
    """
    HTTP transport for MCP communication.
    
    Per MCP spec:
    - POST requests for client-to-server messages
    - Session management via mcp-session-id header
    - Optional SSE for server-to-client messages
    """
    
    def __init__(
        self,
        url: str,
        timeout: float = 30.0,
        session_timeout: float = 300.0
    ):
        """
        Initialize HTTP transport.
        
        Args:
            url: MCP server endpoint URL
            timeout: Request timeout in seconds
            session_timeout: Session idle timeout in seconds
        """
        if not HAS_REQUESTS:
            raise MCPError("HTTP transport requires 'requests' library")
        
        self._url = url
        self._timeout = timeout
        self._session_timeout = session_timeout
        self._session_id: Optional[str] = None
        self._session_last_used: float = 0.0
        self._closed = False
        self._lock = threading.Lock()
        self._pending_responses: Dict[Union[int, str], Dict[str, Any]] = {}
    
    def send(self, message: Dict[str, Any]) -> None:
        """Send a message and store response for retrieval."""
        if self._closed:
            raise MCPError("Transport is closed")
        
        with self._lock:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"
            }
            
            if self._session_id:
                headers["mcp-session-id"] = self._session_id
            
            try:
                response = requests.post(
                    self._url,
                    headers=headers,
                    json=message,
                    timeout=self._timeout
                )
                
                # Capture session ID
                if "mcp-session-id" in response.headers:
                    self._session_id = response.headers["mcp-session-id"]
                
                self._session_last_used = time.time()
                
                # Handle HTTP errors
                if response.status_code in (400, 401, 403):
                    self._session_id = None
                    raise MCPError(
                        f"Session error: HTTP {response.status_code}",
                        code=response.status_code
                    )
                
                response.raise_for_status()
                
                # Store response for receive()
                msg_id = message.get("id")
                if msg_id is not None:
                    self._pending_responses[msg_id] = response.json()
                    
            except requests.exceptions.ConnectionError:
                raise MCPError(f"Cannot connect to {self._url}")
            except requests.exceptions.Timeout:
                raise MCPError(f"Request timed out after {self._timeout}s")
            except requests.exceptions.HTTPError as e:
                raise MCPError(f"HTTP error: {e}")
    
    def receive(self, timeout: float = None) -> Optional[Dict[str, Any]]:
        """Receive a pending response."""
        with self._lock:
            if self._pending_responses:
                msg_id = next(iter(self._pending_responses))
                return self._pending_responses.pop(msg_id)
        return None
    
    def send_and_receive(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request and return the response (synchronous)."""
        self.send(message)
        
        msg_id = message.get("id")
        if msg_id is not None:
            with self._lock:
                if msg_id in self._pending_responses:
                    return self._pending_responses.pop(msg_id)
        
        raise MCPError("No response received")
    
    def close(self) -> None:
        self._closed = True
        self._session_id = None
        self._pending_responses.clear()
    
    @property
    def is_open(self) -> bool:
        return not self._closed
    
    @property
    def session_id(self) -> Optional[str]:
        return self._session_id
    
    @property
    def is_session_stale(self) -> bool:
        if not self._session_id:
            return True
        idle = time.time() - self._session_last_used
        return idle > self._session_timeout
    
    def refresh_session(self) -> None:
        """Clear session to force re-initialization."""
        self._session_id = None
        self._session_last_used = 0.0


# =============================================================================
# MCP CAPABILITIES
# =============================================================================

@dataclass
class MCPCapabilities:
    """MCP server/client capabilities."""
    tools: bool = False
    resources: bool = False
    prompts: bool = False
    sampling: bool = False
    roots: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPCapabilities":
        return cls(
            tools="tools" in data,
            resources="resources" in data,
            prompts="prompts" in data,
            sampling="sampling" in data,
            roots="roots" in data
        )


@dataclass
class MCPServerInfo:
    """Information about connected MCP server."""
    name: str = ""
    version: str = ""
    capabilities: MCPCapabilities = field(default_factory=MCPCapabilities)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPServerInfo":
        return cls(
            name=data.get("serverInfo", {}).get("name", ""),
            version=data.get("serverInfo", {}).get("version", ""),
            capabilities=MCPCapabilities.from_dict(data.get("capabilities", {}))
        )


# =============================================================================
# MCP CLIENT
# =============================================================================

class MCPClient:
    """
    MCP (Model Context Protocol) Client.
    
    Implements the client side of MCP specification:
    https://modelcontextprotocol.io/specification/2025-06-18
    
    Lifecycle:
    - initialize: Handshake with server, exchange capabilities
    - initialized: Notification after successful init
    - shutdown: Clean disconnection
    
    Server Features:
    - tools/list, tools/call: Invoke server-side tools
    - resources/list, resources/read: Access server resources
    - prompts/list, prompts/get: Use server prompts
    
    Example:
        mcp = MCPClient(url="http://localhost:9090/mcp")
        
        if mcp.connect():
            tools = mcp.list_tools()
            result = mcp.call_tool("my_tool", {"arg": "value"})
            mcp.disconnect()
    """
    
    def __init__(
        self,
        transport: MCPTransport = None,
        # HTTP convenience params
        url: str = None,
        timeout: float = 30.0,
        session_timeout: float = 300.0,
        # Client info
        client_name: str = "G-Assist-Plugin",
        client_version: str = "1.0.0"
    ):
        """
        Initialize MCP client.
        
        Args:
            transport: MCP transport (StdioTransport or HTTPTransport)
            url: HTTP URL (creates HTTPTransport if transport not provided)
            timeout: Request timeout
            session_timeout: Session idle timeout
            client_name: Client name for initialization
            client_version: Client version for initialization
        """
        if transport:
            self._transport = transport
        elif url:
            if not HAS_REQUESTS:
                raise MCPError("HTTP transport requires 'requests' library")
            self._transport = HTTPTransport(url, timeout, session_timeout)
        else:
            raise ValueError("Must provide either transport or url")
        
        self._client_name = client_name
        self._client_version = client_version
        self._server_info: Optional[MCPServerInfo] = None
        self._initialized = False
        self._request_id = 0
        self._lock = threading.Lock()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to MCP server."""
        return self._initialized and self._transport.is_open
    
    @property
    def server_info(self) -> Optional[MCPServerInfo]:
        """Get server info from initialization."""
        return self._server_info
    
    def _next_id(self) -> int:
        """Generate next request ID."""
        with self._lock:
            self._request_id += 1
            return self._request_id
    
    def _send_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a JSON-RPC request and return the result."""
        request = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {}
        }
        
        logger.debug(f"MCP request: {method}")
        
        if isinstance(self._transport, HTTPTransport):
            response = self._transport.send_and_receive(request)
        else:
            self._transport.send(request)
            response = self._transport.receive()
        
        if response is None:
            raise MCPError(f"No response for {method}")
        
        if "error" in response:
            error = response["error"]
            raise MCPError(
                message=error.get("message", str(error)),
                code=error.get("code", -1),
                data=error.get("data")
            )
        
        return response.get("result", {})
    
    def _send_notification(self, method: str, params: Dict[str, Any] = None) -> None:
        """Send a JSON-RPC notification (no response expected)."""
        notification = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        self._transport.send(notification)
    
    # =========================================================================
    # LIFECYCLE
    # =========================================================================
    
    def connect(self, startup_timeout: float = None) -> bool:
        """
        Connect to MCP server and initialize session.
        
        Per MCP spec lifecycle:
        1. Send 'initialize' request with capabilities
        2. Receive server capabilities and info
        3. Send 'notifications/initialized' notification
        
        Args:
            startup_timeout: Optional shorter timeout for startup
        
        Returns:
            True if connected successfully
        """
        # Handle stale session for HTTP transport
        if isinstance(self._transport, HTTPTransport):
            if self._transport.is_session_stale:
                logger.info("Session stale, refreshing...")
                self._transport.refresh_session()
                self._initialized = False
        
        if self._initialized:
            return True
        
        try:
            logger.info("MCP: Initializing connection...")
            
            # Start transport if needed (for stdio)
            if isinstance(self._transport, StdioTransport):
                if not self._transport.is_open:
                    if not self._transport.start():
                        return False
            
            # Send initialize request (per MCP spec)
            result = self._send_request("initialize", {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    # Client capabilities (what we support)
                },
                "clientInfo": {
                    "name": self._client_name,
                    "version": self._client_version
                }
            })
            
            # Parse server info and capabilities
            self._server_info = MCPServerInfo.from_dict(result)
            logger.info(
                f"MCP: Connected to {self._server_info.name} v{self._server_info.version}"
            )
            
            # Send initialized notification (per MCP spec)
            self._send_notification("notifications/initialized")
            
            self._initialized = True
            return True
            
        except MCPError as e:
            logger.error(f"MCP initialization failed: {e}")
            return False
        except Exception as e:
            logger.error(f"MCP connection error: {e}")
            return False
    
    def disconnect(self) -> None:
        """
        Disconnect from MCP server.
        
        Per MCP spec: Send shutdown notification before closing.
        """
        if self._initialized:
            try:
                self._send_notification("notifications/shutdown")
            except Exception:
                pass
        
        self._transport.close()
        self._initialized = False
        self._server_info = None
        logger.info("MCP: Disconnected")
    
    # =========================================================================
    # TOOLS (MCP Server Feature)
    # =========================================================================
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List available tools from the server.
        
        Returns:
            List of tool definitions with name, description, inputSchema
        """
        if not self._ensure_connected():
            return []
        
        result = self._send_request("tools/list")
        return result.get("tools", [])
    
    def call_tool(
        self,
        name: str,
        arguments: Dict[str, Any] = None,
        retry_on_session_error: bool = True
    ) -> Dict[str, Any]:
        """
        Call a tool on the MCP server.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            retry_on_session_error: Retry with fresh session on 400/401/403
        
        Returns:
            Tool result (extracted from content)
        """
        if not self._ensure_connected():
            raise MCPError("Not connected to MCP server")
        
        try:
            result = self._send_request("tools/call", {
                "name": name,
                "arguments": arguments or {}
            })
            
            return self._extract_content(result)
            
        except MCPError as e:
            # Retry on session errors
            if retry_on_session_error and e.code in (400, 401, 403):
                logger.warning(f"Session error, reconnecting: {e}")
                self._initialized = False
                if isinstance(self._transport, HTTPTransport):
                    self._transport.refresh_session()
                if self.connect():
                    return self.call_tool(name, arguments, retry_on_session_error=False)
            raise
    
    # =========================================================================
    # RESOURCES (MCP Server Feature)
    # =========================================================================
    
    def list_resources(self) -> List[Dict[str, Any]]:
        """
        List available resources from the server.
        
        Returns:
            List of resource definitions with uri, name, description
        """
        if not self._ensure_connected():
            return []
        
        if not self._server_info or not self._server_info.capabilities.resources:
            logger.warning("Server does not support resources")
            return []
        
        result = self._send_request("resources/list")
        return result.get("resources", [])
    
    def read_resource(self, uri: str) -> Dict[str, Any]:
        """
        Read a resource by URI.
        
        Args:
            uri: Resource URI
        
        Returns:
            Resource content
        """
        if not self._ensure_connected():
            raise MCPError("Not connected")
        
        result = self._send_request("resources/read", {"uri": uri})
        return self._extract_content(result)
    
    # =========================================================================
    # PROMPTS (MCP Server Feature)
    # =========================================================================
    
    def list_prompts(self) -> List[Dict[str, Any]]:
        """
        List available prompts from the server.
        
        Returns:
            List of prompt definitions
        """
        if not self._ensure_connected():
            return []
        
        if not self._server_info or not self._server_info.capabilities.prompts:
            logger.warning("Server does not support prompts")
            return []
        
        result = self._send_request("prompts/list")
        return result.get("prompts", [])
    
    def get_prompt(self, name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get a prompt by name.
        
        Args:
            name: Prompt name
            arguments: Prompt arguments
        
        Returns:
            Prompt content
        """
        if not self._ensure_connected():
            raise MCPError("Not connected")
        
        result = self._send_request("prompts/get", {
            "name": name,
            "arguments": arguments or {}
        })
        return result
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _ensure_connected(self) -> bool:
        """Ensure connected, reconnecting if needed."""
        if not self.is_connected:
            return self.connect()
        return True
    
    def _extract_content(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured content from MCP response."""
        if not isinstance(result, dict):
            return {"raw": result}
        
        # Try structuredContent first (preferred)
        if "structuredContent" in result:
            return result["structuredContent"]
        
        # Try content array
        if "content" in result:
            for item in result.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"text": text}
        
        return result


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # MCP Client
    "MCPClient",
    "MCPError",
    "MCPCapabilities",
    "MCPServerInfo",
    "MCP_PROTOCOL_VERSION",
    # Transports
    "MCPTransport",
    "StdioTransport",
    "HTTPTransport",
    "HAS_REQUESTS",
    # Function Discovery
    "FunctionDef",
    "FunctionRegistry",
    "sanitize_name",
]

