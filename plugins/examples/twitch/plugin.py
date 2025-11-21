"""Twitch Plugin for NVIDIA G-Assist Platform.

This plugin provides functionality to interact with the Twitch API,
specifically for checking stream status of Twitch users. It implements
a Windows pipe-based communication protocol for receiving commands and
sending responses.

Configuration:
    Required configuration in config.json:
    {
        "TWITCH_CLIENT_ID": "your_client_id_here",
        "TWITCH_CLIENT_SECRET": "your_client_secret_here"
    }

    Config location: %PROGRAMDATA%\\NVIDIA Corporation\\nvtopps\\rise\\plugins\\twitch\\config.json
    Log location: %PROGRAMDATA%\\NVIDIA Corporation\\nvtopps\\rise\\plugins\\twitch\\twitch-plugin.log

Commands Supported:
    - initialize: Initialize the plugin
    - check_twitch_live_status: Check if a Twitch user is streaming
    - shutdown: Gracefully shutdown the plugin

Dependencies:
    - requests: For making HTTP requests to Twitch API
    - ctypes: For Windows pipe communication
"""

import json
import logging
import os
import sys
import webbrowser
from typing import Optional, Dict, Any
import requests
from ctypes import byref, windll, wintypes
import threading
import time

# Type definitions
Response = Dict[str, Any]
"""Type alias for response dictionary containing 'success' and optional 'message'."""

# Constants
STD_INPUT_HANDLE = -10
"""Windows standard input handle constant."""

STD_OUTPUT_HANDLE = -11
"""Windows standard output handle constant."""

BUFFER_SIZE = 4096
"""Size of buffer for reading from pipe in bytes."""

PLUGIN_NAME = "twitch"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", ".")
PLUGIN_DIR = os.path.join(
    PROGRAM_DATA,
    "NVIDIA Corporation",
    "nvtopps",
    "rise",
    "plugins",
    PLUGIN_NAME,
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
STATE_FILE = os.path.join(PLUGIN_DIR, "setup_state.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

DEFAULT_CONFIG: Dict[str, Any] = {
    "TWITCH_CLIENT_ID": "",
    "TWITCH_CLIENT_SECRET": "",
    "default_timeout": 10,
    "features": {
        "enable_passthrough": False,
        "stream_chunk_size": 240,
        "use_setup_wizard": True,
    },
}

STATE: Dict[str, Any] = {
    "config": DEFAULT_CONFIG.copy(),
    "awaiting_input": False,
    "wizard_active": False,
    "heartbeat_active": False,
    "heartbeat_thread": None,
    "heartbeat_message": "",
}

# Maintain backward-compatible global alias
config: Dict[str, str] = STATE["config"]
"""Loaded configuration containing Twitch API credentials."""

# Twitch API endpoints
TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/token"
"""Twitch OAuth token endpoint for client credentials flow."""

TWITCH_STREAM_URL = "https://api.twitch.tv/helix/streams"
"""Twitch API endpoint for checking stream status."""

# Global state
oauth_token: Optional[str] = None
"""Cached OAuth token for Twitch API requests."""

# Helpers for filesystem/config
def ensure_directories() -> None:
    os.makedirs(PLUGIN_DIR, exist_ok=True)


def setup_logging() -> None:
    ensure_directories()
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def apply_config_defaults(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = DEFAULT_CONFIG.copy()
    merged.update({k: v for k, v in raw.items() if k != "features"})
    merged_features = DEFAULT_CONFIG["features"].copy()
    merged_features.update(raw.get("features", {}))
    merged["features"] = merged_features
    return merged


def load_config() -> Dict[str, Any]:
    ensure_directories()
    if not os.path.isfile(CONFIG_FILE):
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        data = DEFAULT_CONFIG.copy()

    merged = apply_config_defaults(data)
    STATE["config"] = merged
    global config
    config = STATE["config"]
    return STATE["config"]


def save_config(config_data: Dict[str, Any]) -> None:
    ensure_directories()
    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config_data, file, indent=2)
    STATE["config"] = config_data
    global config
    config = STATE["config"]
    logging.info("[CONFIG] Saved configuration successfully")


def validate_config(cfg: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    if not cfg.get("TWITCH_CLIENT_ID"):
        return False, "TWITCH_CLIENT_ID is missing in config.json"
    if not cfg.get("TWITCH_CLIENT_SECRET"):
        return False, "TWITCH_CLIENT_SECRET is missing in config.json"
    return True, None


def build_setup_instructions(error: Optional[str] = None) -> str:
    header = "[TWITCH SETUP]\n========================\n"
    error_section = f"⚠️ {error}\n\n" if error else ""
    body = (
        f"1. Open config file:\n   {CONFIG_FILE}\n"
        "2. Paste your Twitch Client ID and Client Secret.\n"
        "3. Save the file and return here with 'done'.\n"
    )
    return header + error_section + body


def config_needs_setup(cfg: Dict[str, Any], valid: bool) -> bool:
    return cfg.get("features", {}).get("use_setup_wizard", True) and not valid


# Setup state machine
class SetupState:
    """Persistent setup state machine for plugin configuration"""
    UNCONFIGURED = "unconfigured"                    # No app credentials
    WAITING_APP_CREATION = "waiting_app_creation"    # User creating Twitch app
    WAITING_CREDENTIALS = "waiting_credentials"       # User entering credentials
    CONFIGURED = "configured"                         # Fully set up
    
    def __init__(self, state_file):
        self.state_file = state_file
        self.current_state = self.UNCONFIGURED
        self.completed_steps = []
        self.last_error = None
        self.retry_count = 0
        self.timestamp = None
        self.load()
    
    def load(self):
        """Load state from disk"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self.current_state = data.get('current_state', self.UNCONFIGURED)
                    self.completed_steps = data.get('completed_steps', [])
                    self.last_error = data.get('last_error')
                    self.retry_count = data.get('retry_count', 0)
                    self.timestamp = data.get('timestamp')
                    logging.info(f"[STATE] Loaded state: {self.current_state}")
        except Exception as e:
            logging.error(f"[STATE] Error loading state: {e}")
    
    def save(self):
        """Save state to disk"""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            data = {
                'current_state': self.current_state,
                'completed_steps': self.completed_steps,
                'last_error': self.last_error,
                'retry_count': self.retry_count,
                'timestamp': time.time()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"[STATE] Saved state: {self.current_state}")
        except Exception as e:
            logging.error(f"[STATE] Error saving state: {e}")
    
    def advance(self, new_state, completed_step=None):
        """Advance to new state"""
        self.current_state = new_state
        if completed_step and completed_step not in self.completed_steps:
            self.completed_steps.append(completed_step)
        self.retry_count = 0
        self.last_error = None
        self.save()
    
    def record_error(self, error):
        """Record error and increment retry count"""
        self.last_error = error
        self.retry_count += 1
        self.save()
    
    def reset(self):
        """Reset to unconfigured state"""
        self.current_state = self.UNCONFIGURED
        self.completed_steps = []
        self.last_error = None
        self.retry_count = 0
        self.save()

# Global setup state
SETUP_STATE = None

# Helper response generators
def generate_message_response(message: str, awaiting_input: bool = False) -> dict:
    """
    Generate a message response.
    
    PHASE 3: Tethered Mode Protocol
    - awaiting_input=True: Plugin needs more user interaction, stay in passthrough
    - awaiting_input=False: Plugin is done, exit passthrough mode
    """
    return {
        'success': True,
        'message': message,
        'awaiting_input': awaiting_input
    }

def generate_success_response(body: dict = None, awaiting_input: bool = False) -> dict:
    """Generate a success response with optional data"""
    response = body.copy() if body is not None else dict()
    response['success'] = True
    response['awaiting_input'] = awaiting_input
    return response

def generate_failure_response(body: dict = None) -> dict:
    """Generate a failure response with optional data"""
    response = body.copy() if body is not None else dict()
    response['success'] = False
    response['awaiting_input'] = False
    return response


def start_setup_wizard(error: Optional[str] = None) -> dict:
    STATE["wizard_active"] = True
    STATE["awaiting_input"] = True
    if error:
        send_status_message(build_setup_instructions(error))
    else:
        send_status_message(build_setup_instructions())
    return execute_setup_wizard()


def finalize_response(response: Optional[dict]) -> Optional[dict]:
    if response is None:
        return None
    STATE["awaiting_input"] = response.get("awaiting_input", False)
    if not STATE["awaiting_input"]:
        STATE["wizard_active"] = False
    return response

# PHASE 1: Tethered Mode - Heartbeat and Status Messages
def send_heartbeat(state="ready"):
    """Send silent heartbeat to engine (not visible to user)"""
    try:
        heartbeat_msg = {
            "type": "heartbeat",
            "state": state,
            "timestamp": time.time()
        }
        write_response(heartbeat_msg)
        logging.info(f"[HEARTBEAT] Sent heartbeat: state={state}")
    except Exception as e:
        logging.error(f"[HEARTBEAT] Error: {e}")

def send_status_message(message):
    """Send status update visible to user"""
    try:
        status_msg = {
            "type": "status",
            "message": message
        }
        write_response(status_msg)
        logging.info(f"[STATUS] Sent: {message[:50]}...")
    except Exception as e:
        logging.error(f"[STATUS] Error: {e}")

def send_state_change(new_state):
    """Notify engine of state transition"""
    try:
        state_msg = {
            "type": "state_change",
            "new_state": new_state
        }
        write_response(state_msg)
        logging.info(f"[STATE] Changed to: {new_state}")
    except Exception as e:
        logging.error(f"[STATE] Error: {e}")

def start_continuous_heartbeat(state="ready", interval=5, show_dots=False):
    """
    Start background thread that sends periodic heartbeats.
    
    Args:
        state: Heartbeat state ("onboarding" or "ready")
        interval: Seconds between heartbeats
        show_dots: If True, send visible status dots. If False, send silent heartbeats only.
    """
    stop_continuous_heartbeat()

    STATE["heartbeat_message"] = state
    STATE["heartbeat_active"] = True

    def heartbeat_loop():
        while STATE["heartbeat_active"]:
            time.sleep(interval)
            if STATE["heartbeat_active"]:
                send_heartbeat(STATE["heartbeat_message"])
                if show_dots:
                    send_status_message(".")

    thread = threading.Thread(target=heartbeat_loop, daemon=True)
    STATE["heartbeat_thread"] = thread
    thread.start()
    logging.info(f"[HEARTBEAT] Started continuous heartbeat: state={state}, interval={interval}s, show_dots={show_dots}")

def stop_continuous_heartbeat():
    """Stop background heartbeat thread"""
    STATE["heartbeat_active"] = False
    thread = STATE.get("heartbeat_thread")
    if thread and thread.is_alive():
        thread.join(timeout=1)
    STATE["heartbeat_thread"] = None
    logging.info("[HEARTBEAT] Stopped continuous heartbeat")

def execute_setup_wizard() -> Response:
    """
    Multi-stage setup wizard with persistent state.
    Guides user through Twitch app creation and credential configuration.
    """
    global SETUP_STATE, config
    
    # Initialize state if needed
    if SETUP_STATE is None:
        SETUP_STATE = SetupState(STATE_FILE)
    
    # Check current configuration
    config = load_config()
    client_id = config.get('TWITCH_CLIENT_ID', '')
    client_secret = config.get('TWITCH_CLIENT_SECRET', '')
    
    # Validate credentials
    credentials_valid = (
        client_id and len(client_id) > 20 and
        client_secret and len(client_secret) > 20
    )
    
    # If credentials are valid, verify with API
    if credentials_valid:
        logging.info("[WIZARD] Credentials found, verifying with Twitch API...")
        send_status_message("Verifying Twitch credentials...")
        
        token = get_oauth_token()
        if token:
            SETUP_STATE.advance(SetupState.CONFIGURED, "credentials_verified")
            stop_continuous_heartbeat()
            start_continuous_heartbeat(state="ready", interval=5, show_dots=False)
            send_state_change("ready")
            
            return generate_message_response(
                "✓ Twitch plugin configured successfully!\n\n"
                "You can now check if Twitch users are live streaming.",
                awaiting_input=False
            )
        else:
            # Credentials exist but are invalid
            SETUP_STATE.record_error("Invalid credentials")
            logging.error("[WIZARD] Credentials verification failed")
    
    # Determine current wizard stage based on state
    current_state = SETUP_STATE.current_state
    
    # Stage 1: App Creation Instructions (only if UNCONFIGURED)
    if current_state == SetupState.UNCONFIGURED:
        logging.info("[WIZARD] Stage 1: App Creation")
        
        # Stop any existing heartbeat during setup
        stop_continuous_heartbeat()
        
        # Open Twitch Developer Console
        try:
            webbrowser.open("https://dev.twitch.tv/console/apps")
            logging.info("[WIZARD] Opened Twitch Developer Console in browser")
        except Exception as e:
            logging.error(f"[WIZARD] Failed to open browser: {e}")
        
        SETUP_STATE.advance(SetupState.WAITING_APP_CREATION, "browser_opened")
        
        message = f"""
╔════════════════════════════════════════════════════════════════╗
║           TWITCH PLUGIN - FIRST TIME SETUP (1/2)               ║
╚════════════════════════════════════════════════════════════════╝

Welcome! Let's set up your Twitch app. This takes about 5 minutes.

📋 STEP 1 - Create Twitch App:
   I've opened the Twitch Developer Console in your browser.
   
   1. Log in with your Twitch account
   2. Click "Register Your Application"
   3. Fill in the form:
      • Name: "G-Assist Plugin"
      • OAuth Redirect URLs: "http://localhost"
      • Category: "Application Integration"
   4. Click "Create"

📋 STEP 2 - Get Credentials:
   1. Click "Manage" on your new app
   2. Copy your "Client ID"
   3. Click "New Secret" and copy the client secret
   
   ⚠️  IMPORTANT: Keep your client secret private!

When you have both credentials, send me ANY message (like "ready") to continue!
"""
        
        return generate_message_response(message, awaiting_input=True)
    
    # Stage 1.5: User responded, ready to move to credential entry
    elif current_state == SetupState.WAITING_APP_CREATION:
        logging.info("[WIZARD] User ready - advancing to Stage 2")
        SETUP_STATE.advance(SetupState.WAITING_CREDENTIALS, "user_ready")
        # Fall through to Stage 2
    
    # Stage 2: Credential Entry
    if current_state == SetupState.WAITING_CREDENTIALS or not credentials_valid:
        logging.info("[WIZARD] Stage 2: Credential Entry")
        
        # Open config file for user
        try:
            # Create template config if it doesn't exist
            if not os.path.exists(CONFIG_FILE):
                template_config = {
                    "TWITCH_CLIENT_ID": "",
                    "TWITCH_CLIENT_SECRET": ""
                }
                save_config(template_config)
            
            # Open config file in default editor
            os.startfile(CONFIG_FILE)
            logging.info("[WIZARD] Opened config file for editing")
        except Exception as e:
            logging.error(f"[WIZARD] Failed to open config file: {e}")
        
        SETUP_STATE.advance(SetupState.WAITING_CREDENTIALS, "config_opened")
        
        message = f"""
╔════════════════════════════════════════════════════════════════╗
║           TWITCH PLUGIN - FIRST TIME SETUP (2/2)               ║
╚════════════════════════════════════════════════════════════════╝

Great! Now let's add your credentials.

📝 STEP 3 - Configure Plugin:
   I've opened your config file. Please:
   
   1. Paste your Client ID between the quotes:
      "TWITCH_CLIENT_ID": "YOUR_CLIENT_ID_HERE"
   
   2. Paste your Client Secret between the quotes:
      "TWITCH_CLIENT_SECRET": "YOUR_CLIENT_SECRET_HERE"
   
   3. Save the file (Ctrl+S)
   4. Close the editor

📁 Config file location:
   {CONFIG_FILE}

After saving, send me ANY message (like "done") and I'll verify it!
"""
        
        return generate_message_response(message, awaiting_input=True)
    
    # Fallback (shouldn't reach here)
    return generate_message_response(
        "Setup wizard in progress. Please follow the instructions above.",
        awaiting_input=True
    )

def get_oauth_token() -> Optional[str]:
    """Obtain OAuth token from Twitch API using client credentials flow."""
    global oauth_token
    try:
        response = requests.post(
            TWITCH_OAUTH_URL,
            params={
                "client_id": config.get("TWITCH_CLIENT_ID", ""),
                "client_secret": config.get("TWITCH_CLIENT_SECRET", ""),
                "grant_type": "client_credentials"
            },
            timeout=10
        )
        response_data = response.json()
        if "access_token" in response_data:
            oauth_token = response_data["access_token"]
            logging.info("Successfully obtained OAuth token")
            return oauth_token
        logging.error(f"Failed to get OAuth token: {response_data}")
        return None
    except requests.RequestException as e:
        logging.error(f"Error requesting OAuth token: {e}")
        return None

def generate_response(success: bool, message: Optional[str] = None) -> Response:
    """Generate a standardized response dictionary."""
    response = {'success': success}
    if message:
        response['message'] = message
    return response

def generate_status_update(message: str) -> dict:
    """Generate a status update (not a final response)."""
    return {'status': 'in_progress', 'message': message}

def check_twitch_live_status(params: Dict[str, str], send_status_callback=None) -> Response:
    """Check if a Twitch user is currently live."""
    global oauth_token, SETUP_STATE
    username = params.get("username")
    
    if not username:
        return generate_failure_response({'message': "Missing required parameter: username"})
    
    # Send status update
    if send_status_callback:
        send_status_callback(generate_status_update(f"Checking if {username} is live..."))
    
    if not oauth_token:
        oauth_token = get_oauth_token()
        if not oauth_token:
            # Authentication failed - trigger setup wizard
            logging.error("Authentication failed - credentials may be invalid or missing")
            if SETUP_STATE:
                SETUP_STATE.current_state = SetupState.WAITING_CREDENTIALS
                SETUP_STATE.record_error("Authentication failed")
            return generate_message_response(
                "⚠️ Twitch authentication failed. Let's set up your credentials!\n\n"
                "Please send me any message (like 'setup') to start the configuration wizard.",
                awaiting_input=True
            )
    
    try:
        headers = {
            "Client-ID": config.get("TWITCH_CLIENT_ID", ""),
            "Authorization": f"Bearer {oauth_token}"
        }
        response = requests.get(
            TWITCH_STREAM_URL,
            headers=headers,
            params={"user_login": username},
            timeout=10
        )
        
        # Handle token expiration
        if response.status_code == 401:
            logging.info("OAuth token expired, refreshing...")
            oauth_token = get_oauth_token()
            if oauth_token:
                headers["Authorization"] = f"Bearer {oauth_token}"
                response = requests.get(
                    TWITCH_STREAM_URL,
                    headers=headers,
                    params={"user_login": username},
                    timeout=10
                )
        
        response_data = response.json()

        if "data" in response_data and response_data["data"]:
            stream_info = response_data["data"][0]
            # Strip non-ASCII characters from title and game name
            title = ''.join(char for char in stream_info['title'] if ord(char) < 128)
            game_name = ''.join(char for char in stream_info.get('game_name', 'Unknown') if ord(char) < 128) if stream_info.get('game_name') else 'Unknown'
            
            return generate_success_response({
                'message': (
                    f"{username} is LIVE!\n"
                    f"Title: {title}\n"
                    f"Game: {game_name}\n"
                    f"Viewers: {stream_info['viewer_count']}\n"
                    f"Started At: {stream_info['started_at']}"
                )
            })
        return generate_success_response({'message': f"{username} is OFFLINE"})
    
    except requests.RequestException as e:
        logging.error(f"Error checking Twitch live status: {e}")
        return generate_failure_response({'message': "Failed to check Twitch live status. Please try again."})


def handle_initialize() -> dict:
    load_config()
    return finalize_response(initialize())


def handle_check_twitch_live_status(params: Dict[str, str]) -> dict:
    response = check_twitch_live_status(params, send_status_callback=write_response)
    return finalize_response(response)


def handle_shutdown() -> dict:
    return finalize_response(shutdown())


COMMAND_HANDLER_MAP = {
    "check_twitch_live_status": handle_check_twitch_live_status,
}

def read_command() -> Optional[Dict[str, Any]]:
    """Read command from stdin pipe."""
    try:
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
        chunks = []
        
        while True:
            message_bytes = wintypes.DWORD()
            buffer = bytes(BUFFER_SIZE)
            success = windll.kernel32.ReadFile(
                pipe,
                buffer,
                BUFFER_SIZE,
                byref(message_bytes),
                None
            )

            if not success:
                logging.error('Error reading from command pipe')
                return None

            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            if message_bytes.value < BUFFER_SIZE:
                break

        retval = ''.join(chunks)
        logging.info(f'[PIPE] Read {len(retval)} bytes from pipe')
        return json.loads(retval)
        
    except json.JSONDecodeError:
        logging.error(f'Received invalid JSON: {retval}')
        logging.exception("JSON decoding failed:")
        return None
    except Exception as e:
        logging.error(f'Exception in read_command(): {e}')
        return None


def handle_tool_call(command: Dict[str, Any]) -> dict:
    tool_calls = command.get("tool_calls", [])
    if not tool_calls:
        return generate_failure_response({"message": "No tool call provided."})

    response = None
    for tool_call in tool_calls:
        func = tool_call.get("func")
        params = tool_call.get("params", {}) or {}

        if func == "initialize":
            response = handle_initialize()
        elif func == "shutdown":
            response = handle_shutdown()
        elif func == "twitch_setup":
            response = finalize_response(start_setup_wizard())
        else:
            handler = COMMAND_HANDLER_MAP.get(func)
            if handler is None:
                response = generate_failure_response({"message": f"Unknown function: {func}"})
            else:
                cfg = load_config()
                valid, error = validate_config(cfg)
                if config_needs_setup(cfg, valid) or (SETUP_STATE and SETUP_STATE.current_state != SetupState.CONFIGURED):
                    response = finalize_response(start_setup_wizard(error))
                else:
                    response = handler(params)

        if response is None:
            response = generate_failure_response({"message": "Plugin returned no response."})

    return response


def handle_user_input(message: Dict[str, Any]) -> dict:
    content = (message.get("content") or "").strip()
    cfg = load_config()
    valid, error = validate_config(cfg)
    if config_needs_setup(cfg, valid) or (SETUP_STATE and SETUP_STATE.current_state != SetupState.CONFIGURED):
        return finalize_response(execute_setup_wizard())

    if not STATE.get("awaiting_input") and not STATE.get("wizard_active"):
        return finalize_response(
            generate_message_response("No passthrough session is active.", awaiting_input=False)
        )

    echo = content or "(blank input)"
    return finalize_response(
        generate_message_response(f"Received: {echo}", awaiting_input=True)
    )

def write_response(response: Response) -> None:
    """Write response to stdout pipe."""
    try:
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)
        
        logging.info(f"[PIPE] Writing message: success={response.get('success', 'unknown')}, length={message_len} bytes")
        
        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            byref(bytes_written),
            None
        )
        
        if success:
            logging.info(f"[PIPE] Write OK - bytes={bytes_written.value}/{message_len}")
        else:
            logging.error(f"[PIPE] Write FAILED - GetLastError={windll.kernel32.GetLastError()}")
    except Exception as e:
        logging.error(f'Error writing response: {e}')

def initialize() -> Response:
    """Initialize the plugin."""
    global SETUP_STATE
    
    logging.info("Initializing plugin")
    
    # Initialize setup state
    if SETUP_STATE is None:
        SETUP_STATE = SetupState(STATE_FILE)
    
    # Check if config is loaded and valid
    client_id = config.get("TWITCH_CLIENT_ID", "")
    client_secret = config.get("TWITCH_CLIENT_SECRET", "")
    
    if not client_id or not client_secret or len(client_id) < 20 or len(client_secret) < 20:
        logging.info("Config not found or invalid - starting setup wizard")
        SETUP_STATE.current_state = SetupState.UNCONFIGURED
        SETUP_STATE.save()
        return execute_setup_wizard()
    
    # Verify credentials with API
    logging.info("Verifying credentials with Twitch API...")
    token = get_oauth_token()
    if not token:
        logging.error("Credential verification failed - starting setup wizard")
        SETUP_STATE.current_state = SetupState.WAITING_CREDENTIALS
        SETUP_STATE.record_error("Credential verification failed")
        return execute_setup_wizard()
    
    # Start ready-state heartbeat
    start_continuous_heartbeat(state="ready", interval=5, show_dots=False)
    
    return generate_message_response(
        "Twitch plugin initialized successfully! You can now check if Twitch users are live.",
        awaiting_input=False
    )

def shutdown() -> Response:
    """Shutdown the plugin."""
    logging.info("Shutting down plugin")
    stop_continuous_heartbeat()
    return generate_response(True, "Plugin shutdown successfully")

def main() -> int:
    setup_logging()
    logging.info("Twitch Plugin Started")

    load_config()
    global SETUP_STATE
    SETUP_STATE = SetupState(STATE_FILE)

    cfg = STATE["config"]
    valid, _ = validate_config(cfg)
    initial_state = "ready" if SETUP_STATE.current_state == SetupState.CONFIGURED and valid else "onboarding"
    start_continuous_heartbeat(state=initial_state, interval=5, show_dots=(initial_state != "ready"))

    try:
        while True:
            command = read_command()
            if command is None:
                continue

            try:
                if "tool_calls" in command:
                    response = handle_tool_call(command)
                elif command.get("msg_type") == "user_input":
                    response = handle_user_input(command)
                elif command.get("msg_type") == "terminate":
                    reason = command.get("reason", "unknown")
                    response = generate_message_response(
                        f"[OK] Twitch plugin terminating ({reason})", awaiting_input=False
                    )
                    write_response(response)
                    break
                else:
                    response = generate_failure_response({"message": "Unsupported command payload."})

                if response is not None:
                    write_response(response)
            except Exception as exc:
                logging.exception("Unhandled error while processing command")
                write_response(
                    generate_failure_response({"message": f"Plugin error: {exc}"})
                )
    except KeyboardInterrupt:
        logging.info("Twitch plugin interrupted, shutting down.")
    finally:
        stop_continuous_heartbeat()

    logging.info("Twitch Plugin exiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
