# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Stream Deck MCP Plugin
#
# This plugin interfaces with an MCP (Model Context Protocol) server to discover
# and execute tools dynamically. It rewrites its manifest.json at runtime based
# on the tools discovered from the MCP server.

import json
import logging
import os
import sys
import time
from typing import Optional, Dict, Any, List

# ============================================================================
# CONFIGURATION (must be early for log file path)
# ============================================================================
PLUGIN_NAME = "stream-deck"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."), 
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
MANIFEST_FILE = os.path.join(PLUGIN_DIR, "manifest.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

# ============================================================================
# STDOUT/STDERR PROTECTION
# ============================================================================
# CRITICAL: Redirect stderr to log file BEFORE importing any libraries.
# This prevents libraries (like requests/urllib3) from corrupting the 
# pipe protocol by accidentally writing to stdout/stderr.
# 
# stdout is used by the SDK protocol - DO NOT redirect it!
# stderr needs to go to log file to prevent corruption.

class _StderrToLog:
    """Redirect stderr writes to log file to prevent pipe corruption."""
    def __init__(self, log_path):
        self._log_path = log_path
        self._original_stderr = sys.stderr
    
    def write(self, msg):
        if msg and msg.strip():
            try:
                with open(self._log_path, "a") as f:
                    f.write(f"[STDERR] {msg}\n")
            except:
                pass
    
    def flush(self):
        pass

# Redirect stderr to log file
sys.stderr = _StderrToLog(LOG_FILE)

# ============================================================================
# PATH SETUP - Must be BEFORE importing libs/ dependencies
# ============================================================================
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# Now we can import from libs/
import requests

# Disable any library logging that might go to stdout
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

try:
    from gassist_sdk import Plugin, Context
except ImportError as e:
    with open(LOG_FILE, "a") as f:
        f.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

# Also check local manifest for development
LOCAL_MANIFEST_FILE = os.path.join(_plugin_dir, "manifest.json")

# ============================================================================
# LOGGING SETUP
# ============================================================================
# Configure root logger to use FILE ONLY (no StreamHandler!)
# This prevents any library from accidentally writing to stdout

# Remove any existing handlers
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

# Set up file-only logging with UTF-8 encoding (required for emojis)
file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.root.addHandler(file_handler)
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# ============================================================================
# PLUGIN DEFINITION
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="1.0.0",
    description="Stream Deck MCP plugin - dynamically discovers and executes tools from MCP server"
)

# ============================================================================
# GLOBAL STATE
# ============================================================================
mcp_session_id: Optional[str] = None
mcp_tools: Dict[str, Dict[str, Any]] = {}  # tool_name -> tool_schema
mcp_server_url: str = "http://localhost:9090/mcp"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_config() -> dict:
    """Load configuration from file."""
    default_config = {
        "mcp_server_url": "http://localhost:9090/mcp",
        "auto_discover": True,
        "timeout": 30
    }
    
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                return {**default_config, **config}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    # Create default config
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(default_config, f, indent=2)
    except:
        pass
    
    return default_config


def mcp_request(method: str, params: dict = None, timeout: int = 30, _retry: bool = True) -> dict:
    """
    Send a JSON-RPC request to the MCP server.
    
    Automatically handles session timeout (HTTP 400) by re-initializing
    the session and retrying the request once.
    """
    global mcp_session_id, mcp_server_url
    
    config = load_config()
    mcp_server_url = config.get("mcp_server_url", mcp_server_url)
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }
    
    if mcp_session_id:
        headers["mcp-session-id"] = mcp_session_id
    
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000),  # Unique ID
        "method": method,
        "params": params or {}
    }
    
    logger.info(f"MCP Request: {method} to {mcp_server_url} (session={mcp_session_id}, retry={_retry})")
    logger.debug(f"Payload: {json.dumps(payload)}")
    
    response = None
    try:
        response = requests.post(
            mcp_server_url,
            headers=headers,
            json=payload,
            timeout=timeout
        )
        
        logger.info(f"MCP Response status: {response.status_code}")
        
        # Handle HTTP 400 (Bad Request) - typically session timeout
        # Check this BEFORE raise_for_status() to handle it gracefully
        if response.status_code == 400:
            logger.warning(f"MCP returned HTTP 400 for {method}")
            if _retry:
                logger.info("Attempting session re-initialization...")
                mcp_session_id = None
                
                if _reinitialize_session():
                    logger.info("Session re-initialized successfully, retrying request...")
                    return mcp_request(method, params, timeout, _retry=False)
                else:
                    logger.error("Failed to re-initialize session after 400 error")
                    raise Exception("MCP session expired and re-initialization failed")
            else:
                logger.error("Already retried once, giving up")
                raise Exception(f"MCP server returned 400 Bad Request for {method}")
        
        # Extract session ID from response headers if present
        if "mcp-session-id" in response.headers:
            mcp_session_id = response.headers["mcp-session-id"]
            logger.info(f"Got MCP session ID: {mcp_session_id}")
        
        # Now check for other HTTP errors
        response.raise_for_status()
        
        result = response.json()
        # Log FULL MCP response to file (no truncation for debugging/processing)
        logger.info(f"[MCP RAW RESPONSE] {method}:\n{json.dumps(result, indent=2)}")
        return result
        
    except requests.exceptions.Timeout:
        logger.error(f"MCP request timed out: {method}")
        raise Exception(f"MCP server timeout for {method}")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"MCP connection error: {e}")
        raise Exception(f"Cannot connect to MCP server: {e}")
    except requests.exceptions.HTTPError as e:
        # For non-400 HTTP errors (400 is handled above)
        logger.error(f"MCP HTTP error: {e}")
        raise Exception(f"MCP server HTTP error: {e}")
    except Exception as e:
        # Catch-all for any other errors
        logger.error(f"MCP request failed: {type(e).__name__}: {e}")
        raise


def _reinitialize_session() -> bool:
    """
    Internal function to re-initialize the MCP session.
    Used for automatic session recovery on 400 errors.
    """
    global mcp_session_id
    
    logger.info("Re-initializing MCP session...")
    
    try:
        # Make initialize request directly (not through mcp_request to avoid recursion)
        config = load_config()
        url = config.get("mcp_server_url", mcp_server_url)
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
        
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "RISE-MCP-Client",
                    "version": "1.0"
                }
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # Extract new session ID
        if "mcp-session-id" in response.headers:
            mcp_session_id = response.headers["mcp-session-id"]
            logger.info(f"Got new MCP session ID: {mcp_session_id}")
        
        response.raise_for_status()
        result = response.json()
        
        if "result" in result:
            logger.info("MCP session re-initialized successfully")
            return True
        elif "error" in result:
            logger.error(f"MCP re-initialization error: {result['error']}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to re-initialize MCP session: {e}")
        return False


def initialize_mcp_session() -> bool:
    """Initialize a session with the MCP server."""
    global mcp_session_id
    
    try:
        result = mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "RISE-MCP-Client",
                "version": "1.0"
            }
        })
        
        if "result" in result:
            logger.info("MCP session initialized successfully")
            return True
        elif "error" in result:
            logger.error(f"MCP initialization error: {result['error']}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize MCP session: {e}")
        return False


def discover_mcp_tools() -> List[Dict[str, Any]]:
    """Discover available tools from the MCP server."""
    global mcp_tools
    
    try:
        result = mcp_request("tools/list", {})
        
        if "result" in result and "tools" in result["result"]:
            tools = result["result"]["tools"]
            
            # Store tools in global dict
            mcp_tools = {tool["name"]: tool for tool in tools}
            
            logger.info(f"Discovered {len(tools)} tools from MCP server")
            return tools
        
        return []
        
    except Exception as e:
        logger.error(f"Failed to discover tools: {e}")
        return []


def update_manifest(tools: List[Dict[str, Any]]):
    """Update the manifest.json with discovered tools."""
    
    # Build functions list from MCP tools
    functions = [
        {
            "name": "streamdeck_discover",
            "description": "Discover available tools from the Stream Deck MCP server. Call this to refresh the list of available actions.",
            "tags": ["stream-deck", "mcp", "discover", "tools"],
            "properties": {},
            "required": []
        }
    ]
    
    for tool in tools:
        # Convert MCP tool schema to G-Assist function schema
        # Use streamdeck_ prefix to avoid conflicts with other MCP plugins
        func = {
            "name": f"streamdeck_{tool['name']}",
            "description": tool.get("description", f"Execute {tool['name']} on Stream Deck"),
            "tags": ["stream-deck", tool["name"]],
            "properties": {},
            "required": []
        }
        
        # Convert input schema if present
        if "inputSchema" in tool:
            schema = tool["inputSchema"]
            if "properties" in schema:
                for prop_name, prop_schema in schema["properties"].items():
                    func["properties"][prop_name] = {
                        "type": prop_schema.get("type", "string"),
                        "description": prop_schema.get("description", f"Parameter: {prop_name}")
                    }
            
            if "required" in schema:
                func["required"] = schema["required"]
        
        functions.append(func)
    
    # Create new manifest
    manifest = {
        "manifestVersion": 1,
        "name": PLUGIN_NAME,
        "version": "1.0.0",
        "description": f"Stream Deck MCP plugin with {len(tools)} discovered tools",
        "executable": "plugin.py",
        "persistent": True,
        "protocol_version": "2.0",
        "functions": functions
    }
    
    # Write to deployed manifest location
    try:
        with open(MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Updated manifest with {len(functions)} functions at {MANIFEST_FILE}")
    except Exception as e:
        logger.error(f"Failed to write manifest to {MANIFEST_FILE}: {e}")
    
    # Also update local manifest for development
    try:
        with open(LOCAL_MANIFEST_FILE, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Updated local manifest at {LOCAL_MANIFEST_FILE}")
    except Exception as e:
        logger.warning(f"Failed to write local manifest: {e}")


def call_mcp_tool(tool_name: str, arguments: dict) -> Any:
    """Call a tool on the MCP server."""
    
    try:
        result = mcp_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })
        
        if "result" in result:
            return result["result"]
        elif "error" in result:
            raise Exception(f"MCP tool error: {result['error']}")
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to call MCP tool {tool_name}: {e}")
        raise


# ============================================================================
# RESPONSE FORMATTING
# ============================================================================

def format_mcp_response(tool_name: str, result: Any) -> str:
    """
    Format MCP response as beautiful, human-readable text.
    
    Stream Deck specific formatting for devices, plugins, actions, etc.
    """
    MAX_RESPONSE_SIZE = 4000
    
    def truncate_for_engine(text: str, max_size: int = MAX_RESPONSE_SIZE) -> str:
        if len(text) > max_size:
            return text[:max_size] + "\n\n[... Response truncated]"
        return text
    
    def try_parse_json(text: str) -> Any:
        """Try to parse text as JSON."""
        text = text.strip()
        if text.startswith('{') or text.startswith('['):
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
        return text
    
    # ========== STREAM DECK SPECIFIC FORMATTERS ==========
    
    def format_devices(devices: list) -> str:
        """Format Stream Deck devices beautifully."""
        if not devices:
            return "No Stream Deck devices found."
        
        lines = [f"Found **{len(devices)} Stream Deck device(s)**:\n"]
        
        for device in devices:
            name = device.get("name", "Unknown Device")
            model = device.get("model", "")
            connected = device.get("connected", False)
            device_id = device.get("id", "")
            caps = device.get("capabilities", {})
            
            # Status icon
            status = "🟢 Connected" if connected else "⚫ Disconnected"
            
            lines.append(f"**{name}**")
            if model and model != name:
                lines.append(f"  Model: {model}")
            lines.append(f"  Status: {status}")
            
            # Capabilities
            if caps:
                keys = caps.get("keys", 0)
                cols = caps.get("columns", 0)
                rows = caps.get("rows", 0)
                dials = caps.get("dials", 0)
                
                lines.append(f"  Layout: {cols}x{rows} ({keys} keys)")
                if dials > 0:
                    lines.append(f"  Dials: {dials}")
            
            if device_id:
                lines.append(f"  ID: `{device_id}`")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_plugins(plugins: list) -> str:
        """Format Stream Deck plugins beautifully."""
        if not plugins:
            return "No plugins installed."
        
        lines = [f"Found **{len(plugins)} plugin(s)** installed:\n"]
        
        for i, plugin in enumerate(plugins, 1):
            name = plugin.get("name", "Unknown")
            author = plugin.get("author", "")
            desc = plugin.get("description", "")
            version = plugin.get("version", "")
            actions = plugin.get("actions", [])
            
            # Plugin header
            header = f"**{i}. {name}**"
            if version:
                header += f" (v{version})"
            lines.append(header)
            
            if author:
                lines.append(f"   by {author}")
            if desc:
                lines.append(f"   {desc}")
            
            # Actions summary
            if actions:
                action_count = len(actions)
                action_names = [a.get("name", "?") for a in actions[:3]]
                action_preview = ", ".join(action_names)
                if action_count > 3:
                    action_preview += f" (+{action_count - 3} more)"
                lines.append(f"   Actions: {action_preview}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def format_actions(actions: list) -> str:
        """Format executable actions beautifully."""
        if not actions:
            return "No executable actions available.\n\nTip: Configure actions in the Stream Deck app, then try again."
        
        lines = [f"Found **{len(actions)} executable action(s)**:\n"]
        
        for i, action in enumerate(actions, 1):
            name = action.get("name", "Unknown Action")
            action_id = action.get("id", "")
            desc = action.get("description", "")
            plugin = action.get("plugin", "")
            
            lines.append(f"**{i}. {name}**")
            if desc:
                lines.append(f"   {desc}")
            if plugin:
                lines.append(f"   Plugin: {plugin}")
            if action_id:
                lines.append(f"   To execute: `execute_action` with id `{action_id}`")
            lines.append("")
        
        return "\n".join(lines)
    
    def format_execution_result(result_data: dict) -> str:
        """Format action execution result."""
        success = result_data.get("success", True)
        message = result_data.get("message", "")
        
        if success:
            return f"Action executed successfully!" + (f"\n{message}" if message else "")
        else:
            return f"Action failed: {message}" if message else "Action failed."
    
    def format_generic(data: Any, indent: int = 0) -> str:
        """Format any data structure nicely."""
        prefix = "  " * indent
        
        if data is None:
            return "(none)"
        elif isinstance(data, bool):
            return "Yes" if data else "No"
        elif isinstance(data, (int, float)):
            return str(data)
        elif isinstance(data, str):
            return data
        elif isinstance(data, list):
            if not data:
                return "(empty)"
            if len(data) <= 5 and all(isinstance(x, (str, int, float, bool)) for x in data):
                return ", ".join(str(x) for x in data)
            lines = []
            for item in data:
                formatted = format_generic(item, indent + 1)
                lines.append(f"{prefix}• {formatted}")
            return "\n".join(lines)
        elif isinstance(data, dict):
            if not data:
                return "(empty)"
            lines = []
            for k, v in data.items():
                formatted = format_generic(v, indent + 1)
                if "\n" in formatted:
                    lines.append(f"{prefix}**{k}**:\n{formatted}")
                else:
                    lines.append(f"{prefix}**{k}**: {formatted}")
            return "\n".join(lines)
        return str(data)
    
    # ========== MAIN FORMATTING LOGIC ==========
    
    def format_result_data(data: Any) -> str:
        """Smart formatting based on data structure."""
        if not isinstance(data, dict):
            if isinstance(data, list):
                return format_generic(data)
            return str(data) if data else "(empty result)"
        
        # Detect and format Stream Deck specific responses
        if "device_ids" in data or "devices" in data:
            devices = data.get("device_ids") or data.get("devices") or []
            return format_devices(devices)
        
        if "plugins" in data:
            return format_plugins(data["plugins"])
        
        if "actions" in data:
            return format_actions(data["actions"])
        
        if "success" in data or "executed" in data:
            return format_execution_result(data)
        
        # Generic formatting
        return format_generic(data)
    
    # ========== PROCESS RESULT ==========
    
    output_lines = []
    
    if result is None:
        return f"**{tool_name}** completed (no data returned)"
    
    # Extract data from MCP response format
    data_to_format = None
    
    if isinstance(result, dict):
        # Standard MCP format: {"content": [{"type": "text", "text": "..."}]}
        if "content" in result and isinstance(result["content"], list):
            for item in result["content"]:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content = item.get("text", "")
                    parsed = try_parse_json(text_content)
                    if isinstance(parsed, (dict, list)):
                        data_to_format = parsed
                        break
                    else:
                        data_to_format = text_content
                        break
            
            # Also check structuredContent (some MCP servers provide this)
            if data_to_format is None and "structuredContent" in result:
                data_to_format = result["structuredContent"]
        
        # Check structuredContent at top level too
        elif "structuredContent" in result:
            data_to_format = result["structuredContent"]
        
        # Direct response (not wrapped in content)
        else:
            data_to_format = result
    
    elif isinstance(result, list):
        data_to_format = result
    
    else:
        data_to_format = result
    
    # Format the extracted data
    formatted = format_result_data(data_to_format)
    
    # Build final response
    full_response = formatted
    
    # Log full response to file (no truncation)
    logger.info(f"[MCP FULL RESPONSE] {tool_name}:\n{full_response}")
    
    # Truncate for engine output to prevent buffer issues
    return truncate_for_engine(full_response)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@plugin.command("streamdeck_discover")
def streamdeck_discover_cmd(context: Context = None):
    """
    Discover available tools from the Stream Deck MCP server.
    
    This command:
    1. Initializes a session with the MCP server (if needed)
    2. Queries available tools
    3. Updates the manifest.json with discovered tools
    4. Returns a list of available tools
    
    Note: If session has expired (400 error), automatic retry with fresh session.
    """
    global mcp_session_id
    
    plugin.stream("🔍 Connecting to Stream Deck MCP server...\n")
    
    try:
        # Initialize session if we don't have one
        # Note: If session expired, mcp_request will auto-retry with new session on 400
        if not mcp_session_id:
            plugin.stream("Initializing MCP session...\n")
            if not initialize_mcp_session():
                return "❌ Failed to initialize MCP session. Is the Stream Deck MCP server running?"
        
        # Discover tools (will auto-retry with new session if 400)
        plugin.stream("Discovering available tools...\n")
        tools = discover_mcp_tools()
        
        if not tools:
            return "⚠️ No tools discovered from MCP server. The server may not have any tools registered."
        
        # Update manifest
        plugin.stream("Updating manifest with discovered tools...\n")
        update_manifest(tools)
        
        # Register the newly discovered commands so they can be called immediately
        logger.info(f"Before dynamic registration, commands: {list(plugin._commands.keys())}")
        register_dynamic_commands()
        logger.info(f"After dynamic registration, commands: {list(plugin._commands.keys())}")
        
        # Build response
        response = f"✅ Discovered {len(tools)} tools from Stream Deck MCP server:\n\n"
        
        for tool in tools:
            response += f"• **{tool['name']}**"
            if tool.get("description"):
                response += f": {tool['description']}"
            response += "\n"
        
        response += f"\n📝 Manifest updated. You can now use these tools with `streamdeck_<tool_name>` commands."
        
        return response
        
    except Exception as e:
        logger.error(f"Error discovering tools: {e}")
        return f"❌ Error: {e}"


@plugin.command("streamdeck_call")
def streamdeck_call_cmd(tool: str = None, arguments: str = None, context: Context = None):
    """
    Call any MCP tool by name with JSON arguments.
    
    Args:
        tool: The name of the MCP tool to call (with or without streamdeck_ prefix)
        arguments: JSON string of arguments to pass to the tool
    """
    global mcp_session_id
    
    if not tool:
        return "❌ Please specify a tool name. Use `streamdeck_discover` to see available tools."
    
    # Strip streamdeck_ prefix if present - MCP server doesn't know our prefixed names
    original_tool = tool
    if tool.startswith("streamdeck_"):
        tool = tool[11:]  # Remove "streamdeck_" prefix
        logger.info(f"Stripped prefix: {original_tool} -> {tool}")
    
    # Parse arguments
    args = {}
    if arguments:
        try:
            args = json.loads(arguments)
        except json.JSONDecodeError:
            return f"❌ Invalid JSON arguments: {arguments}"
    
    try:
        # Initialize session if needed
        if not mcp_session_id:
            if not initialize_mcp_session():
                return "❌ Failed to initialize MCP session."
        
        plugin.stream(f"🎮 Calling Stream Deck tool: {tool}...\n")
        
        result = call_mcp_tool(tool, args)
        
        # Format MCP response as human-readable text (no raw JSON)
        formatted = format_mcp_response(tool, result)
        return formatted
        
    except Exception as e:
        logger.error(f"Error calling tool {tool}: {e}")
        return f"❌ Error calling {tool}: {e}"


@plugin.command("on_input")
def on_input(content: str):
    """Handle follow-up user input."""
    # For now, just pass through to mcp_call if it looks like a tool call
    content = content.strip()
    
    if content.lower() in ["exit", "quit", "bye"]:
        plugin.set_keep_session(False)
        return "👋 Goodbye!"
    
    plugin.set_keep_session(True)
    return f"Use `streamdeck_discover` to see available tools or `streamdeck_call` to call a specific tool."


# ============================================================================
# DYNAMIC COMMAND REGISTRATION
# ============================================================================

def register_dynamic_commands():
    """
    Register commands dynamically based on discovered MCP tools.
    
    This is called at startup and after discovery to register tools.
    """
    global mcp_tools
    
    # Try to load tools from previous discovery
    try:
        logger.info(f"register_dynamic_commands: Loading manifest from {MANIFEST_FILE}")
        
        if os.path.isfile(MANIFEST_FILE):
            with open(MANIFEST_FILE, "r") as f:
                manifest = json.load(f)
            
            functions = manifest.get("functions", [])
            logger.info(f"register_dynamic_commands: Found {len(functions)} functions in manifest")
            
            registered_count = 0
            for func in functions:
                name = func.get("name", "")
                if name.startswith("streamdeck_") and name != "streamdeck_discover" and name != "streamdeck_call":
                    # Extract original tool name (MCP server's name without prefix)
                    tool_name = name[11:]  # Remove "streamdeck_" prefix
                    
                    # Register dynamic command handler
                    def make_handler(tn):
                        def handler(**kwargs):
                            logger.info(f"Dynamic handler for {tn} called with kwargs={kwargs}")
                            return streamdeck_call_cmd(tool=tn, arguments=json.dumps(kwargs) if kwargs else None)
                        return handler
                    
                    plugin.command(name)(make_handler(tool_name))
                    registered_count += 1
                    logger.info(f"Registered dynamic command: {name} -> MCP tool: {tool_name}")
            
            logger.info(f"register_dynamic_commands: Registered {registered_count} dynamic commands")
        else:
            logger.info(f"register_dynamic_commands: No manifest file found at {MANIFEST_FILE}")
    
    except Exception as e:
        logger.warning(f"Could not load dynamic commands: {e}", exc_info=True)


# ============================================================================
# INITIALIZATION
# ============================================================================

# Register dynamic commands from previous discovery
logger.info(f"At startup, commands before registration: {list(plugin._commands.keys())}")
register_dynamic_commands()
logger.info(f"At startup, commands after registration: {list(plugin._commands.keys())}")

# Auto-discover tools on startup if configured
config = load_config()
if config.get("auto_discover", False):
    try:
        logger.info("Auto-discovering MCP tools on startup...")
        if initialize_mcp_session():
            tools = discover_mcp_tools()
            if tools:
                update_manifest(tools)
                register_dynamic_commands()
    except Exception as e:
        logger.warning(f"Auto-discovery failed: {e}")


if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin...")
    plugin.run()
