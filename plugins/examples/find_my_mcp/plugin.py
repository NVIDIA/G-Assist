"""
FindMyMCP Plugin for G-Assist.

This plugin discovers and interacts with MCP (Model Context Protocol) servers,
and can generate standalone G-Assist plugins to bridge to them.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import sys
from ctypes import byref, windll, wintypes, create_string_buffer, GetLastError
from typing import Any, Dict, Optional, List

# -----------------------------------------------------------------------------
# Paths & persistent state
# -----------------------------------------------------------------------------

PLUGIN_NAME = "find_my_mcp"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", ".")
PLUGIN_DIR = os.path.join(
    PROGRAM_DATA, "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
PLUGINS_ROOT_DIR = os.path.dirname(PLUGIN_DIR)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

DEFAULT_CONFIG: Dict[str, Any] = {
    "default_timeout": 30,
    "features": {
        "enable_passthrough": False,
        "use_setup_wizard": True,
    },
    "mcp_servers": {
        # Example entries
        # "filesystem": {
        #     "command": "npx",
        #     "args": ["-y", "@modelcontextprotocol/server-filesystem", "."]
        # }
    }
}

STATE: Dict[str, Any] = {
    "config": DEFAULT_CONFIG.copy(),
    "awaiting_input": False,
    "heartbeat_active": False,
    "heartbeat_thread": None,
    "wizard_active": False,
}

# -----------------------------------------------------------------------------
# MCP Bridge Template
# -----------------------------------------------------------------------------

MCP_BRIDGE_TEMPLATE = r'''"""
Auto-generated MCP Bridge Plugin for G-Assist.
Target Server: {server_name}
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
import sys
from ctypes import byref, windll, wintypes, create_string_buffer, GetLastError
from typing import Any, Dict, Optional, List

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

PLUGIN_NAME = "{plugin_name}"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", ".")
PLUGIN_DIR = os.path.join(
    PROGRAM_DATA, "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{{PLUGIN_NAME}}.log")

# Default config is populated at generation time
DEFAULT_CONFIG = {default_config}

STATE = {{
    "config": DEFAULT_CONFIG.copy(),
    "heartbeat_active": False,
    "heartbeat_thread": None,
}}

# -----------------------------------------------------------------------------
# Logging / IO helpers (Standard G-Assist)
# -----------------------------------------------------------------------------

def ensure_directories() -> None:
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

def load_config() -> Dict[str, Any]:
    ensure_directories()
    if not os.path.isfile(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    STATE["config"] = data
    return data

def save_config(data: Dict[str, Any]) -> None:
    ensure_directories()
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    STATE["config"] = data

def read_command() -> Optional[Dict[str, Any]]:
    STD_INPUT_HANDLE = -10
    pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
    buffer = []
    while True:
        chunk = create_string_buffer(4096)
        bytes_read = wintypes.DWORD()
        success = windll.kernel32.ReadFile(pipe, chunk, len(chunk), byref(bytes_read), None)
        if not success: return None
        if bytes_read.value == 0:
            time.sleep(0.01)
            continue
        buffer.append(chunk.value[: bytes_read.value].decode("utf-8"))
        if bytes_read.value < len(chunk): break
    payload = "".join(buffer)
    if payload.endswith("<<END>>"): payload = payload[: -len("<<END>>")]
    try:
        return json.loads(payload.encode("utf-8").decode("raw_unicode_escape"))
    except json.JSONDecodeError:
        return None

def write_response(response: Dict[str, Any]) -> None:
    STD_OUTPUT_HANDLE = -11
    pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    payload = (json.dumps(response) + "<<END>>").encode("utf-8")
    bytes_written = wintypes.DWORD()
    windll.kernel32.WriteFile(pipe, payload, len(payload), byref(bytes_written), None)

def start_heartbeat(interval: int = 5) -> None:
    STATE["heartbeat_active"] = True
    def loop():
        while STATE["heartbeat_active"]:
            write_response({{"type": "heartbeat", "timestamp": time.time()}})
            time.sleep(interval)
    thread = threading.Thread(target=loop, daemon=True)
    STATE["heartbeat_thread"] = thread
    thread.start()

def stop_heartbeat() -> None:
    STATE["heartbeat_active"] = False

def generate_success_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {{"success": True, "message": message, "awaiting_input": awaiting_input}}

def generate_failure_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {{"success": False, "message": message, "awaiting_input": awaiting_input}}

# -----------------------------------------------------------------------------
# MCP Client Logic
# -----------------------------------------------------------------------------

class McpClient:
    def __init__(self, command: str, args: List[str]):
        self.command = command
        self.args = args
        self.process = None
        self.msg_id = 0

    def start(self):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        self.process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=0 
        )
        # Initialize MCP
        self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "g-assist-bridge", "version": "1.0"}
        })
        self.send_notification("notifications/initialized", {})

    def stop(self):
        if self.process:
            self.process.terminate()
            self.process = None

    def send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        if not self.process: raise RuntimeError("MCP server not started")
        
        self.msg_id += 1
        payload = {"jsonrpc": "2.0", "id": self.msg_id, "method": method}
        if params is not None: payload["params"] = params
        
        msg_str = json.dumps(payload) + "\n"
        self.process.stdin.write(msg_str)
        self.process.stdin.flush()
        logging.info(f"[MCP] Sent: {msg_str.strip()}")

        # Read response (blocking, simple implementation)
        while True:
            line = self.process.stdout.readline()
            if not line: raise RuntimeError("MCP server closed connection")
            logging.info(f"[MCP] Recv: {line.strip()}")
            try:
                data = json.loads(line)
                if data.get("id") == self.msg_id:
                    if "error" in data:
                        raise RuntimeError(f"MCP Error: {data['error']['message']}")
                    return data.get("result")
            except json.JSONDecodeError:
                continue

    def send_notification(self, method: str, params: Optional[Dict] = None):
        if not self.process: return
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None: payload["params"] = params
        msg_str = json.dumps(payload) + "\n"
        self.process.stdin.write(msg_str)
        self.process.stdin.flush()

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        return self.send_request("tools/call", {"name": name, "arguments": arguments})

# -----------------------------------------------------------------------------
# Main Handler
# -----------------------------------------------------------------------------

MCP_CLIENT = None

def handle_initialize(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    global MCP_CLIENT
    config = load_config()
    
    start_heartbeat()
    
    # Start MCP Server
    cmd = config["mcp_server"]["command"]
    args = config["mcp_server"]["args"]
    try:
        MCP_CLIENT = McpClient(cmd, args)
        MCP_CLIENT.start()
        return generate_success_response(f"Bridge to {PLUGIN_NAME} established.")
    except Exception as e:
        logging.exception("Failed to start MCP server")
        return generate_failure_response(f"Failed to connect to MCP server: {str(e)}")

def handle_tool_call(command: Dict[str, Any]) -> Dict[str, Any]:
    tool_call = command["tool_calls"][0]
    func_name = tool_call.get("func")
    params = tool_call.get("params", {}) or {}

    if func_name == "initialize":
        return handle_initialize(tool_call)

    if not MCP_CLIENT:
        return generate_failure_response("Plugin not initialized or MCP server down.")

    # Forward to MCP
    try:
        result = MCP_CLIENT.call_tool(func_name, params)
        # Format result for G-Assist
        content = result.get("content", [])
        text_output = ""
        for item in content:
            if item.get("type") == "text":
                text_output += item.get("text", "") + "\n"
        
        return generate_success_response(text_output.strip())
    except Exception as e:
        return generate_failure_response(f"MCP Tool Error: {str(e)}")

def main() -> int:
    ensure_directories()
    logging.info(f"Launching {PLUGIN_NAME}")
    try:
        while True:
            command = read_command()
            if not command: continue
            if "tool_calls" in command:
                write_response(handle_tool_call(command))
            elif command.get("msg_type") == "user_input":
                write_response(generate_success_response("Input received", awaiting_input=False))
    finally:
        stop_heartbeat()
        if MCP_CLIENT: MCP_CLIENT.stop()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''

# -----------------------------------------------------------------------------
# Logging / IO helpers
# -----------------------------------------------------------------------------

def ensure_directories() -> None:
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

def load_config() -> Dict[str, Any]:
    ensure_directories()
    if not os.path.isfile(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    STATE["config"] = data
    return data

def save_config(data: Dict[str, Any]) -> None:
    ensure_directories()
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    STATE["config"] = data

def validate_config(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    return True, None

def build_setup_instructions(error: Optional[str] = None) -> str:
    header = f"[{PLUGIN_NAME.upper()} SETUP]\n========================\n"
    error_section = f"⚠️ {error}\n\n" if error else ""
    body = (
        f"1. Open config file:\n   {CONFIG_FILE}\n"
        "2. Add your MCP servers to the 'mcp_servers' list.\n"
        "3. Save the file.\n"
        "4. Return here and type 'done'.\n"
    )
    return header + error_section + body

def config_needs_setup(config: Dict[str, Any], valid: bool) -> bool:
    return config["features"].get("use_setup_wizard", False) and not valid

def start_setup_wizard(error: Optional[str]) -> Dict[str, Any]:
    STATE["wizard_active"] = True
    STATE["awaiting_input"] = True
    instructions = build_setup_instructions(error)
    return generate_success_response(instructions, awaiting_input=True)

def read_command() -> Optional[Dict[str, Any]]:
    STD_INPUT_HANDLE = -10
    pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
    buffer = []
    while True:
        chunk = create_string_buffer(4096)
        bytes_read = wintypes.DWORD()
        success = windll.kernel32.ReadFile(pipe, chunk, len(chunk), byref(bytes_read), None)
        if not success: return None
        if bytes_read.value == 0:
            time.sleep(0.01)
            continue
        buffer.append(chunk.value[: bytes_read.value].decode("utf-8"))
        if bytes_read.value < len(chunk): break
    payload = "".join(buffer)
    if payload.endswith("<<END>>"): payload = payload[: -len("<<END>>")]
    try:
        return json.loads(payload.encode("utf-8").decode("raw_unicode_escape"))
    except json.JSONDecodeError:
        return None

def write_response(response: Dict[str, Any]) -> None:
    STD_OUTPUT_HANDLE = -11
    pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    payload = (json.dumps(response) + "<<END>>").encode("utf-8")
    bytes_written = wintypes.DWORD()
    windll.kernel32.WriteFile(pipe, payload, len(payload), byref(bytes_written), None)
    logging.info("[PIPE] Sent %s", response.get("type", "response"))

def start_heartbeat(interval: int = 5) -> None:
    stop_heartbeat()
    STATE["heartbeat_active"] = True
    def loop():
        while STATE["heartbeat_active"]:
            write_response({"type": "heartbeat", "timestamp": time.time()})
            time.sleep(interval)
    thread = threading.Thread(target=loop, daemon=True)
    STATE["heartbeat_thread"] = thread
    thread.start()

def stop_heartbeat() -> None:
    STATE["heartbeat_active"] = False
    thread = STATE.get("heartbeat_thread")
    if thread and thread.is_alive(): thread.join(timeout=1)

def generate_success_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {"success": True, "message": message, "awaiting_input": awaiting_input}

def generate_failure_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {"success": False, "message": message, "awaiting_input": awaiting_input}

# -----------------------------------------------------------------------------
# Simple MCP Client
# -----------------------------------------------------------------------------

class McpClient:
    def __init__(self, command: str, args: List[str]):
        self.command = command
        self.args = args
        self.process = None
        self.msg_id = 0

    def start(self):
        # Use shell=True on Windows if needed for path resolution, but explicit is safer
        # Assuming command is in PATH or full path
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        
        logging.info(f"Starting MCP process: {self.command} {self.args}")
        self.process = subprocess.Popen(
            [self.command] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            bufsize=0 
        )
        
        # Handshake
        self.send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "find-my-mcp", "version": "1.0"}
        })
        self.send_notification("notifications/initialized", {})

    def stop(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except:
                self.process.kill()
            self.process = None

    def send_request(self, method: str, params: Optional[Dict] = None) -> Any:
        if not self.process: raise RuntimeError("MCP server not started")
        
        self.msg_id += 1
        payload = {"jsonrpc": "2.0", "id": self.msg_id, "method": method}
        if params is not None: payload["params"] = params
        
        msg_str = json.dumps(payload) + "\n"
        self.process.stdin.write(msg_str)
        self.process.stdin.flush()

        # Read loop (simplistic)
        start_time = time.time()
        while (time.time() - start_time) < 10: # 10s timeout
            line = self.process.stdout.readline()
            if not line: raise RuntimeError("MCP server closed connection")
            try:
                data = json.loads(line)
                if data.get("id") == self.msg_id:
                    if "error" in data:
                        raise RuntimeError(f"MCP Error: {data['error']['message']}")
                    return data.get("result")
            except json.JSONDecodeError:
                continue
        raise TimeoutError("MCP request timed out")

    def send_notification(self, method: str, params: Optional[Dict] = None):
        if not self.process: return
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None: payload["params"] = params
        msg_str = json.dumps(payload) + "\n"
        self.process.stdin.write(msg_str)
        self.process.stdin.flush()

# -----------------------------------------------------------------------------
# Plugin Logic
# -----------------------------------------------------------------------------

def handle_initialize(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    if config_needs_setup(config, True):
        return start_setup_wizard(None)
        
    start_heartbeat(interval=15)
    
    server_count = len(config.get("mcp_servers", {}))
    return generate_success_response(
        f"FindMyMCP ready. Configured to search {server_count} servers.\n"
        "Use 'scan_mcp_servers' to list them, or 'create_mcp_plugin' to generate bridges.",
        awaiting_input=False
    )

def handle_scan_mcp_servers(params: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    servers = config.get("mcp_servers", {})
    if not servers:
        return generate_success_response("No MCP servers configured in config.json.")
    
    lines = ["Configured MCP Servers:"]
    for name, details in servers.items():
        cmd = f"{details.get('command')} {' '.join(details.get('args', []))}"
        lines.append(f"- {name}: {cmd}")
    
    return generate_success_response("\n".join(lines))

def handle_inspect_mcp_server(params: Dict[str, Any]) -> Dict[str, Any]:
    server_name = params.get("server_name")
    config = load_config()
    server_conf = config.get("mcp_servers", {}).get(server_name)
    
    if not server_conf:
        return generate_failure_response(f"Server '{server_name}' not found in config.")

    try:
        client = McpClient(server_conf["command"], server_conf["args"])
        client.start()
        
        tools_result = client.send_request("tools/list", {})
        tools = tools_result.get("tools", [])
        
        client.stop()
        
        if not tools:
            return generate_success_response(f"Server '{server_name}' connected but reported no tools.")
            
        lines = [f"Tools found on '{server_name}':"]
        for t in tools:
            lines.append(f"- {t['name']}: {t.get('description', 'No description')}")
            
        return generate_success_response("\n".join(lines))
        
    except Exception as e:
        logging.exception(f"Failed to inspect {server_name}")
        return generate_failure_response(f"Inspection failed: {str(e)}")

def handle_create_mcp_plugin(params: Dict[str, Any]) -> Dict[str, Any]:
    server_name = params.get("server_name")
    plugin_name = params.get("plugin_name")
    
    config = load_config()
    server_conf = config.get("mcp_servers", {}).get(server_name)
    
    if not server_conf:
        return generate_failure_response(f"Server '{server_name}' not found in config.")
    
    if not plugin_name:
        plugin_name = f"mcp_{server_name}"

    # 1. Inspect to get tools
    try:
        client = McpClient(server_conf["command"], server_conf["args"])
        client.start()
        tools_result = client.send_request("tools/list", {})
        tools = tools_result.get("tools", [])
        client.stop()
    except Exception as e:
        return generate_failure_response(f"Could not connect to server to generate manifest: {str(e)}")

    # 2. Generate Manifest
    functions = []
    for t in tools:
        fn = {
            "name": t["name"],
            "description": t.get("description", ""),
            "tags": ["mcp", server_name, t["name"]],
            "properties": t.get("inputSchema", {}).get("properties", {})
        }
        functions.append(fn)

    manifest = {
        "manifestVersion": 1,
        "executable": f"{plugin_name}.exe", # Placeholder
        "persistent": True,
        "functions": functions + [{"name": "initialize", "description": "Initializes the plugin"}]
    }

    # 3. Create Directory
    target_dir = os.path.join(PLUGINS_ROOT_DIR, plugin_name)
    if os.path.exists(target_dir):
        return generate_failure_response(f"Plugin directory '{plugin_name}' already exists.")
    
    os.makedirs(target_dir)

    # 4. Write files
    # Manifest
    with open(os.path.join(target_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=4)
    
    # Config (Generated)
    generated_config = {
        "api_base_url": config.get("api_base_url", ""),
        "api_key": config.get("api_key", ""),
        "default_timeout": 60,
        "features": {"enable_passthrough": False, "use_setup_wizard": False},
        "mcp_server": server_conf
    }
    
    # Plugin Code
    code = MCP_BRIDGE_TEMPLATE.format(
        server_name=server_name,
        plugin_name=plugin_name,
        default_config=json.dumps(generated_config, indent=4)
    )
    with open(os.path.join(target_dir, "plugin.py"), "w", encoding="utf-8") as f:
        f.write(code)
        
    # Batch file for easy testing/building
    with open(os.path.join(target_dir, "build.bat"), "w", encoding="utf-8") as f:
        f.write(f"""@echo off
set PLUGIN_NAME={plugin_name}
echo Building %PLUGIN_NAME%...
REM Add your pyinstaller command here
echo Done.
""")

    return generate_success_response(
        f"Plugin '{plugin_name}' created successfully at:\n{target_dir}\n\n"
        "You must restart the Engine (or trigger a rescan) to load it."
    )

def handle_user_input(message: Dict[str, Any]) -> Dict[str, Any]:
    content = message.get("content", "").strip()
    if STATE["wizard_active"]:
        load_config()
        STATE["wizard_active"] = False
        STATE["awaiting_input"] = False
        return generate_success_response("Setup complete!", awaiting_input=False)
    
    return generate_success_response("Unexpected input.", awaiting_input=False)

def handle_tool_call(command: Dict[str, Any]) -> Dict[str, Any]:
    tool_call = command["tool_calls"][0]
    func_name = tool_call.get("func")
    params = tool_call.get("params", {}) or {}

    if func_name == "initialize":
        return handle_initialize(tool_call)
    elif func_name == "scan_mcp_servers":
        return handle_scan_mcp_servers(params)
    elif func_name == "inspect_mcp_server":
        return handle_inspect_mcp_server(params)
    elif func_name == "create_mcp_plugin":
        return handle_create_mcp_plugin(params)

    return generate_failure_response(f"Unknown function: {func_name}")

def main() -> int:
    ensure_directories()
    logging.info(f"Launching {PLUGIN_NAME}")
    try:
        while True:
            command = read_command()
            if not command: continue
            
            if "tool_calls" in command:
                write_response(handle_tool_call(command))
            elif command.get("msg_type") == "user_input":
                write_response(handle_user_input(command))
    finally:
        stop_heartbeat()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

