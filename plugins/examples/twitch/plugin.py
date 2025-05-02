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
    Log location: %USERPROFILE%\\twitch.log

Commands Supported:
    - initialize: Initialize the plugin
    - is_twitch_user_live: Check if a Twitch user is streaming
    - shutdown: Gracefully shutdown the plugin

Dependencies:
    - requests: For making HTTP requests to Twitch API
    - ctypes: For Windows pipe communication
"""

import json
import logging
import os
import sys
from typing import Optional, Dict, Any
import requests
from ctypes import byref, windll, wintypes

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

CONFIG_FILE = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    r'NVIDIA Corporation\nvtopps\rise\plugins\twitch',
    'config.json'
)
"""Path to configuration file containing Twitch API credentials."""

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'twitch.log')
"""Path to log file for plugin operations."""

# Twitch API endpoints
TWITCH_OAUTH_URL = "https://id.twitch.tv/oauth2/token"
"""Twitch OAuth token endpoint for client credentials flow."""

TWITCH_STREAM_URL = "https://api.twitch.tv/helix/streams"
"""Twitch API endpoint for checking stream status."""

# Global state
oauth_token: Optional[str] = None
"""Cached OAuth token for Twitch API requests."""

config: Dict[str, str] = {}
"""Loaded configuration containing Twitch API credentials."""

def setup_logging() -> None:
    """Configure logging with appropriate format and level.
    
    Sets up the logging configuration with file output, INFO level, and timestamp format.
    The log file location is determined by LOG_FILE constant.
    
    Log Format:
        %(asctime)s - %(levelname)s - %(message)s
        Example: 2024-03-14 12:34:56,789 - INFO - Plugin initialized
    """
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )

def load_config() -> Dict[str, str]:
    """Load configuration from config.json file.
    
    Expected config format:
    {
        "TWITCH_CLIENT_ID": "your_client_id_here",
        "TWITCH_CLIENT_SECRET": "your_client_secret_here"
    }
    
    Returns:
        Dict[str, str]: Configuration dictionary containing Twitch API credentials.
                       Returns empty dict if file doesn't exist or on error.
    
    Note:
        Errors during file reading or JSON parsing are logged but not raised.
    """
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as file:
                return json.load(file)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
    return {}

def save_config(config_data: Dict[str, str]) -> None:
    """Save configuration to config.json file.
    
    Args:
        config_data (Dict[str, str]): Configuration dictionary to save.
    """
    try:
        with open(CONFIG_FILE, "w") as file:
            json.dump(config_data, file, indent=4)
    except Exception as e:
        logging.error(f"Error saving config: {e}")

def get_oauth_token() -> Optional[str]:
    """Obtain OAuth token from Twitch API.
    
    Uses the client credentials flow to obtain an access token from Twitch.
    Requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET in config.
    
    Returns:
        Optional[str]: The OAuth access token if successful, None otherwise.
    """
    global oauth_token
    try:
        response = requests.post(
            TWITCH_OAUTH_URL,
            params={
                "client_id": config.get("TWITCH_CLIENT_ID", ""),
                "client_secret": config.get("TWITCH_CLIENT_SECRET", ""),
                "grant_type": "client_credentials"
            }
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
    """Generate a standardized response dictionary.
    
    Args:
        success (bool): Whether the operation was successful.
        message (Optional[str]): Optional message to include in response.
    
    Returns:
        Response: Dictionary containing success status and optional message.
    """
    response = {'success': success}
    if message:
        response['message'] = message
    return response

def check_twitch_live_status(params: Dict[str, str]) -> Response:
    """Check if a Twitch user is currently live.
    
    Args:
        params (Dict[str, str]): Dictionary containing 'username' key with Twitch username.
    
    Returns:
        Response: Dictionary containing:
            - success: True if check was successful
            - message: Stream details if user is live, "OFFLINE" if not,
                      or error message if check failed.
    
    Example Response (User Live):
        {
            'success': True,
            'message': 'username is LIVE!\nTitle: Stream Title\nGame: Game Name\n
                       Viewers: 1234\nStarted At: 2024-03-14T12:34:56Z'
        }
    
    Example Response (User Offline):
        {
            'success': True,
            'message': 'username is OFFLINE'
        }
    """
    global oauth_token
    username = params.get("username")
    
    if not username:
        return generate_response(False, "Missing required parameter: username")
    
    if not oauth_token:
        oauth_token = get_oauth_token()
        if not oauth_token:
            return generate_response(False, "Failed to authenticate with Twitch")
    
    try:
        headers = {
            "Client-ID": config.get("TWITCH_CLIENT_ID", ""),
            "Authorization": f"Bearer {oauth_token}"
        }
        response = requests.get(
            TWITCH_STREAM_URL,
            headers=headers,
            params={"user_login": username}
        )
        response_data = response.json()

        if "data" in response_data and response_data["data"]:
            stream_info = response_data["data"][0]
            # Strip emojis from title and game name
            title = ''.join(char for char in stream_info['title'] if ord(char) < 128)
            game_name = ''.join(char for char in stream_info.get('game_name', 'Unknown')) if stream_info.get('game_name') else 'Unknown'
            return generate_response(True, 
                f"{username} is LIVE!\n"
                f"Title: {title}\n"
                f"Game: {game_name}\n"
                f"Viewers: {stream_info['viewer_count']}\n"
                f"Started At: {stream_info['started_at']}"
            )
        return generate_response(True, f"{username} is OFFLINE")
    
    except requests.RequestException as e:
        logging.error(f"Error checking Twitch live status: {e}")
        return generate_response(False, "Failed to check Twitch live status")

def read_command() -> Optional[Dict[str, Any]]:
    """Read command from stdin pipe.
    
    Reads data from Windows pipe in chunks until complete message is received.
    Expects JSON-formatted input.
    
    Returns:
        Optional[Dict[str, Any]]: Parsed command dictionary if successful,
                                 None if reading or parsing fails.
    
    Expected Command Format:
        {
            "tool_calls": [
                {
                    "func": "command_name",
                    "params": {
                        "param1": "value1",
                        ...
                    }
                }
            ]
        }
    """
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
        logging.info(f'Raw Input: {retval}')
        return json.loads(retval)
        
    except json.JSONDecodeError:
        logging.error(f'Received invalid JSON: {retval}')
        logging.exception("JSON decoding failed:")
        return None
    except Exception as e:
        logging.error(f'Exception in read_command(): {e}')
        return None

def write_response(response: Response) -> None:
    """Write response to stdout pipe.
    
    Writes JSON-formatted response to Windows pipe with <<END>> marker.
    The marker is used by the reader to determine the end of the response.
    
    Args:
        response (Response): Response dictionary to write.
    
    Response Format:
        JSON-encoded dictionary followed by <<END>> marker.
        Example: {"success":true,"message":"Plugin initialized successfully"}<<END>>
    """
    try:
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        
        bytes_written = wintypes.DWORD()
        windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            len(message_bytes),
            bytes_written,
            None
        )
    except Exception as e:
        logging.error(f'Error writing response: {e}')

def initialize() -> Response:
    """Initialize the plugin.
    
    Performs any necessary setup for the plugin.
    
    Returns:
        Response: Success response with initialization status.
    """
    logging.info("Initializing plugin")
    return generate_response(True, "Plugin initialized successfully")

def shutdown() -> Response:
    """Shutdown the plugin.
    
    Performs any necessary cleanup before plugin shutdown.
    
    Returns:
        Response: Success response with shutdown status.
    """
    logging.info("Shutting down plugin")
    return generate_response(True, "Plugin shutdown successfully")

def main() -> None:
    """Main plugin loop.
    
    Sets up logging and enters main command processing loop.
    Handles incoming commands and routes them to appropriate handlers.
    Continues running until shutdown command is received.
    
    Command Processing Flow:
        1. Read command from pipe
        2. Parse command and parameters
        3. Route to appropriate handler
        4. Write response back to pipe
        5. Repeat until shutdown command
    
    Error Handling:
        - Invalid commands return error response
        - Failed command reads are logged and loop continues
        - Shutdown command exits loop gracefully
    """
    setup_logging()
    logging.info("Twitch Plugin Started")
    
    while True:
        command = read_command()
        if command is None:
            logging.error('Error reading command')
            continue
        
        tool_calls = command.get("tool_calls", [])
        for tool_call in tool_calls:
            func = tool_call.get("func")
            params = tool_call.get("params", {})
            
            if func == "initialize":
                response = initialize()
            elif func == "check_twitch_live_status":
                response = check_twitch_live_status(params)
            elif func == "shutdown":
                response = shutdown()
                write_response(response)
                return
            else:
                response = generate_response(False, "Unknown function call")
            
            write_response(response)

if __name__ == "__main__":
    config = load_config()
    main()
