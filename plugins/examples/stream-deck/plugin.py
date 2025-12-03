# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Stream Deck Plugin
#
# This plugin discovers Stream Deck executable actions and exposes them as
# G-Assist functions. The manifest is dynamically updated with discovered actions.

import json
import logging
import os
import re
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
ACTIONS_CACHE_FILE = os.path.join(PLUGIN_DIR, "actions_cache.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

# ============================================================================
# STDOUT/STDERR PROTECTION
# ============================================================================
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

sys.stderr = _StderrToLog(LOG_FILE)

# ============================================================================
# PATH SETUP
# ============================================================================
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

import requests

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

try:
    from gassist_sdk import Plugin, Context
except ImportError as e:
    with open(LOG_FILE, "a") as f:
        f.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

LOCAL_MANIFEST_FILE = os.path.join(_plugin_dir, "manifest.json")

# ============================================================================
# LOGGING SETUP
# ============================================================================
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

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
    description="Stream Deck plugin - discover and execute Stream Deck actions"
)

# ============================================================================
# GLOBAL STATE
# ============================================================================
mcp_session_id: Optional[str] = None
mcp_server_url: str = "http://localhost:9090/mcp"

# Cache: action_id -> action info (name, description, etc.)
discovered_actions: Dict[str, Dict[str, Any]] = {}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_config() -> dict:
    """Load configuration from file."""
    default_config = {
        "mcp_server_url": "http://localhost:9090/mcp",
        "timeout": 30
    }
    
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return {**default_config, **json.load(f)}
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    return default_config


def sanitize_function_name(name: str) -> str:
    """Convert action name to valid function name."""
    # Convert to lowercase, replace spaces/special chars with underscore
    clean = re.sub(r'[^a-zA-Z0-9]+', '_', name.lower())
    # Remove leading/trailing underscores
    clean = clean.strip('_')
    # Prefix with streamdeck_
    return f"streamdeck_{clean}"


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
        "id": int(time.time() * 1000),
        "method": method,
        "params": params or {}
    }
    
    logger.info(f"MCP Request: {method} (session={mcp_session_id}, retry={_retry})")
    
    # Send keep-alive before potentially slow HTTP request
    plugin.stream(".")
    
    try:
        response = requests.post(mcp_server_url, headers=headers, json=payload, timeout=timeout)
        
        # Handle HTTP 400 (Bad Request) - typically stale session
        if response.status_code == 400:
            logger.warning(f"MCP returned HTTP 400 for {method} - session may be stale")
            if _retry:
                logger.info("Re-initializing session and retrying...")
                plugin.stream(".")  # Keep-alive during re-init
                mcp_session_id = None
                
                if _reinitialize_session():
                    return mcp_request(method, params, timeout, _retry=False)
                else:
                    raise Exception("Failed to re-initialize MCP session")
            else:
                raise Exception(f"MCP server returned 400 for {method}")
        
        if "mcp-session-id" in response.headers:
            mcp_session_id = response.headers["mcp-session-id"]
            logger.info(f"Got MCP session ID: {mcp_session_id}")
        
        response.raise_for_status()
        result = response.json()
        logger.info(f"MCP Response: {json.dumps(result, indent=2)[:500]}")
        return result
        
    except requests.exceptions.ConnectionError as e:
        raise Exception(f"Cannot connect to Stream Deck MCP server at {mcp_server_url}. Is it running?")
    except requests.exceptions.HTTPError as e:
        logger.error(f"MCP HTTP error: {e}")
        raise
    except Exception as e:
        logger.error(f"MCP request failed: {e}")
        raise


def _reinitialize_session() -> bool:
    """
    Re-initialize the MCP session.
    Used for automatic session recovery on 400 errors.
    """
    global mcp_session_id
    
    logger.info("Re-initializing MCP session...")
    plugin.stream(".")  # Keep-alive
    
    try:
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
                "clientInfo": {"name": "G-Assist-StreamDeck", "version": "1.0"}
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        plugin.stream(".")  # Keep-alive after response
        
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
    """Initialize MCP session."""
    try:
        result = mcp_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "G-Assist-StreamDeck", "version": "1.0"}
        })
        return "result" in result
    except Exception as e:
        logger.error(f"Failed to initialize MCP session: {e}")
        return False


def call_mcp_tool(tool_name: str, arguments: dict = None) -> Any:
    """Call an MCP tool."""
    result = mcp_request("tools/call", {
        "name": tool_name,
        "arguments": arguments or {}
    })
    
    if "result" in result:
        return result["result"]
    elif "error" in result:
        raise Exception(f"MCP tool error: {result['error']}")
    return result


def get_executable_actions() -> List[Dict[str, Any]]:
    """
    Get list of executable actions from Stream Deck.
    
    Response format:
    {
        "result": {
            "structuredContent": {
                "actions": [
                    {
                        "id": "bea905d0-...",  # ID to execute
                        "title": "Open webpage",  # User-configured title
                        "pluginId": "com.elgato.streamdeck.system.website",
                        "description": {
                            "name": "Website",  # Action type
                            "description": "Open URL"  # What it does
                        }
                    },
                    ...
                ]
            }
        }
    }
    """
    result = call_mcp_tool("get_executable_actions")
    
    # Extract from structuredContent.actions (preferred) or fallback to content text
    if isinstance(result, dict):
        # Try structuredContent first
        if "structuredContent" in result:
            structured = result["structuredContent"]
            if isinstance(structured, dict) and "actions" in structured:
                logger.info(f"Found {len(structured['actions'])} actions in structuredContent")
                return structured["actions"]
        
        # Fallback: parse from content text
        if "content" in result:
            for item in result.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        data = json.loads(text)
                        if isinstance(data, dict) and "actions" in data:
                            logger.info(f"Found {len(data['actions'])} actions in content text")
                            return data["actions"]
                    except json.JSONDecodeError:
                        pass
    
    logger.warning("No actions found in response")
    return []


def execute_action(action_id: str) -> dict:
    """Execute a Stream Deck action by ID."""
    result = call_mcp_tool("execute_action", {"id": action_id})
    
    # Extract from structuredContent or content
    if isinstance(result, dict):
        if "structuredContent" in result:
            return result["structuredContent"]
        if "content" in result:
            for item in result.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text", "")
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"success": True, "message": text}
    
    return {"success": True}


def save_actions_cache(actions: List[Dict[str, Any]]):
    """
    Save discovered actions to cache file.
    
    Each action has:
    - id: the execution ID
    - title: user-configured title (e.g., "Audacity", "Open webpage")
    - pluginId: source plugin (e.g., "com.elgato.streamdeck.system.openapp")
    - description.name: action type (e.g., "Open Application", "Website")
    - description.description: what it does (e.g., "Open an app", "Open URL")
    """
    cache = {}
    seen_names = {}  # Track duplicates
    
    for action in actions:
        action_id = action.get("id", "")
        if not action_id:
            continue
        
        # Extract from nested description object
        desc_obj = action.get("description", {})
        action_type = desc_obj.get("name", "Unknown")  # e.g., "Website", "Open Application"
        action_desc = desc_obj.get("description", "")  # e.g., "Open URL", "Open an app"
        
        # User's configured title for this specific action
        title = action.get("title", action_type)  # e.g., "Open webpage", "Audacity"
        
        # Plugin that provides this action
        plugin_id = action.get("pluginId", "")
        
        # Generate function name from title (more specific) or action type
        # Use title if available and meaningful, otherwise use action type
        base_name = title if title and title != action_type else action_type
        func_name = sanitize_function_name(base_name)
        
        # Handle duplicates by appending a number
        if func_name in seen_names:
            seen_names[func_name] += 1
            func_name = f"{func_name}_{seen_names[func_name]}"
        else:
            seen_names[func_name] = 1
        
        cache[func_name] = {
            "id": action_id,
            "title": title,
            "action_type": action_type,
            "description": action_desc,
            "plugin_id": plugin_id
        }
        
        logger.info(f"Cached action: {func_name} -> '{title}' ({action_type})")
    
    try:
        with open(ACTIONS_CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
        logger.info(f"Saved {len(cache)} actions to cache")
    except Exception as e:
        logger.error(f"Failed to save actions cache: {e}")
    
    return cache


def load_actions_cache() -> Dict[str, Dict[str, Any]]:
    """Load actions from cache file."""
    try:
        if os.path.isfile(ACTIONS_CACHE_FILE):
            with open(ACTIONS_CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load actions cache: {e}")
    return {}


def update_manifest_with_actions(actions_cache: Dict[str, Dict[str, Any]]):
    """Update manifest with discovered actions as functions."""
    
    # Start with the discover function
    functions = [
        {
            "name": "streamdeck_discover",
            "description": "Discover Stream Deck and learn what actions are available. Call this first to see what your Stream Deck can do, then use the discovered action functions.",
            "tags": ["stream-deck", "streamdeck", "discover", "elgato", "actions"],
            "properties": {},
            "required": []
        }
    ]
    
    # Add a function for each discovered action
    for func_name, action_info in actions_cache.items():
        title = action_info.get("title", "Unknown")
        action_type = action_info.get("action_type", "")
        action_desc = action_info.get("description", "")
        
        # Build a nice description
        # e.g., "Execute 'Audacity' (Open Application) - Open an app"
        description = f"Execute '{title}' on Stream Deck"
        if action_type and action_type != title:
            description += f" ({action_type})"
        if action_desc:
            description += f" - {action_desc}"
        
        # Build tags from action info
        tags = ["stream-deck", "execute"]
        if title:
            tags.append(title.lower().replace(" ", "-"))
        if action_type:
            tags.append(action_type.lower().replace(" ", "-"))
        
        func = {
            "name": func_name,
            "description": description,
            "tags": tags,
            "properties": {},
            "required": []
        }
        functions.append(func)
    
    # Create manifest
    manifest = {
        "manifestVersion": 1,
        "name": PLUGIN_NAME,
        "version": "1.0.0",
        "description": f"Stream Deck plugin with {len(actions_cache)} executable actions",
        "executable": "plugin.py",
        "persistent": True,
        "protocol_version": "2.0",
        "functions": functions
    }
    
    # Write to both locations
    for path in [MANIFEST_FILE, LOCAL_MANIFEST_FILE]:
        try:
            with open(path, "w") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Updated manifest at {path}")
        except Exception as e:
            logger.warning(f"Failed to write manifest to {path}: {e}")


def register_action_commands():
    """Register command handlers for cached actions."""
    global discovered_actions
    
    actions_cache = load_actions_cache()
    discovered_actions = actions_cache
    
    for func_name, action_info in actions_cache.items():
        action_id = action_info.get("id")
        title = action_info.get("title", "Unknown")
        action_type = action_info.get("action_type", "")
        
        if not action_id:
            continue
        
        # Create handler for this action
        def make_handler(aid, atitle, atype):
            def handler(context: Context = None):
                display_name = atitle if atitle else atype
                logger.info(f"Executing action: {display_name} (id={aid})")
                plugin.stream(f"Executing **{display_name}**...\n")
                
                try:
                    global mcp_session_id
                    if not mcp_session_id:
                        if not initialize_mcp_session():
                            return "Failed to connect to Stream Deck MCP server."
                    
                    result = execute_action(aid)
                    
                    success = result.get("success", True) if isinstance(result, dict) else True
                    if success:
                        return f"**{display_name}** executed successfully."
                    else:
                        msg = result.get("message", "Unknown error") if isinstance(result, dict) else str(result)
                        return f"Failed to execute {display_name}: {msg}"
                        
                except Exception as e:
                    logger.error(f"Error executing action {display_name}: {e}")
                    return f"Error: {e}"
            
            return handler
        
        plugin.command(func_name)(make_handler(action_id, title, action_type))
        logger.info(f"Registered action command: {func_name} -> '{title}' ({action_type})")


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@plugin.command("streamdeck_discover")
def streamdeck_discover_cmd(context: Context = None):
    """
    Discover Stream Deck and its executable actions.
    
    This connects to the Stream Deck MCP server, queries for available
    actions, and registers them as functions in the manifest.
    """
    global mcp_session_id, discovered_actions
    
    plugin.stream("**Discovering Stream Deck...**\n\n")
    
    try:
        # Step 1: Connect to MCP server
        plugin.stream("Connecting to Stream Deck MCP server...\n")
        
        if not initialize_mcp_session():
            return "Failed to connect to Stream Deck MCP server.\n\nMake sure the Stream Deck MCP server is running."
        
        plugin.stream("Connected.\n\n")
        
        # Step 2: Query for available actions
        plugin.stream("Querying available actions...\n")
        
        actions = get_executable_actions()
        
        if not actions:
            return "No executable actions found.\n\nConfigure some actions in the Stream Deck app, then try again."
        
        plugin.stream(f"Found **{len(actions)} actions**.\n\n")
        
        # Step 3: Process and cache actions
        plugin.stream("Registering actions...\n")
        
        actions_cache = save_actions_cache(actions)
        discovered_actions = actions_cache
        
        # Step 4: Update manifest
        update_manifest_with_actions(actions_cache)
        
        # Step 5: Register commands
        register_action_commands()
        
        plugin.stream("Done.\n\n")
        
        # Step 6: Build response with discovered actions
        response = f"**Stream Deck Discovery Complete**\n\n"
        response += f"Found **{len(actions_cache)} actions** ready to use:\n\n"
        
        for func_name, action_info in actions_cache.items():
            title = action_info.get("title", "Unknown")
            action_type = action_info.get("action_type", "")
            action_desc = action_info.get("description", "")
            
            # Show title with action type in parentheses, plus description
            response += f"- **{title}**"
            if action_type and action_type != title:
                response += f" ({action_type})"
            if action_desc:
                response += f" - {action_desc}"
            response += "\n"
        
        response += f"\nJust ask me to execute any of these actions."
        
        return response
        
    except Exception as e:
        logger.error(f"Discovery failed: {e}", exc_info=True)
        return f"Discovery failed: {e}"


@plugin.command("on_input")
def on_input(content: str):
    """Handle follow-up user input."""
    content = content.strip()
    
    if content.lower() in ["exit", "quit", "bye"]:
        plugin.set_keep_session(False)
        return "Goodbye."
    
    plugin.set_keep_session(True)
    return "Use `streamdeck_discover` to find available actions, or call an action function directly."


# ============================================================================
# INITIALIZATION
# ============================================================================

# Load cached actions and register commands at startup
logger.info("Initializing Stream Deck plugin...")
register_action_commands()
logger.info(f"Registered commands: {list(plugin._commands.keys())}")


if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin...")
    plugin.run()
