"""
G-Assist Plugin Emulator

A Python tool that emulates the engine's plugin communication capabilities
for plugin development and testing.

Features:
- Plugin manifest scanning and function discovery
- JSON-RPC 2.0 communication with length-prefixed framing
- Passthrough and one-shot execution modes
- Heartbeat enforcement and watchdog
- Autonomous LLM judge-driven validation mode
- Interactive user-driven testing mode
"""

__version__ = "1.0.0"
__author__ = "NVIDIA G-Assist Team"

from .protocol import (
    ProtocolError,
    JsonRpcRequest,
    JsonRpcResponse, 
    JsonRpcNotification,
    frame_message,
    decode_length,
    MAX_MESSAGE_SIZE,
    PING_TIMEOUT_MS,
    EXECUTE_TIMEOUT_MS,
    PING_INTERVAL_MS,
)

from .manifest import (
    ManifestParser,
    PluginManifest,
    FunctionDefinition,
    ManifestError,
)

from .plugin import (
    Plugin,
    PluginState,
    PluginError,
)

from .manager import (
    PluginManager,
)

from .engine import (
    PluginEngine,
    EngineMode,
    ExecutionResult,
)

from .validator import (
    PluginValidator,
    ValidationReport,
    ValidationCategory,
    ValidationCheck,
    ValidationStatus,
)

from .watcher import (
    PluginWatcher,
    PluginChange,
)

__all__ = [
    # Protocol
    'ProtocolError',
    'JsonRpcRequest',
    'JsonRpcResponse',
    'JsonRpcNotification',
    'frame_message',
    'decode_length',
    'MAX_MESSAGE_SIZE',
    'PING_TIMEOUT_MS',
    'EXECUTE_TIMEOUT_MS',
    'PING_INTERVAL_MS',
    # Manifest
    'ManifestParser',
    'PluginManifest',
    'FunctionDefinition',
    'ManifestError',
    # Plugin
    'Plugin',
    'PluginState',
    'PluginError',
    # Manager
    'PluginManager',
    # Engine
    'PluginEngine',
    'EngineMode',
    'ExecutionResult',
    # Validator
    'PluginValidator',
    'ValidationReport',
    'ValidationCategory',
    'ValidationCheck',
    'ValidationStatus',
    # Watcher
    'PluginWatcher',
    'PluginChange',
]

