# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Stream Deck Plugin
#
# This plugin discovers Stream Deck executable actions and exposes them as
# G-Assist functions using the SDK's MCP auto-discovery support.
#
# All MCP session management, caching, and manifest updates are handled by the SDK.

import json
import logging
import os
import sys
from typing import List

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "stream-deck"

# Source directory (where plugin.py and manifest.json live)
SOURCE_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_FILE = os.path.join(SOURCE_DIR, "manifest.json")

# Deploy directory (where logs and cache are written)
DEPLOY_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."), 
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
LOG_FILE = os.path.join(DEPLOY_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(DEPLOY_DIR, exist_ok=True)

# ============================================================================
# STDOUT/STDERR PROTECTION
# ============================================================================
class _StderrToLog:
    """Redirect stderr writes to log file to prevent pipe corruption."""
    def __init__(self, log_path):
        self._log_path = log_path
    
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
# PATH SETUP - Add SDK to path
# ============================================================================
_libs_path = os.path.join(SOURCE_DIR, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# ============================================================================
# LOGGING SETUP
# ============================================================================
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.root.addHandler(file_handler)
logging.root.setLevel(logging.INFO)

# Suppress noisy libraries
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# ============================================================================
# SDK IMPORTS
# ============================================================================
try:
    from gassist_sdk import MCPPlugin, Context
    from gassist_sdk.mcp import MCPClient, FunctionDef, sanitize_name
except ImportError as e:
    logger.error(f"FATAL: Cannot import gassist_sdk: {e}")
    sys.exit(1)

# ============================================================================
# CONFIGURATION LOADER
# ============================================================================
def load_manifest() -> dict:
    """Load manifest.json - the source of truth for MCP configuration."""
    try:
        with open(MANIFEST_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading manifest: {e}")
        return {}


# ============================================================================
# PLUGIN DEFINITION - Using MCPPlugin for auto-discovery
# ============================================================================
# 
# MCP configuration lives in manifest.json:
#   "mcp": { "enabled": true, "server_url": "...", "launch_on_startup": true }
# 
# The engine reads the manifest, sees launch_on_startup=true, and launches
# this plugin at startup for auto-discovery.
#
manifest = load_manifest()
mcp_config = manifest.get("mcp", {})
mcp_url = mcp_config.get("server_url", "http://localhost:9090/mcp")

plugin = MCPPlugin(
    name=PLUGIN_NAME,
    version=manifest.get("version", "2.0.0"),
    description=manifest.get("description", "Stream Deck plugin"),
    mcp_url=mcp_url,
    mcp_timeout=30,
    session_timeout=300,
    discovery_timeout=5.0,
    launch_on_startup=mcp_config.get("launch_on_startup", True)
)

# ============================================================================
# DISCOVERY FUNCTION - Called at startup and on rediscover()
# ============================================================================
# Global: Track discovered actions for auto-retry
# ============================================================================
_discovered_action_names: set = set()

# ============================================================================
@plugin.discoverer
def discover_stream_deck_actions(mcp: MCPClient) -> List[FunctionDef]:
    """
    Discover Stream Deck actions from the MCP server.
    
    This is called automatically at startup by MCPPlugin.
    Returns a list of FunctionDef objects that become plugin commands.
    
    Note: No utility functions exposed - discovery/refresh happens automatically.
    """
    global _discovered_action_names
    logger.info("Discovering Stream Deck actions...")
    
    functions = []
    _discovered_action_names = set()  # Reset tracking
    
    # =========================================================================
    # COMPREHENSIVE DISCOVERY - Using original working approach
    # 
    # The Stream Deck MCP server exposes tools via tools/list
    # The main tool is 'get_executable_actions' which returns all actions
    # Response format: {"structuredContent": {"actions": [...]}}
    # =========================================================================
    
    logger.info("=" * 60)
    logger.info("STREAM DECK DISCOVERY START")
    logger.info("=" * 60)
    
    # =========================================================================
    # Step 1: List available tools from the MCP server
    # =========================================================================
    logger.info("Step 1: Listing available MCP tools (tools/list)...")
    
    try:
        tools = mcp.list_tools()
        logger.info(f"Found {len(tools)} tools from MCP server:")
        for tool in tools:
            name = tool.get('name', 'unknown')
            desc = tool.get('description', 'no description')
            schema = tool.get('inputSchema', {})
            logger.info(f"  Tool: '{name}'")
            logger.info(f"    Description: {desc}")
            if schema.get('properties'):
                logger.info(f"    Parameters: {list(schema['properties'].keys())}")
    except Exception as e:
        logger.error(f"Failed to list tools: {e}")
        tools = []
    
    tool_names = [t.get('name', '') for t in tools]
    actions = []
    
    # =========================================================================
    # Step 2: Call get_executable_actions with RAW response logging
    # This is the primary way to discover Stream Deck actions
    # =========================================================================
    logger.info("Step 2: Calling 'get_executable_actions'...")
    
    if 'get_executable_actions' in tool_names:
        logger.info("  Tool 'get_executable_actions' found in tool list")
    else:
        logger.warning("  Tool 'get_executable_actions' NOT in tool list, trying anyway...")
    
    try:
        # Call the tool and log EVERYTHING
        raw_result = mcp.call_tool("get_executable_actions")
        
        # Log the raw result type and content
        logger.info(f"  Raw result type: {type(raw_result).__name__}")
        logger.info(f"  Raw result: {json.dumps(raw_result, indent=2) if isinstance(raw_result, dict) else str(raw_result)}")
        
        # Extract actions - try multiple paths
        if isinstance(raw_result, dict):
            # Path 1: Direct 'actions' key (SDK extracts structuredContent)
            if 'actions' in raw_result:
                actions = raw_result['actions']
                logger.info(f"  Found 'actions' key with {len(actions)} items")
            
            # Path 2: Nested in 'structuredContent' (in case SDK didn't extract)
            elif 'structuredContent' in raw_result:
                structured = raw_result['structuredContent']
                if isinstance(structured, dict) and 'actions' in structured:
                    actions = structured['actions']
                    logger.info(f"  Found 'structuredContent.actions' with {len(actions)} items")
            
            # Path 3: Try 'content' array (text/json format)
            elif 'content' in raw_result:
                for item in raw_result.get('content', []):
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text = item.get('text', '')
                        logger.info(f"  Parsing content text: {text[:200]}...")
                        try:
                            data = json.loads(text)
                            if isinstance(data, dict) and 'actions' in data:
                                actions = data['actions']
                                logger.info(f"  Parsed {len(actions)} actions from content text")
                                break
                        except json.JSONDecodeError as e:
                            logger.warning(f"  Failed to parse content text: {e}")
            
            # Log if no actions found but response had data
            if not actions:
                logger.warning(f"  No 'actions' found in response. Keys: {list(raw_result.keys())}")
        else:
            logger.warning(f"  Unexpected result type: {type(raw_result)}")
            
    except Exception as e:
        logger.error(f"  get_executable_actions failed: {e}", exc_info=True)
    
    # =========================================================================
    # Step 3: Try other discovery tools if no actions found
    # =========================================================================
    if len(actions) == 0:
        logger.info("Step 3: Trying alternative tools...")
        
        other_tools = [
            ('get_devices', 'devices'),
            ('get_plugins', 'plugins'), 
            ('get_profiles', 'profiles'),
            ('get_actions', 'actions'),
            ('list_actions', 'actions'),
        ]
        
        for tool_name, key in other_tools:
            if tool_name in tool_names:
                logger.info(f"  Trying '{tool_name}'...")
                try:
                    result = mcp.call_tool(tool_name)
                    logger.info(f"    Response: {json.dumps(result, indent=4) if isinstance(result, dict) else str(result)}")
                    
                    if isinstance(result, dict) and key in result:
                        data = result[key]
                        logger.info(f"    Found '{key}' with {len(data) if isinstance(data, list) else 'N/A'} items")
                except Exception as e:
                    logger.warning(f"    {tool_name} failed: {e}")
    
    # =========================================================================
    # Log final summary
    # =========================================================================
    logger.info("=" * 60)
    logger.info(f"DISCOVERY COMPLETE:")
    logger.info(f"  MCP tools available: {len(tools)}")
    logger.info(f"  Actions discovered: {len(actions)}")
    if actions:
        for i, action in enumerate(actions[:5]):
            title = action.get('title', action.get('name', 'Unknown'))
            action_id = action.get('id', 'no-id')
            logger.info(f"    {i+1}. '{title}' (id={action_id})")
        if len(actions) > 5:
            logger.info(f"    ... and {len(actions) - 5} more")
    logger.info("=" * 60)
    
    seen_names = {}
    
    for action in actions:
        action_id = action.get("id", "")
        if not action_id:
            continue
        
        # Extract action info from the nested description object
        # Structure: {"id": "...", "description": {"name": "Play Audio", "description": "..."}, ...}
        desc_obj = action.get("description", {})
        action_type = desc_obj.get("name", "")        # e.g., "Play Audio", "Website"
        action_desc = desc_obj.get("description", "") # e.g., "Play a sound bite..."
        title = action.get("title", "")               # User-configured title (may be empty)
        plugin_id = action.get("pluginId", "")        # e.g., "com.elgato.streamdeck.soundboard"
        
        # Use title if user configured one, otherwise use action_type from description.name
        display_name = title if title else action_type
        if not display_name:
            display_name = f"action_{action_id[:8]}"  # Last resort: use part of ID
        
        logger.info(f"Processing action: title='{title}', action_type='{action_type}', display_name='{display_name}'")
        
        # Generate unique function name from display_name
        func_name = sanitize_name(f"streamdeck_{display_name}")
        
        # Handle duplicates
        if func_name in seen_names:
            seen_names[func_name] += 1
            func_name = f"{func_name}_{seen_names[func_name]}"
        else:
            seen_names[func_name] = 1
        
        # Build description
        # e.g., "Execute 'Play Audio' on Stream Deck - Play a sound bite, audio effect or music clip"
        description = f"Execute '{display_name}' on Stream Deck"
        if title and action_type and title != action_type:
            # User has a custom title different from action type
            description += f" ({action_type})"
        if action_desc:
            description += f" - {action_desc}"
        
        # Build tags for better LLM matching
        tags = ["stream-deck", "streamdeck", "execute"]
        if display_name:
            tags.append(display_name.lower().replace(" ", "-"))
        if action_type and action_type.lower() != display_name.lower():
            tags.append(action_type.lower().replace(" ", "-"))
        if plugin_id:
            # Extract short plugin name from ID like "com.elgato.streamdeck.soundboard" -> "soundboard"
            short_plugin = plugin_id.split(".")[-1] if "." in plugin_id else plugin_id
            tags.append(short_plugin.lower())
        
        # Create executor that captures action_id and display_name
        # Includes auto-retry: if execution fails, refresh and retry once
        def make_executor(aid: str, aname: str):
            def executor():
                logger.info(f"Executing action: {aname} (id={aid})")
                plugin.stream(f"Executing **{aname}**...\n")
                
                try:
                    result = mcp.call_tool("execute_action", {"id": aid})
                    
                    success = result.get("success", True) if isinstance(result, dict) else True
                    if success:
                        return f"**{aname}** executed successfully."
                    else:
                        msg = result.get("message", "Unknown error") if isinstance(result, dict) else str(result)
                        logger.warning(f"Action failed: {msg}, will NOT auto-retry (action exists)")
                        return f"Failed to execute {aname}: {msg}"
                        
                except Exception as e:
                    logger.error(f"Action execution error: {e}")
                    # Try to refresh and retry once
                    logger.info("Attempting auto-refresh after error...")
                    plugin.stream("Connection issue detected, refreshing...\n")
                    
                    try:
                        if plugin.refresh_session():
                            plugin.stream("Retrying...\n")
                            result = mcp.call_tool("execute_action", {"id": aid})
                            success = result.get("success", True) if isinstance(result, dict) else True
                            if success:
                                return f"**{aname}** executed successfully (after reconnect)."
                    except Exception as retry_error:
                        logger.error(f"Retry also failed: {retry_error}")
                    
                    return f"Failed to execute {aname}: Connection error. Please try again."
            return executor
        
        functions.append(FunctionDef(
            name=func_name,
            description=description,
            tags=tags,
            executor=make_executor(action_id, display_name)
        ))
        
        # Track discovered action names for auto-retry
        _discovered_action_names.add(func_name)
        
        logger.info(f"Registered: {func_name} -> '{display_name}' (type={action_type})")
    
    return functions

# ============================================================================
# INTERNAL HELPERS (not exposed as commands)
# ============================================================================

def _internal_refresh_and_rediscover() -> int:
    """
    Internal: Refresh session and rediscover actions.
    Called automatically when an action is not found.
    
    Returns: Number of actions discovered
    """
    global _discovered_action_names
    
    logger.info("Auto-refresh: Refreshing session and rediscovering actions...")
    
    try:
        if not plugin.refresh_session():
            logger.error("Auto-refresh: Failed to refresh session")
            return 0
        
        count = plugin.rediscover()
        logger.info(f"Auto-refresh: Discovered {count} actions")
        return count
        
    except Exception as e:
        logger.error(f"Auto-refresh failed: {e}")
        return 0


@plugin.command("on_input")
def on_input(content: str):
    """Handle follow-up user input."""
    content = content.strip()
    
    if content.lower() in ["exit", "quit", "bye"]:
        plugin.set_keep_session(False)
        return "Goodbye."
    
    plugin.set_keep_session(True)
    return "What Stream Deck action would you like to execute?"


# ============================================================================
# MAIN
# ============================================================================
logger.info(f"Initializing Stream Deck plugin v{manifest.get('version', '2.0.0')}...")
logger.info(f"MCP URL: {mcp_url}")

if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin...")
    plugin.run()  # Auto-discovers at startup via MCPPlugin
