"""
Plugin Process Management and Communication

Handles spawning plugin processes, pipe-based IPC, and 
JSON-RPC message exchange with proper heartbeat tracking.

This mirrors the C++ Plugin class implementation.
"""

import os
import sys
import subprocess
import threading
import queue
import time
import json
import logging
from typing import Optional, Dict, Any, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path

from .protocol import (
    ProtocolError,
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcNotification,
    frame_message,
    decode_length,
    parse_message,
    classify_message,
    is_valid_jsonrpc,
    build_initialize_request,
    build_execute_request,
    build_shutdown_request,
    build_ping_request,
    build_input_request,
    MAX_MESSAGE_SIZE,
    HEARTBEAT_TIMEOUT_MS,
    EXECUTE_TIMEOUT_MS,
    PING_INTERVAL_MS,
)
from .manifest import PluginManifest, FunctionDefinition


logger = logging.getLogger(__name__)


class PluginState(Enum):
    """Plugin lifecycle states"""
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    INITIALIZING = auto()
    READY = auto()
    EXECUTING = auto()
    AWAITING_INPUT = auto()
    STOPPING = auto()
    ERROR = auto()


class PluginError(Exception):
    """Plugin-related errors"""
    pass


@dataclass
class PluginResponse:
    """Response from plugin execution"""
    success: bool
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    awaiting_input: bool = False
    error_code: Optional[int] = None


class Plugin:
    """
    Interface to a plugin's process.
    
    Handles:
    - Process lifecycle (start, stop, restart)
    - Pipe-based IPC with JSON-RPC 2.0 framing
    - Heartbeat tracking
    - User input passthrough
    
    This mirrors the C++ Plugin class implementation.
    """
    
    def __init__(
        self,
        manifest: PluginManifest,
        on_stream: Optional[Callable[[str], None]] = None,
        on_complete: Optional[Callable[[bool, str], None]] = None,
        on_error: Optional[Callable[[str, int], None]] = None,
        on_log: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize a plugin instance.
        
        Args:
            manifest: Parsed plugin manifest
            on_stream: Callback for streaming data
            on_complete: Callback for completion (success, data)
            on_error: Callback for errors (message, code)
            on_log: Callback for log messages (level, message)
        """
        self.manifest = manifest
        self.name = manifest.name
        self.description = manifest.description
        self.directory = manifest.directory
        self.executable_path = manifest.executable_path
        self.persistent = manifest.persistent
        self.passthrough = manifest.passthrough
        
        # Process state
        self._process: Optional[subprocess.Popen] = None
        self._state = PluginState.STOPPED
        self._state_lock = threading.Lock()
        
        # IPC
        self._next_request_id = 1
        self._pending_responses: Dict[int, queue.Queue] = {}
        self._read_buffer = bytearray()
        self._expected_length = 0
        
        # Heartbeat tracking
        self._last_heartbeat_time = 0.0
        self._process_start_time = 0.0
        self._awaiting_input = False
        
        # Callbacks
        self._on_stream = on_stream
        self._on_complete = on_complete
        self._on_error = on_error
        self._on_log = on_log
        
        # Reader thread
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running = False
        
        # Response queue for synchronous operations
        self._response_queue: queue.Queue = queue.Queue()
        self._current_full_response = ""
        
        # Last initialization response
        self._last_init_response: Dict[str, Any] = {}
        self._last_init_message = ""
    
    @property
    def state(self) -> PluginState:
        """Get current plugin state"""
        with self._state_lock:
            return self._state
    
    @state.setter
    def state(self, value: PluginState):
        """Set plugin state"""
        with self._state_lock:
            old_state = self._state
            self._state = value
            logger.debug(f"Plugin '{self.name}': {old_state.name} -> {value.name}")
    
    @property
    def is_running(self) -> bool:
        """Check if plugin process is running"""
        if self._process is None:
            return False
        return self._process.poll() is None
    
    @property
    def is_awaiting_input(self) -> bool:
        """Check if plugin is waiting for user input"""
        return self._awaiting_input
    
    def start(self) -> bool:
        """
        Start the plugin process.
        
        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.debug(f"Plugin '{self.name}' already running")
            return True
        
        try:
            self.state = PluginState.STARTING
            
            # Build command line
            cmd = self._build_command_line()
            if not cmd:
                self.state = PluginState.ERROR
                return False
            
            logger.info(f"Starting plugin '{self.name}': {cmd}")
            
            # Set up environment
            env = self._build_environment()
            
            # Start process with pipes
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.directory,
                env=env,
                shell=False,
                bufsize=0,  # Unbuffered
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            self._process_start_time = time.time()
            self._last_heartbeat_time = self._process_start_time
            
            # Start reader thread
            self._reader_running = True
            self._reader_thread = threading.Thread(
                target=self._reader_loop,
                name=f"PluginReader-{self.name}",
                daemon=True
            )
            self._reader_thread.start()
            
            self.state = PluginState.RUNNING
            logger.info(f"Plugin '{self.name}' started (PID: {self._process.pid})")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start plugin '{self.name}': {e}")
            self.state = PluginState.ERROR
            return False
    
    def stop(self) -> bool:
        """
        Stop the plugin process.
        
        Returns:
            True if stopped successfully
        """
        if not self.is_running:
            self.state = PluginState.STOPPED
            return True
        
        try:
            self.state = PluginState.STOPPING
            
            # Stop reader thread
            self._reader_running = False
            
            # Try graceful shutdown
            if self._process and self._process.stdin:
                try:
                    self._process.stdin.close()
                except:
                    pass
            
            # Wait briefly for clean exit
            if self._process:
                try:
                    self._process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    # Force kill
                    logger.warning(f"Plugin '{self.name}' did not exit gracefully, killing")
                    self._process.kill()
                    self._process.wait(timeout=1.0)
            
            # Wait for reader thread
            if self._reader_thread and self._reader_thread.is_alive():
                self._reader_thread.join(timeout=1.0)
            
            self._process = None
            self._reader_thread = None
            self._awaiting_input = False
            self._read_buffer.clear()
            self._expected_length = 0
            
            self.state = PluginState.STOPPED
            logger.info(f"Plugin '{self.name}' stopped")
            
            return True
            
        except Exception as e:
            logger.error(f"Error stopping plugin '{self.name}': {e}")
            self.state = PluginState.ERROR
            return False
    
    def restart(self) -> bool:
        """Restart the plugin process"""
        self.stop()
        return self.start()
    
    def initialize(self) -> PluginResponse:
        """
        Send initialize command to plugin.
        
        Returns:
            PluginResponse with initialization result
        """
        if not self.is_running:
            if not self.start():
                return PluginResponse(
                    success=False,
                    message="Failed to start plugin"
                )
        
        self.state = PluginState.INITIALIZING
        
        request = build_initialize_request(self._next_request_id)
        self._next_request_id += 1
        
        response = self._send_and_wait(request, timeout_ms=EXECUTE_TIMEOUT_MS)
        
        if response.success:
            self.state = PluginState.READY
            self._last_init_response = response.data
            self._last_init_message = response.message
        else:
            self.state = PluginState.ERROR
        
        return response
    
    def shutdown(self) -> PluginResponse:
        """
        Send shutdown command to plugin.
        
        Returns:
            PluginResponse with shutdown result
        """
        if not self.is_running:
            return PluginResponse(
                success=True,
                message="Plugin already stopped"
            )
        
        self.state = PluginState.STOPPING
        
        request = build_shutdown_request(self._next_request_id)
        self._next_request_id += 1
        
        response = self._send_and_wait(request, timeout_ms=5000)
        
        # Give plugin time to cleanup
        time.sleep(0.5)
        
        # Force stop if still running
        self.stop()
        
        return response
    
    def execute(
        self,
        function: str,
        arguments: Dict[str, Any],
        context: Optional[List[Dict[str, str]]] = None,
        system_info: Optional[str] = None,
        timeout_ms: int = EXECUTE_TIMEOUT_MS
    ) -> PluginResponse:
        """
        Execute a plugin function.
        
        Args:
            function: Function name to execute
            arguments: Function arguments
            context: Optional conversation context
            system_info: Optional system information string
            timeout_ms: Execution timeout in milliseconds
            
        Returns:
            PluginResponse with execution result
        """
        # Ensure plugin is running and initialized
        if not self.is_running:
            init_response = self.initialize()
            if not init_response.success:
                return init_response
        
        if self.state not in (PluginState.READY, PluginState.AWAITING_INPUT):
            return PluginResponse(
                success=False,
                message=f"Plugin not ready (state: {self.state.name})"
            )
        
        self.state = PluginState.EXECUTING
        self._current_full_response = ""
        
        request = build_execute_request(
            self._next_request_id,
            function,
            arguments,
            context,
            system_info
        )
        self._next_request_id += 1
        
        response = self._send_and_wait(request, timeout_ms=timeout_ms)
        
        if response.awaiting_input:
            self.state = PluginState.AWAITING_INPUT
            self._awaiting_input = True
        else:
            self.state = PluginState.READY
            self._awaiting_input = False
        
        return response
    
    def send_user_input(self, content: str) -> PluginResponse:
        """
        Send user input to a plugin in passthrough mode.
        
        Args:
            content: User input text
            
        Returns:
            PluginResponse with result
        """
        if not self.is_running:
            return PluginResponse(
                success=False,
                message="Plugin not running"
            )
        
        if not self._awaiting_input:
            return PluginResponse(
                success=False,
                message="Plugin not awaiting input"
            )
        
        self._current_full_response = ""
        
        request = build_input_request(self._next_request_id, content)
        self._next_request_id += 1
        
        response = self._send_and_wait(request, timeout_ms=EXECUTE_TIMEOUT_MS)
        
        if response.awaiting_input:
            self.state = PluginState.AWAITING_INPUT
            self._awaiting_input = True
        else:
            self.state = PluginState.READY
            self._awaiting_input = False
        
        return response
    
    def send_ping(self) -> bool:
        """
        Send ping to check plugin liveness.
        
        Returns:
            True if ping was sent successfully
        """
        if not self.is_running:
            return False
        
        request = build_ping_request(self._next_request_id)
        self._next_request_id += 1
        
        return self._send_request(request)
    
    def update_heartbeat(self):
        """Update the last heartbeat timestamp"""
        self._last_heartbeat_time = time.time()
    
    def is_heartbeat_expired(self) -> bool:
        """Check if heartbeat has expired"""
        reference_time = self._last_heartbeat_time or self._process_start_time
        if reference_time == 0:
            return False
        
        elapsed_ms = (time.time() - reference_time) * 1000
        return elapsed_ms > HEARTBEAT_TIMEOUT_MS
    
    def get_function(self, name: str) -> Optional[FunctionDefinition]:
        """Get a function definition by name"""
        return self.manifest.get_function(name)
    
    def get_function_names(self) -> List[str]:
        """Get list of all function names"""
        return self.manifest.get_function_names()
    
    # ========================================================================
    # Private Methods
    # ========================================================================
    
    def _build_command_line(self) -> Optional[List[str]]:
        """Build the command line for launching the plugin"""
        
        exe_path = Path(self.executable_path)
        
        # Check if executable exists
        if not exe_path.exists():
            logger.error(f"Plugin executable not found: {exe_path}")
            self._last_init_message = f"Executable not found: {exe_path}"
            return None
        
        # Handle Python scripts
        if exe_path.suffix.lower() == '.py':
            python_exe = self._find_python()
            if not python_exe:
                logger.error("Python interpreter not found for .py plugin")
                self._last_init_message = "Python interpreter not found"
                return None
            return [python_exe, str(exe_path)]
        
        # Handle executables directly
        return [str(exe_path)]
    
    def _find_python(self) -> Optional[str]:
        """Find Python interpreter"""
        import shutil
        
        # Check GA_PYTHON_DEV environment variable
        dev_python = os.environ.get('GA_PYTHON_DEV')
        if dev_python and os.path.exists(dev_python):
            return dev_python
        
        # Check for bundled Python
        plugin_root = Path(self.directory).parent.parent
        bundled = plugin_root / "python" / "python.exe"
        if bundled.exists():
            return str(bundled)
        
        # Check system PATH
        for name in ['python', 'python3', 'py']:
            found = shutil.which(name)
            if found:
                return found
        
        return None
    
    def _build_environment(self) -> Dict[str, str]:
        """Build environment variables for plugin process"""
        env = os.environ.copy()
        
        # Set PYTHONPATH for Python plugins
        if self.executable_path.endswith('.py'):
            libs_path = os.path.join(self.directory, 'libs')
            if os.path.exists(libs_path):
                existing = env.get('PYTHONPATH', '')
                if existing:
                    env['PYTHONPATH'] = f"{libs_path}{os.pathsep}{existing}"
                else:
                    env['PYTHONPATH'] = libs_path
        
        return env
    
    def _send_request(self, request: JsonRpcRequest) -> bool:
        """Send a request without waiting for response"""
        if not self._process or not self._process.stdin:
            return False
        
        try:
            framed = frame_message(request.to_dict())
            self._process.stdin.write(framed)
            self._process.stdin.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to send request to plugin '{self.name}': {e}")
            return False
    
    def _send_and_wait(
        self,
        request: JsonRpcRequest,
        timeout_ms: int = EXECUTE_TIMEOUT_MS
    ) -> PluginResponse:
        """Send a request and wait for response"""
        
        # Clear old responses
        while not self._response_queue.empty():
            try:
                self._response_queue.get_nowait()
            except queue.Empty:
                break
        
        # Create response queue for this request
        response_queue: queue.Queue = queue.Queue()
        self._pending_responses[request.id] = response_queue
        
        try:
            # Send request
            if not self._send_request(request):
                return PluginResponse(
                    success=False,
                    message="Failed to send request"
                )
            
            # Wait for response with heartbeat checking
            start_time = time.time()
            timeout_sec = timeout_ms / 1000.0
            
            while True:
                elapsed = time.time() - start_time
                remaining = timeout_sec - elapsed
                
                if remaining <= 0:
                    return PluginResponse(
                        success=False,
                        message="Request timeout"
                    )
                
                # Check heartbeat
                if self.is_heartbeat_expired():
                    if not self.is_running:
                        return PluginResponse(
                            success=False,
                            message="Plugin process died"
                        )
                    # Reset heartbeat if process is still alive
                    self._last_heartbeat_time = time.time()
                
                # Try to get response
                try:
                    response = response_queue.get(timeout=min(0.5, remaining))
                    return response
                except queue.Empty:
                    continue
                
        finally:
            # Cleanup
            self._pending_responses.pop(request.id, None)
    
    def _reader_loop(self):
        """Background thread that reads from plugin stdout"""
        logger.debug(f"Reader thread started for plugin '{self.name}'")
        
        buffer = bytearray()
        
        while self._reader_running and self._process:
            try:
                if not self._process.stdout:
                    break
                
                # Check if process is still running
                if self._process.poll() is not None:
                    logger.debug(f"Plugin '{self.name}' process exited")
                    break
                
                # Read one byte at a time to avoid blocking
                # This is less efficient but more reliable for IPC
                byte = self._process.stdout.read(1)
                if not byte:
                    # EOF
                    break
                
                buffer.extend(byte)
                
                # Try to parse complete messages from buffer
                while len(buffer) >= 4:
                    # Read length from header
                    msg_length = decode_length(bytes(buffer[:4]))
                    
                    if msg_length > MAX_MESSAGE_SIZE:
                        logger.error(f"Message too large from plugin '{self.name}': {msg_length}")
                        buffer = buffer[4:]  # Skip bad header
                        continue
                    
                    # Check if we have complete message
                    total_needed = 4 + msg_length
                    if len(buffer) < total_needed:
                        break  # Need more data
                    
                    # Extract and parse message
                    json_bytes = bytes(buffer[4:total_needed])
                    buffer = buffer[total_needed:]
                    
                    try:
                        msg = parse_message(json_bytes)
                        self._handle_message(msg)
                    except Exception as e:
                        logger.error(f"Failed to parse message from plugin '{self.name}': {e}")
                
            except Exception as e:
                if self._reader_running:
                    logger.error(f"Reader error for plugin '{self.name}': {e}")
                break
        
        logger.debug(f"Reader thread stopped for plugin '{self.name}'")
    
    def _process_buffer(self):
        """Process messages from read buffer"""
        while True:
            # Need at least 4 bytes for header
            if len(self._read_buffer) < 4:
                break
            
            # Read length if we haven't yet
            if self._expected_length == 0:
                self._expected_length = decode_length(bytes(self._read_buffer[:4]))
                
                if self._expected_length > MAX_MESSAGE_SIZE:
                    logger.error(f"Message too large from plugin '{self.name}': {self._expected_length}")
                    self._read_buffer.clear()
                    self._expected_length = 0
                    break
            
            # Check if we have complete message
            total_needed = 4 + self._expected_length
            if len(self._read_buffer) < total_needed:
                break
            
            # Extract and parse JSON
            json_bytes = bytes(self._read_buffer[4:total_needed])
            self._read_buffer = self._read_buffer[total_needed:]
            self._expected_length = 0
            
            try:
                msg = parse_message(json_bytes)
                self._handle_message(msg)
            except Exception as e:
                logger.error(f"Failed to parse message from plugin '{self.name}': {e}")
    
    def _handle_message(self, msg: Dict[str, Any]):
        """Handle a parsed JSON-RPC message"""
        
        if not is_valid_jsonrpc(msg):
            logger.warning(f"Invalid JSON-RPC from plugin '{self.name}'")
            return
        
        # Update heartbeat on any message
        self.update_heartbeat()
        
        msg_type = classify_message(msg)
        
        if msg_type == "response":
            self._handle_response(msg)
        elif msg_type == "notification":
            self._handle_notification(msg)
        else:
            logger.warning(f"Unknown message type from plugin '{self.name}'")
    
    def _handle_response(self, msg: Dict[str, Any]):
        """Handle a JSON-RPC response"""
        response = JsonRpcResponse.from_dict(msg)
        
        # Check for pong
        if response.result and isinstance(response.result, dict):
            if "timestamp" in response.result:
                # This is a pong response
                logger.debug(f"Pong from plugin '{self.name}'")
                return
            
            # Check for acknowledgment
            if response.result.get("acknowledged"):
                logger.debug(f"Acknowledgment from plugin '{self.name}'")
                return
        
        # Route to pending request
        response_queue = self._pending_responses.get(response.id)
        if response_queue:
            plugin_response = PluginResponse(
                success=not response.is_error(),
                message=self._current_full_response,
                data=response.result if response.result else {},
                awaiting_input=False,
                error_code=response.error.get("code") if response.error else None
            )
            response_queue.put(plugin_response)
        else:
            logger.warning(f"Unexpected response id {response.id} from plugin '{self.name}'")
    
    def _handle_notification(self, msg: Dict[str, Any]):
        """Handle a JSON-RPC notification"""
        notif = JsonRpcNotification.from_dict(msg)
        method = notif.method
        params = notif.params
        
        if method == "stream":
            # Streaming data
            data = params.get("data", "")
            if data:
                self._current_full_response += data
                if self._on_stream:
                    self._on_stream(data)
                    
        elif method == "complete":
            # Command completed
            success = params.get("success", True)
            data = params.get("data", "")
            awaiting_input = params.get("keep_session", False)
            
            if data:
                self._current_full_response += data
            
            self._awaiting_input = awaiting_input
            
            # Create and queue response
            response = PluginResponse(
                success=success,
                message=self._current_full_response,
                data=params,
                awaiting_input=awaiting_input
            )
            
            # Route to any pending request
            for queue_obj in self._pending_responses.values():
                queue_obj.put(response)
            
            if self._on_complete:
                self._on_complete(success, self._current_full_response)
                
        elif method == "error":
            # Error notification
            code = params.get("code", -1)
            message = params.get("message", "Unknown error")
            
            logger.error(f"Error from plugin '{self.name}': {message} (code={code})")
            
            self._awaiting_input = False
            
            response = PluginResponse(
                success=False,
                message=message,
                data=params,
                awaiting_input=False,
                error_code=code
            )
            
            for queue_obj in self._pending_responses.values():
                queue_obj.put(response)
            
            if self._on_error:
                self._on_error(message, code)
                
        elif method == "log":
            # Log message
            level = params.get("level", "info")
            log_msg = params.get("message", "")
            
            logger.debug(f"Plugin '{self.name}' [{level}]: {log_msg}")
            
            if self._on_log:
                self._on_log(level, log_msg)
        else:
            logger.debug(f"Unknown notification '{method}' from plugin '{self.name}'")

