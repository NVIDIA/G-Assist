import json
import logging
import os
import requests
import feedparser
from ctypes import byref, windll, wintypes
from typing import Dict, Optional, List
import threading
import time

# Data Types
Response = Dict[bool, Optional[str]]

# Get the directory where the plugin is deployed
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "ifttt")
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

# Save log in plugin directory for better organization
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'ifttt-plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Global state
IFTTT_WEBHOOK_KEY = None
EVENT_NAME = None
MAIN_RSS_URL = "https://feeds.feedburner.com/ign/pc-articles"  # IGN PC Gaming RSS feed as default
ALTERNATE_RSS_URL = "https://feeds.feedburner.com/ign/all"  # IGN All RSS feed as default
SETUP_COMPLETE = False

# Load config at startup
try:
    with open(CONFIG_FILE, 'r') as file:
        config = json.load(file)
    IFTTT_WEBHOOK_KEY = config.get('webhook_key', '')
    EVENT_NAME = config.get('event_name', '')
    MAIN_RSS_URL = config.get('main_rss_url', MAIN_RSS_URL)
    ALTERNATE_RSS_URL = config.get('alternate_rss_url', ALTERNATE_RSS_URL)
    
    if IFTTT_WEBHOOK_KEY and len(IFTTT_WEBHOOK_KEY) > 10 and EVENT_NAME:
        SETUP_COMPLETE = True
        logger.info(f"Successfully loaded config from {CONFIG_FILE}")
    else:
        logger.warning(f"Webhook key or event name is empty/invalid in {CONFIG_FILE}")
        IFTTT_WEBHOOK_KEY = None
        EVENT_NAME = None
except FileNotFoundError:
    logger.error(f"Config file not found at {CONFIG_FILE}")
except Exception as e:
    logger.error(f"Error loading config: {e}")


# Tethered mode support
heartbeat_thread = None
heartbeat_active = False

def send_heartbeat(state="ready"):
    """Send silent heartbeat to engine (not visible to user)."""
    try:
        heartbeat_msg = {
            "type": "heartbeat",
            "state": state,
            "timestamp": time.time()
        }
        write_response(heartbeat_msg)
        logger.info(f"[HEARTBEAT] Sent heartbeat: state={state}")
    except Exception as e:
        logger.error(f"[HEARTBEAT] Failed to send heartbeat: {e}")

def heartbeat_loop():
    """Background thread that sends periodic heartbeats."""
    global heartbeat_active
    logger.info("[HEARTBEAT] Heartbeat thread started")
    while heartbeat_active:
        send_heartbeat(state="ready")
        time.sleep(5)  # Send heartbeat every 5 seconds
    logger.info("[HEARTBEAT] Heartbeat thread stopped")
def execute_setup_wizard() -> Response:
    """Guide user through IFTTT webhook setup."""
    global SETUP_COMPLETE, IFTTT_WEBHOOK_KEY, EVENT_NAME, MAIN_RSS_URL, ALTERNATE_RSS_URL
    
    # Check if config was updated
    try:
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
        new_key = config.get('webhook_key', '')
        new_event = config.get('event_name', '')
        
        if new_key and len(new_key) > 10 and new_event:
            IFTTT_WEBHOOK_KEY = new_key
            EVENT_NAME = new_event
            MAIN_RSS_URL = config.get('main_rss_url', MAIN_RSS_URL)
            ALTERNATE_RSS_URL = config.get('alternate_rss_url', ALTERNATE_RSS_URL)
            SETUP_COMPLETE = True
            logger.info("IFTTT webhook configured successfully!")
            return {
                'success': True,
                'message': "✓ IFTTT webhook configured! You can now trigger your gaming setup applet.",
                'awaiting_input': False
            }
    except:
        pass
    
    # Show setup instructions
    message = f"""
IFTTT PLUGIN - FIRST TIME SETUP
================================

Welcome! Let's set up your IFTTT webhook. This takes about 5 minutes.

STEP 1 - Create IFTTT Account:
   1. Visit: https://ifttt.com/join
   2. Sign up for a free account

STEP 2 - Get Webhook Key:
   1. Visit: https://ifttt.com/maker_webhooks
   2. Click "Documentation"
   3. Your webhook key is shown at the top
   4. Copy the key (it's after "/use/")

STEP 3 - Create an Applet:
   1. Visit: https://ifttt.com/create
   2. Click "+ If This"
   3. Search for "Webhooks" and select it
   4. Choose "Receive a web request"
   5. Enter an event name (e.g., "gaming_setup")
   6. Click "+ Then That"
   7. Choose your action (e.g., control lights, send notification)
   8. Complete the applet setup

STEP 4 - Configure Plugin:
   1. Open this file: {CONFIG_FILE}
   2. Replace the values:
      {{"webhook_key": "your_webhook_key_here",
       "event_name": "your_event_name_here",
       "main_rss_url": "https://feeds.feedburner.com/ign/pc-articles",
       "alternate_rss_url": "https://feeds.feedburner.com/ign/all"}}
   3. Save the file

After saving, send me ANY message (like "done") and I'll verify it!

Note: The plugin will include IGN gaming news headlines when triggering your applet!
"""
    
    logger.info("Showing IFTTT setup wizard to user")
    return {
        'success': True,
        'message': message,
        'awaiting_input': True
    }

def execute_initialize_command() -> dict:
    """Initialize the plugin."""
    logger.info('Initializing IFTTT plugin...')
    
    
    # Start heartbeat thread
    global heartbeat_thread, heartbeat_active
    if not heartbeat_active:
        heartbeat_active = True
        heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        heartbeat_thread.start()
        logger.info("[HEARTBEAT] Started heartbeat thread")
    
    # Check if setup is needed
    if not SETUP_COMPLETE or not IFTTT_WEBHOOK_KEY or not EVENT_NAME:
        return execute_setup_wizard()
    
    return generate_success_response('IFTTT plugin initialized successfully.')

def execute_shutdown_command() -> dict:
    """Shutdown the plugin."""
    logger.info('Shutting down IFTTT plugin')
    
    # Stop heartbeat thread
    global heartbeat_active, heartbeat_thread
    if heartbeat_active:
        heartbeat_active = False
        if heartbeat_thread:
            heartbeat_thread.join(timeout=1)
        logger.info("[HEARTBEAT] Stopped heartbeat thread")
    
    return generate_success_response('Shutdown success.')

def fetch_ign_gaming_news() -> List[str]:
    """
    Fetches the latest gaming news from IGN RSS feed.
    
    Returns:
        List of headlines for the top 3 gaming news articles.
    """
    try:
        logger.info('Fetching IGN gaming news')
        
        # using feedparser to fetch and parse the IGN gaming news RSS feed
        feed_url = MAIN_RSS_URL
        feed = feedparser.parse(feed_url)
        
        if not feed.entries:
            logger.warning('No entries found in main RSS feed, trying alternate feed')
            feed_url = ALTERNATE_RSS_URL
            feed = feedparser.parse(feed_url)
        
        if feed.entries:
            headlines = [entry.title for entry in feed.entries[:3]]
            logger.info(f'Fetched {len(headlines)} headlines from IGN')
            return headlines
        else:
            logger.error('No entries found in either RSS feed')
            return []
            
    except Exception as e:
        logger.error(f'Error fetching IGN gaming news: {str(e)}')
        return []

def execute_run_applet_command(params: dict = None, send_status_callback=None) -> dict:
    """
    Triggers an IFTTT webhook applet with IGN gaming news.
    
    Args:
        params: Optional parameters (currently unused)
        send_status_callback (callable, optional): Callback to send status updates
    
    Returns:
        Success or failure response
    """
    logger.info(f'Executing run_applet with params: {params}')

    if not IFTTT_WEBHOOK_KEY or not EVENT_NAME:
        return generate_failure_response('IFTTT webhook not configured.')
    
    try:
        # Send status update
        if send_status_callback:
            send_status_callback(generate_status_update(f"Fetching gaming news..."))
        
        webhook_url = f'https://maker.ifttt.com/trigger/{EVENT_NAME}/with/key/{IFTTT_WEBHOOK_KEY}'
        
        # initialize webhook data
        webhook_data = {}
        
        # Always fetch and include IGN news in the webhook
        headlines = fetch_ign_gaming_news()
        
        if headlines:
            # format the news items for IFTTT webhook (up to 3 values) from the headlines list
            # formatting based on the IFTTT webhook body documentation (https://ifttt.com/maker_webhooks)
            for i, headline in enumerate(headlines[:3], 1):
                webhook_data[f'value{i}'] = headline
                
            logger.info(f'Including {len(headlines)} news headlines in webhook')
        
        # Send status update
        if send_status_callback:
            send_status_callback(generate_status_update(f"Triggering IFTTT applet {EVENT_NAME}..."))
        
        # Send the webhook request with data if we have any, otherwise send without data
        if webhook_data:
            response = requests.post(webhook_url, json=webhook_data)
        else:
            response = requests.post(webhook_url)

        if response.status_code >= 200 and response.status_code < 300:
            return generate_success_response(f'IFTTT applet {EVENT_NAME} triggered successfully.')
        else:
            logger.error(f'IFTTT webhook {EVENT_NAME} failed: {response.text}')
            return generate_failure_response(f'IFTTT applet {EVENT_NAME} failed: {response.text}')

    except Exception as e:
        logger.error(f'Error triggering IFTTT webhook {EVENT_NAME}: {str(e)}')
        return generate_failure_response(f'Error triggering IFTTT applet {EVENT_NAME}: {str(e)}')

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

def generate_status_update(message: str) -> dict:
    """Generate a status update (not a final response).
    
    Status updates are intermediate messages that don't end the plugin execution.
    They should NOT include 'success' field to avoid being treated as final responses.
    """
    return {'status': 'in_progress', 'message': message}

def read_command() -> dict or None:
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
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'params'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'
    ERROR_MESSAGE = 'Plugin Error!'

    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'trigger_gaming_setup': execute_run_applet_command,
    }
    cmd = ''

    logger.info('IFTTT Plugin started')
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

        # Handle user input passthrough messages (for setup wizard interaction)
        if isinstance(input, dict) and input.get('msg_type') == 'user_input':
            user_input_text = input.get('content', '')
            logger.info(f'[INPUT] Received user input passthrough: "{user_input_text}"')
            
            # Check if setup is needed
            global SETUP_COMPLETE, IFTTT_WEBHOOK_KEY, EVENT_NAME
            if not SETUP_COMPLETE:
                logger.info("[WIZARD] User input during setup - checking config")
                response = execute_setup_wizard()
                write_response(response)
                continue
            else:
                # Setup already complete, acknowledge the input
                logger.info("[INPUT] Setup already complete, acknowledging user input")
                response = generate_success_response("Got it! The IFTTT plugin is ready to use.")
                write_response(response)
                continue

        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY]
                    logger.info(f'Processing command: {cmd}')
                    if cmd in commands:
                        if cmd in [INITIALIZE_COMMAND, SHUTDOWN_COMMAND]:
                            response = commands[cmd]()
                        else:
                            # Check if setup is needed before executing IFTTT functions
                            if not SETUP_COMPLETE or not IFTTT_WEBHOOK_KEY or not EVENT_NAME:
                                logger.info('[COMMAND] Webhook not configured - starting setup wizard')
                                response = execute_setup_wizard()
                            else:
                                params = tool_call.get(PARAMS_PROPERTY, {})
                                response = commands[cmd](params, send_status_callback=write_response)
                    else:
                        logger.warning(f'Unknown command: {cmd}')
                        response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
                else:
                    logger.warning('Malformed input: missing function property')
                    response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')
        else:
            logger.warning('Malformed input: missing tool_calls property')
            response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

        logger.info(f'Sending response: {response}')
        write_response(response)

        if cmd == SHUTDOWN_COMMAND:
            logger.info('Shutdown command received, terminating plugin')
            break

    logger.info('IFTTT Plugin stopped.')
    return 0

if __name__ == '__main__':
    main()
