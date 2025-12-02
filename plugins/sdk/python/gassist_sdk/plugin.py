"""
Main Plugin class for G-Assist Plugin SDK (V2 Only).

Provides a simple decorator-based API for building plugins:

    from gassist_sdk import Plugin

    plugin = Plugin("my-plugin", version="1.0.0")

    @plugin.command("search")
    def search(query: str):
        plugin.stream("Searching...")
        return {"results": [...]}

    plugin.run()
"""

import logging
import sys
import os
import traceback
import signal
from typing import Any, Callable, Dict, List, Optional, TypeVar
from dataclasses import dataclass, field

from .protocol import Protocol, ProtocolError, ConnectionClosed
from .types import (
    Context, SystemInfo,
    JsonRpcRequest, JsonRpcResponse, JsonRpcNotification,
    ErrorCode, LogLevel
)

# Set up logging - use temp directory to avoid permission issues
def _get_log_path():
    """Get a writable log file path."""
    import tempfile
    # Try current working directory first (plugin's directory)
    cwd_log = os.path.join(os.getcwd(), "gassist_sdk.log")
    try:
        with open(cwd_log, "a") as f:
            pass
        return cwd_log
    except (PermissionError, OSError):
        pass
    # Fall back to temp directory
    return os.path.join(tempfile.gettempdir(), "gassist_sdk.log")

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_get_log_path(), mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("gassist_sdk.plugin")

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class CommandInfo:
    """Information about a registered command."""
    name: str
    handler: Callable
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)


def command(name: str = None, description: str = None):
    """
    Decorator to register a function as a plugin command.
    
    Usage:
        @plugin.command("search", description="Search the web")
        def search(query: str):
            return {"results": [...]}
    """
    def decorator(func: F) -> F:
        func._gassist_command = True
        func._gassist_name = name or func.__name__
        func._gassist_description = description or func.__doc__ or ""
        return func
    return decorator


class Plugin:
    """
    Main plugin class using Protocol V2 (JSON-RPC 2.0).
    
    Features:
    - Automatic ping/pong handling (no threading required!)
    - Streaming support via stream() method
    - Decorator-based command registration
    - Automatic error handling and reporting
    """
    
    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: str = ""
    ):
        """
        Initialize the plugin.
        
        Args:
            name: Plugin name (should match manifest.json)
            version: Plugin version
            description: Plugin description
        """
        self.name = name
        self.version = version
        self.description = description
        
        # Protocol (V2 only)
        self._protocol: Protocol = None
        
        # Command registry
        self._commands: Dict[str, CommandInfo] = {}
        
        # State
        self._running = False
        self._current_request_id: Optional[int] = None
        self._initialized = False
        self._keep_session = False
        
        # Register shutdown handler
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        
        logger.info(f"Plugin '{name}' v{version} initialized (Protocol V2)")
    
    def command(self, name: str = None, description: str = None):
        """
        Decorator to register a command handler.
        
        Usage:
            @plugin.command("search_web")
            def search_web(query: str):
                return {"results": [...]}
        """
        def decorator(func: F) -> F:
            cmd_name = name or func.__name__
            cmd_desc = description or func.__doc__ or ""
            
            self._commands[cmd_name] = CommandInfo(
                name=cmd_name,
                handler=func,
                description=cmd_desc
            )
            
            logger.debug(f"Registered command: {cmd_name}")
            return func
        return decorator
    
    def stream(self, data: str):
        """
        Send streaming data to the engine.
        
        Use this during command execution to send partial results:
            
            @plugin.command("search")
            def search(query: str):
                plugin.stream("Searching...")
                results = do_search(query)
                plugin.stream("Found results!")
                return results
        """
        if self._current_request_id is None:
            logger.warning("stream() called outside of command execution")
            return
        
        notification = JsonRpcNotification(
            method="stream",
            params={
                "request_id": self._current_request_id,
                "data": data
            }
        )
        self._protocol.send_notification(notification)
    
    def log(self, message: str, level: LogLevel = LogLevel.INFO):
        """Send a log message to the engine (for debugging)."""
        notification = JsonRpcNotification(
            method="log",
            params={
                "level": level.value,
                "message": message
            }
        )
        self._protocol.send_notification(notification)
    
    def set_keep_session(self, keep: bool):
        """
        Set whether to keep the session open after command completion.
        
        If True, the plugin enters "passthrough" mode where user input
        is sent directly to the plugin.
        """
        self._keep_session = keep
    
    def run(self):
        """
        Start the plugin main loop.
        
        This method blocks until the plugin is shut down.
        """
        logger.info(f"Starting plugin '{self.name}' (Protocol V2)")
        
        # Initialize V2 protocol
        self._protocol = Protocol()
        self._running = True
        
        try:
            self._run_loop()
        except ConnectionClosed:
            logger.info("Connection closed, shutting down")
        except Exception as e:
            logger.error(f"Unexpected error: {e}\n{traceback.format_exc()}")
        finally:
            self._running = False
            logger.info(f"Plugin '{self.name}' stopped")
    
    def _run_loop(self):
        """Main loop for V2 (JSON-RPC) protocol."""
        while self._running:
            try:
                request = self._protocol.read_message()
                if request is None:
                    break
                
                self._handle_request(request)
                
            except ConnectionClosed:
                break
            except ProtocolError as e:
                logger.error(f"Protocol error: {e}")
                # Continue trying to read next message
            except Exception as e:
                logger.error(f"Error processing message: {e}\n{traceback.format_exc()}")
    
    def _handle_request(self, request: JsonRpcRequest):
        """Handle a JSON-RPC request."""
        method = request.method
        params = request.params or {}
        
        logger.debug(f"Received request: {method} (id={request.id})")
        
        # Route to handler
        if method == "ping":
            self._handle_ping(request)
        elif method == "initialize":
            self._handle_initialize(request)
        elif method == "execute":
            self._handle_execute(request)
        elif method == "input":
            self._handle_input(request)
        elif method == "shutdown":
            self._handle_shutdown(request)
        else:
            # Unknown method
            if not request.is_notification():
                response = JsonRpcResponse.make_error(
                    request.id,
                    ErrorCode.METHOD_NOT_FOUND,
                    f"Unknown method: {method}"
                )
                self._protocol.send_response(response)
    
    def _handle_ping(self, request: JsonRpcRequest):
        """Handle ping request - respond immediately."""
        timestamp = request.params.get("timestamp") if request.params else None
        
        response = JsonRpcResponse.success(
            request.id,
            {"timestamp": timestamp}
        )
        self._protocol.send_response(response)
        logger.debug("Responded to ping")
    
    def _handle_initialize(self, request: JsonRpcRequest):
        """Handle initialization request."""
        params = request.params or {}
        
        logger.info(f"Initializing with engine version: {params.get('engine_version', 'unknown')}")
        
        # Debug: Log command info before building response
        commands_list = []
        for cmd in self._commands.values():
            logger.debug(f"Command '{cmd.name}': description type={type(cmd.description).__name__}, value={repr(cmd.description)[:100]}")
            commands_list.append({
                "name": cmd.name,
                "description": str(cmd.description) if cmd.description else ""  # Force to string
            })
        
        response = JsonRpcResponse.success(
            request.id,
            {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "protocol_version": "2.0",
                "commands": commands_list
            }
        )
        
        if not self._protocol.send_response(response):
            logger.error("CRITICAL: Failed to send initialize response!")
            return
            
        self._initialized = True
        logger.info("Initialization complete - response sent successfully")
    
    def _handle_execute(self, request: JsonRpcRequest):
        """Handle command execution request."""
        params = request.params or {}
        function_name = params.get("function", "")
        arguments = params.get("arguments", {})
        context_data = params.get("context", [])
        system_info_data = params.get("system_info", "")
        
        logger.info(f"Executing command: {function_name}")
        
        # Find command handler
        cmd = self._commands.get(function_name)
        if cmd is None:
            response = JsonRpcResponse.make_error(
                request.id,
                ErrorCode.METHOD_NOT_FOUND,
                f"Unknown command: {function_name}"
            )
            self._protocol.send_response(response)
            return
        
        # Set current request ID for streaming
        self._current_request_id = request.id
        self._keep_session = False
        
        try:
            # Build context objects
            context = Context.from_list(context_data)
            system_info = SystemInfo.from_string(system_info_data)
            
            # Call handler with appropriate arguments
            result = self._call_handler(cmd.handler, arguments, context, system_info)
            
            # Send completion
            self._send_complete(request.id, True, result, self._keep_session)
            
        except Exception as e:
            logger.error(f"Command execution error: {e}\n{traceback.format_exc()}")
            self._send_error(request.id, ErrorCode.PLUGIN_ERROR, str(e))
        finally:
            self._current_request_id = None
    
    def _handle_input(self, request: JsonRpcRequest):
        """Handle user input during passthrough mode."""
        params = request.params or {}
        content = params.get("content", "")
        
        logger.info(f"Received user input: {content[:50]}...")
        
        # First, send acknowledgment
        ack_response = JsonRpcResponse.success(
            request.id,
            {"acknowledged": True}
        )
        self._protocol.send_response(ack_response)
        
        # Set request ID for streaming
        self._current_request_id = request.id
        self._keep_session = False
        
        try:
            # Find a handler for user input
            handler = self._commands.get("on_input")
            
            if handler:
                result = self._call_handler(handler.handler, {"content": content}, None, None)
                self._send_complete(request.id, True, result, self._keep_session)
            else:
                # No handler - just echo back
                self._send_complete(request.id, True, f"Received: {content}", False)
                
        except Exception as e:
            logger.error(f"Input handling error: {e}\n{traceback.format_exc()}")
            self._send_error(request.id, ErrorCode.PLUGIN_ERROR, str(e))
        finally:
            self._current_request_id = None
    
    def _handle_shutdown(self, request: JsonRpcRequest):
        """Handle shutdown request."""
        logger.info("Received shutdown request")
        self._running = False
    
    def _call_handler(
        self,
        handler: Callable,
        arguments: Dict[str, Any],
        context: Optional[Context],
        system_info: Optional[SystemInfo]
    ) -> Any:
        """Call a command handler with appropriate arguments."""
        import inspect
        sig = inspect.signature(handler)
        
        # Build kwargs based on what the handler accepts
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name in arguments:
                kwargs[param_name] = arguments[param_name]
            elif param_name == "context" and context is not None:
                kwargs[param_name] = context
            elif param_name == "system_info" and system_info is not None:
                kwargs[param_name] = system_info
        
        return handler(**kwargs)
    
    def _send_complete(self, request_id: int, success: bool, data: Any, keep_session: bool):
        """Send completion notification."""
        notification = JsonRpcNotification(
            method="complete",
            params={
                "request_id": request_id,
                "success": success,
                "data": data,
                "keep_session": keep_session
            }
        )
        self._protocol.send_notification(notification)
    
    def _send_error(self, request_id: int, code: int, message: str):
        """Send error notification."""
        notification = JsonRpcNotification(
            method="error",
            params={
                "request_id": request_id,
                "code": code,
                "message": message
            }
        )
        self._protocol.send_notification(notification)
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down")
        self._running = False
