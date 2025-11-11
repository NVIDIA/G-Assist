import json
import logging
import os
import requests
from ctypes import byref, windll, wintypes
from typing import Optional

# Data Types
Response = dict[bool, Optional[str]]

# Get the directory where the plugin is deployed
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "discord")
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

# Save log in plugin directory for better organization
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'discord-plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Directories for media files
CSV_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'Videos', 'NVIDIA', 'G-Assist')
BASE_MP4_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'Videos', 'NVIDIA')
BASE_SCREENSHOT_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'Videos', 'NVIDIA')

# Global state
BOT_TOKEN = None
CHANNEL_ID = None
GAME_DIRECTORY = None
SETUP_COMPLETE = False

# Load config at startup
try:
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    BOT_TOKEN = config.get('BOT_TOKEN', '')
    CHANNEL_ID = config.get('CHANNEL_ID', '')
    GAME_DIRECTORY = config.get('GAME_DIRECTORY', '')
    
    if BOT_TOKEN and len(BOT_TOKEN) > 20 and CHANNEL_ID and len(CHANNEL_ID) > 10:
        SETUP_COMPLETE = True
        logger.info(f"Successfully loaded config from {CONFIG_FILE}")
    else:
        logger.warning(f"Bot token or channel ID is empty/invalid in {CONFIG_FILE}")
        BOT_TOKEN = None
        CHANNEL_ID = None
except FileNotFoundError:
    logger.error(f"Config file not found at {CONFIG_FILE}")
except Exception as e:
    logger.error(f"Error loading config: {e}")

def execute_setup_wizard() -> Response:
    """Guide user through Discord bot setup."""
    global SETUP_COMPLETE, BOT_TOKEN, CHANNEL_ID, GAME_DIRECTORY
    
    # Check if config was updated
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
        new_token = config.get('BOT_TOKEN', '')
        new_channel = config.get('CHANNEL_ID', '')
        new_game_dir = config.get('GAME_DIRECTORY', '')
        
        if new_token and len(new_token) > 20 and new_channel and len(new_channel) > 10:
            BOT_TOKEN = new_token
            CHANNEL_ID = new_channel
            GAME_DIRECTORY = new_game_dir
            SETUP_COMPLETE = True
            logger.info("Discord bot configured successfully!")
            return {
                'success': True,
                'message': "✓ Discord bot configured! You can now send messages, clips, and screenshots to your Discord channel.",
                'awaiting_input': False
            }
    except:
        pass
    
    # Show setup instructions
    message = f"""
DISCORD PLUGIN - FIRST TIME SETUP
==================================

Welcome! Let's set up your Discord bot. This takes about 5 minutes.

STEP 1 - Create Discord Bot:
   1. Visit: https://discord.com/developers/applications
   2. Click "New Application" and give it a name
   3. Go to "Bot" tab and click "Add Bot"
   4. Click "Reset Token" to generate a new token
   5. Copy the token (you'll need it for BOT_TOKEN)
   6. Enable these Privileged Gateway Intents:
      - MESSAGE CONTENT INTENT
      - SERVER MEMBERS INTENT
   7. Save changes

STEP 2 - Add Bot to Your Server:
   1. Go to "Installation" tab
   2. Copy the install link (should include permissions=2048)
   3. Open link in browser and add bot to your server

STEP 3 - Get Channel ID:
   1. In Discord, go to User Settings > Advanced
   2. Enable "Developer Mode"
   3. Right-click on your target channel
   4. Click "Copy ID"

STEP 4 - Configure Plugin:
   1. Open this file: {CONFIG_FILE}
   2. Replace the values:
      {{"BOT_TOKEN": "your_bot_token_here",
       "CHANNEL_ID": "your_channel_id_here",
       "GAME_DIRECTORY": "Desktop"}}
   3. Save the file

After saving, send me ANY message (like "done") and I'll verify it!

Note: GAME_DIRECTORY is where clips/screenshots are stored (e.g., "Desktop", "RUST")
"""
    
    logger.info("Showing Discord setup wizard to user")
    return {
        'success': True,
        'message': message,
        'awaiting_input': True
    }

def execute_initialize_command() -> dict:
    """Initialize the plugin."""
    logger.info("Initializing Discord plugin...")
    
    # Check if setup is needed
    if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
        return execute_setup_wizard()
    
    return generate_success_response('Discord plugin initialized successfully.')

def execute_shutdown_command() -> dict:
    """Shutdown the plugin."""
    logger.info('Shutting down Discord plugin')
    return generate_success_response('Shutdown success.')

def send_message_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    """Send a text message to Discord channel."""
    try:
        if not BOT_TOKEN or not CHANNEL_ID:
            return generate_failure_response('Discord bot not configured.')
        
        text = params.get('message', '')
        if not text:
            return generate_failure_response('No message provided.')
        
        logger.info(f'Sending message to Discord channel: {CHANNEL_ID}')
        
        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
        payload = {"content": text}

        r = requests.post(url, headers=headers, json=payload)

        if r.status_code == 200 or r.status_code == 201:
            logger.info('Message sent successfully.')
            return generate_success_response('Message sent successfully.')
        else:
            logger.error(f'Failed to send message: {r.text}')
            return generate_failure_response(f'Failed to send message: {r.text}')

    except Exception as e:
        logger.error(f'Error in send_message_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending message.')

def find_latest_file(directory: str, extension: str) -> Optional[str]:
    """Find the most recently modified file with given extension."""
    try:
        if not os.path.exists(directory):
            logger.error(f'Directory not found: {directory}')
            return None
            
        files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(extension)]
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception as e:
        logger.error(f'Error finding latest file: {str(e)}')
        return None

def send_latest_chart_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    """Send latest performance chart (CSV) to Discord."""
    try:
        if not BOT_TOKEN or not CHANNEL_ID:
            return generate_failure_response('Discord bot not configured.')
            
        caption = params.get('caption', '') if params else ''
        file_path = find_latest_file(CSV_DIRECTORY, '.csv')

        if not file_path:
            return generate_failure_response('No CSV file found.')

        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        files = {"file": open(file_path, 'rb')}
        payload = {"content": caption}

        r = requests.post(url, headers=headers, data=payload, files=files)

        if r.status_code == 200 or r.status_code == 201:
            return generate_success_response('CSV sent successfully.')
        else:
            return generate_failure_response(f'Failed to send CSV: {r.text}')

    except Exception as e:
        logger.error(f'Error in send_latest_chart_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending CSV.')

def send_latest_shadowplay_clip_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    """Send latest ShadowPlay clip to Discord."""
    try:
        if not BOT_TOKEN or not CHANNEL_ID:
            return generate_failure_response('Discord bot not configured.')
        
        if not GAME_DIRECTORY:
            return generate_failure_response('GAME_DIRECTORY not configured.')
            
        caption = params.get('caption', '') if params else ''
        mp4_directory = os.path.join(BASE_MP4_DIRECTORY, GAME_DIRECTORY)
        file_path = find_latest_file(mp4_directory, '.mp4')

        if not file_path:
            return generate_failure_response(f'No MP4 file found in {mp4_directory}.')

        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        files = {"file": open(file_path, 'rb')}
        payload = {"content": caption}
        r = requests.post(url, headers=headers, data=payload, files=files)

        if r.status_code == 200 or r.status_code == 201:
            return generate_success_response('MP4 sent successfully.')
        else:
            return generate_failure_response(f'Failed to send MP4: {r.text}')

    except Exception as e:
        logger.error(f'Error in send_latest_shadowplay_clip_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending MP4.')

def send_latest_screenshot_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    """Send latest screenshot to Discord."""
    try:
        if not BOT_TOKEN or not CHANNEL_ID:
            return generate_failure_response('Discord bot not configured.')
        
        if not GAME_DIRECTORY:
            return generate_failure_response('GAME_DIRECTORY not configured.')
            
        caption = params.get('caption', '') if params else ''
        screenshot_directory = os.path.join(BASE_SCREENSHOT_DIRECTORY, GAME_DIRECTORY)
        file_path = find_latest_file(screenshot_directory, '.png')

        if not file_path:
            return generate_failure_response(f'No screenshot found in {screenshot_directory}.')

        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        files = {"file": open(file_path, 'rb')}
        payload = {"content": caption}

        r = requests.post(url, headers=headers, data=payload, files=files)

        if r.status_code == 200 or r.status_code == 201:
            return generate_success_response('Screenshot sent successfully.')
        else:
            return generate_failure_response(f'Failed to send screenshot: {r.text}')

    except Exception as e:
        logger.error(f'Error in send_latest_screenshot_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending screenshot.')

def generate_failure_response(message: str = None) -> Response:
    """Generate a failure response."""
    response = {'success': False}
    if message:
        response['message'] = message
    return response

def generate_success_response(message: str = None) -> Response:
    """Generate a success response."""
    response = {'success': True}
    if message:
        response['message'] = message
    return response

def read_command() -> dict | None:
    """Read command from stdin pipe."""
    try:
        STD_INPUT_HANDLE = -10
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
        chunks = []

        while True:
            BUFFER_SIZE = 4096
            message_bytes = wintypes.DWORD()
            buffer = bytes(BUFFER_SIZE)
            success = windll.kernel32.ReadFile(pipe, buffer, BUFFER_SIZE, byref(message_bytes), None)

            if not success:
                logger.error('Error reading from command pipe')
                return None

            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            if message_bytes.value < BUFFER_SIZE:
                break

        retval = ''.join(chunks)
        logger.info(f'[PIPE] Read {len(retval)} bytes from pipe')
        return json.loads(retval)

    except json.JSONDecodeError:
        logger.error('Failed to decode JSON input')
        return None
    except Exception as e:
        logger.error(f'Unexpected error in read_command: {str(e)}')
        return None

def write_response(response: Response) -> None:
    """Write response to stdout pipe."""
    try:
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)
        
        logger.info(f"[PIPE] Writing message: success={response.get('success', 'unknown')}, length={message_len} bytes")

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(pipe, message_bytes, message_len, byref(bytes_written), None)
        
        if success:
            logger.info(f"[PIPE] Write OK - bytes={bytes_written.value}/{message_len}")
        else:
            logger.error(f"[PIPE] Write FAILED - GetLastError={windll.kernel32.GetLastError()}")
    except Exception as e:
        logger.error(f'Failed to write response: {str(e)}')

def main():
    """Main plugin entry point."""
    TOOL_CALLS_PROPERTY = 'tool_calls'
    CONTEXT_PROPERTY = 'messages'
    SYSTEM_INFO_PROPERTY = 'system_info'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'params'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'

    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'send_message_to_discord_channel': send_message_to_discord_channel,
        'send_latest_chart_to_discord_channel': send_latest_chart_to_discord_channel,
        'send_latest_shadowplay_clip_to_discord_channel': send_latest_shadowplay_clip_to_discord_channel,
        'send_latest_screenshot_to_discord_channel': send_latest_screenshot_to_discord_channel,
    }

    cmd = ''
    logger.info('Discord plugin started')
    read_failures = 0
    MAX_READ_FAILURES = 3

    while cmd != SHUTDOWN_COMMAND:
        response = None
        input = read_command()
        if input is None:
            read_failures += 1
            logger.error(f'Error reading command (failure {read_failures}/{MAX_READ_FAILURES})')
            if read_failures >= MAX_READ_FAILURES:
                logger.error('Too many read failures, exiting')
                break
            continue
        
        # Reset failure counter on successful read
        read_failures = 0

        logger.info(f'Received input: {input}')

        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY]
                    logger.info(f'Processing command: {cmd}')
                    if cmd in commands:
                        if cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND:
                            response = commands[cmd]()
                        else:
                            # Check if setup is needed before executing Discord functions
                            if not SETUP_COMPLETE or not BOT_TOKEN or not CHANNEL_ID:
                                logger.info('[COMMAND] Bot not configured - starting setup wizard')
                                response = execute_setup_wizard()
                            else:
                                params = tool_call.get(PARAMS_PROPERTY, {})
                                context = input.get(CONTEXT_PROPERTY, {})
                                system_info = input.get(SYSTEM_INFO_PROPERTY, {})
                                logger.info(f'Executing command: {cmd}')
                                response = commands[cmd](params, context, system_info)
                    else:
                        logger.warning(f'Unknown command: {cmd}')
                        response = generate_failure_response(f'Unknown command: {cmd}')
                else:
                    logger.warning('Malformed input: missing function property')
                    response = generate_failure_response('Malformed input.')
        else:
            logger.warning('Malformed input: missing tool_calls property')
            response = generate_failure_response('Malformed input.')

        logger.info(f'Sending response: {response}')
        write_response(response)

        if cmd == SHUTDOWN_COMMAND:
            logger.info('Shutdown command received, terminating plugin')
            break

    logger.info('Discord plugin stopped.')
    return 0

if __name__ == '__main__':
    main()
