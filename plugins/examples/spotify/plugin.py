import json
import os
import requests
import sys
import webbrowser
import logging
import os
from urllib.parse import urlencode, urlparse, parse_qs
from ctypes import byref, windll, wintypes
from requests import Response
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import time

# Settings specific to the user's system. This is temporary until a
# configuration file is added to the plugin.
# Save log in plugin directory for better organization
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify")
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'spotify-plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REDIRECT_URI="http://127.0.0.1:8888/callback"  # Local callback server (use IP instead of localhost for Spotify compatibility)
SCOPE = "user-library-read user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative"

# Spotify API endpoints
AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
AUTH_URL = "https://accounts.spotify.com/api/token"
BASE_URL = "https://api.spotify.com/v1"

AUTH_STATE = None
ACCESS_TOKEN = None
REFRESH_TOKEN = None

# Spotify app credentials (loaded from config.json in main())
CLIENT_ID = None
CLIENT_SECRET = None
USERNAME = None

# OAuth callback server state
oauth_callback_code = None
oauth_callback_error = None
oauth_server_running = False

# Setup state machine
class SetupState:
    """Persistent setup state machine for plugin configuration"""
    UNCONFIGURED = "unconfigured"                    # No app credentials
    WAITING_APP_CREATION = "waiting_app_creation"    # User creating Spotify app
    WAITING_CREDENTIALS = "waiting_credentials"       # User entering credentials
    NEED_USER_AUTH = "need_user_auth"                # Need OAuth tokens
    WAITING_OAUTH = "waiting_oauth"                  # User authorizing in browser
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
            import time
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

# Heartbeat background thread state
heartbeat_thread = None
heartbeat_active = False
heartbeat_message = ""

# Helper response generators (defined early for use throughout the code)
def generate_message_response(message: str, awaiting_input: bool = False) -> dict:
    """
    Generate a message response.
    
    PHASE 3: Tethered Mode Protocol
    - awaiting_input=True: Plugin needs more user interaction, stay in passthrough
    - awaiting_input=False: Plugin is done, exit passthrough mode
    """
    return {
        'success': True,  # Always include success for protocol compliance
        'message': message,
        'awaiting_input': awaiting_input
    }

def generate_success_response(body: dict = None, awaiting_input: bool = False) -> dict:
    """Generate a success response with optional data"""
    response = body.copy() if body is not None else dict()
    response['success'] = True
    response['awaiting_input'] = awaiting_input  # PHASE 3
    return response

def generate_failure_response(body: dict = None) -> dict:
    """Generate a failure response with optional data"""
    response = body.copy() if body is not None else dict()
    response['success'] = False
    response['awaiting_input'] = False  # PHASE 3: Always exit on failure
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

def start_continuous_heartbeat(state="ready", interval=5, show_dots=True):
    """
    Start background thread that sends periodic heartbeats.
    
    Args:
        state: Heartbeat state ("onboarding" or "ready")
        interval: Seconds between heartbeats
        show_dots: If True, send visible status dots. If False, send silent heartbeats only.
    """
    global heartbeat_thread, heartbeat_active, heartbeat_message
    
    # Stop any existing heartbeat
    stop_continuous_heartbeat()
    
    heartbeat_message = state
    heartbeat_active = True
    
    def heartbeat_loop():
        while heartbeat_active:
            time.sleep(interval)
            if heartbeat_active:
                # Send tagged heartbeat (silent, not visible to user)
                send_heartbeat(heartbeat_message)
                # PHASE 3: Only send status dots if explicitly enabled
                # Don't send dots when awaiting user input - stay quiet
                if show_dots:
                    send_status_message(".")
    
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    logging.info(f"[HEARTBEAT] Started continuous heartbeat: state={state}, interval={interval}s, show_dots={show_dots}")

def stop_continuous_heartbeat():
    """Stop background heartbeat thread"""
    global heartbeat_active, heartbeat_thread
    heartbeat_active = False
    if heartbeat_thread:
        heartbeat_thread.join(timeout=1)
        heartbeat_thread = None
    logging.info("[HEARTBEAT] Stopped continuous heartbeat")


def get_spotify_auth_url():
    """
    Generate the Spotify authorization URL for the user to log in and approve.
    """
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
    }
    return f"{AUTHORIZATION_URL}?{urlencode(params)}"

def extract_code_from_url(callback_url):
    """
    Extract the authorization code from the callback URL.
    """
    query = urlparse(callback_url).query
    code = parse_qs(query).get("code", [None])[0]
    return code

def get_access_token(auth_code):
    """
    Exchange the authorization code for an access token.
    """
    token_response = requests.post(
        AUTH_URL,
        data={
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    if token_response.status_code != 200:
        raise Exception(f"Error getting token: {token_response.json()}")

    token_data = token_response.json()
    return token_data

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callbacks - catches the authorization code"""
    
    def do_GET(self):
        """Handle GET request from OAuth provider"""
        global oauth_callback_code, oauth_callback_error, oauth_server_running
        
        # Parse the URL to extract code or error
        parsed = urlparse(self.path)
        query_params = parse_qs(parsed.query)
        
        if 'code' in query_params:
            # Success! Got authorization code
            oauth_callback_code = query_params['code'][0]
            logging.info(f"[OAuth] Received authorization code: {oauth_callback_code[:20]}...")
            
            # Send success page to browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            success_html = """
            <html>
            <head><title>Authentication Successful</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px; background: #0a0a0f; color: #76b900;">
                <h1>✓ Authentication Successful!</h1>
                <p>You have successfully authenticated with Spotify.</p>
                <p>You can close this window and return to G-Assist.</p>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode())
            
        elif 'error' in query_params:
            # Error from OAuth provider
            oauth_callback_error = query_params['error'][0]
            logging.error(f"[OAuth] Error from provider: {oauth_callback_error}")
            
            # Send error page to browser
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            error_html = f"""
            <html>
            <head><title>Authentication Failed</title></head>
            <body style="font-family: Arial; text-align: center; padding: 50px; background: #0a0a0f; color: #ff3d00;">
                <h1>✗ Authentication Failed</h1>
                <p>Error: {oauth_callback_error}</p>
                <p>Please try again or check your plugin configuration.</p>
            </body>
            </html>
            """
            self.wfile.write(error_html.encode())
        
        # Signal that we received a response (success or error)
        oauth_server_running = False
    
    def log_message(self, format, *args):
        """Suppress default HTTP server logging to avoid cluttering logs"""
        pass


def start_oauth_callback_server(port=8888, timeout=120):
    """
    Start a local HTTP server to catch OAuth callbacks.
    Uses 127.0.0.1 instead of localhost for better Spotify compatibility.
    
    Args:
        port: Port to listen on (default 8888)
        timeout: Max seconds to wait for callback (default 120)
    
    Returns:
        tuple: (auth_code, error) - either auth_code or error will be set
    """
    global oauth_callback_code, oauth_callback_error, oauth_server_running
    
    # Reset state
    oauth_callback_code = None
    oauth_callback_error = None
    oauth_server_running = True
    
    # Create HTTP server on 127.0.0.1 (Spotify allows this for local dev)
    server = HTTPServer(('127.0.0.1', port), OAuthCallbackHandler)
    logging.info(f"[OAuth] Starting HTTP callback server on http://127.0.0.1:{port}")
    
    # Run server in background thread with timeout
    def run_server():
        start_time = time.time()
        while oauth_server_running and (time.time() - start_time) < timeout:
            server.handle_request()  # Handle one request then check flag
        logging.info("[OAuth] Callback server stopped")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    # Wait for callback or timeout
    start_time = time.time()
    while oauth_server_running and (time.time() - start_time) < timeout:
        if oauth_callback_code or oauth_callback_error:
            break
        time.sleep(0.1)
    
    # Cleanup
    oauth_server_running = False
    server_thread.join(timeout=2)
    
    return oauth_callback_code, oauth_callback_error


def authorize_user_automated():
    """
    Fully automated OAuth flow using local callback server.
    Opens browser, catches callback automatically, saves tokens.
    
    Returns:
        dict: Success or failure response with message
    """
    global ACCESS_TOKEN, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET
    
    # Verify credentials are loaded
    if not CLIENT_ID or not CLIENT_SECRET:
        error_msg = "CLIENT_ID or CLIENT_SECRET not loaded. Please check config.json in plugin folder contains:\n"
        error_msg += '{\n  "client_id": "your_spotify_client_id",\n  "client_secret": "your_spotify_client_secret",\n  "username": "your_spotify_username"\n}'
        logging.error(f"[OAuth] {error_msg}")
        return generate_failure_response(error_msg)
    
    logging.info("[OAuth] Starting automated authorization flow...")
    logging.info(f"[OAuth] Using CLIENT_ID: {CLIENT_ID[:20]}...")
    
    try:
        # Step 1: Start local callback server in background
        logging.info("[OAuth] Step 1: Starting local callback server on port 8888...")
        server_thread = threading.Thread(
            target=lambda: start_oauth_callback_server(port=8888, timeout=120),
            daemon=True
        )
        server_thread.start()
        
        # Give server time to start
        time.sleep(0.5)
        
        # Step 2: Open browser to OAuth URL
        auth_url = get_spotify_auth_url()
        logging.info(f"[OAuth] Step 2: Opening browser to: {auth_url}")
        webbrowser.open(auth_url)
        
        logging.info("[OAuth] Waiting for user to authorize in browser...")
        logging.info("[OAuth] (Browser should open automatically)")
        
        # Step 3: Wait for callback server to receive code (with periodic heartbeats)
        wait_time = 0
        heartbeat_interval = 10  # Send heartbeat every 10 seconds
        while wait_time < 120:  # Total timeout: 2 minutes
            server_thread.join(timeout=heartbeat_interval)
            if not server_thread.is_alive() or oauth_callback_code or oauth_callback_error:
                break
            wait_time += heartbeat_interval
            send_status_message(f"Still waiting for browser authorization... ({wait_time}s elapsed)")
        
        # Step 4: Check results
        if oauth_callback_code:
            logging.info("[OAuth] Step 3: Authorization code received!")
            
            # Step 5: Exchange code for tokens
            logging.info("[OAuth] Step 4: Exchanging code for access token...")
            token_data = get_access_token(oauth_callback_code)
            
            ACCESS_TOKEN = token_data['access_token']
            REFRESH_TOKEN = token_data['refresh_token']
            
            # Step 6: Save tokens
            logging.info("[OAuth] Step 5: Saving tokens to auth.json...")
            save_auth_state(ACCESS_TOKEN, REFRESH_TOKEN)
            
            logging.info("[OAuth] ✓ Authorization complete! Tokens saved.")
            return generate_success_response({"message": "Successfully authenticated with Spotify! You're all set."})
            
        elif oauth_callback_error:
            error_msg = f"Authorization failed: {oauth_callback_error}"
            logging.error(f"[OAuth] {error_msg}")
            return generate_failure_response({"message": error_msg})
        else:
            error_msg = "Authorization timeout - no response from browser after 2 minutes"
            logging.error(f"[OAuth] {error_msg}")
            return generate_failure_response({"message": error_msg})
            
    except Exception as e:
        error_msg = f"Authorization error: {str(e)}"
        logging.error(f"[OAuth] {error_msg}")
        logging.exception("[OAuth] Full traceback:")
        return generate_failure_response({"message": error_msg})


def authorize_user():

    """
    Authorize the user using Spotify's API and return access/refresh tokens.
    LEGACY METHOD - Opens browser but requires manual URL copying.
    Use authorize_user_automated() for fully automated flow.
    """
    # Open the Spotify login page in the browser
    auth_url = get_spotify_auth_url()
    webbrowser.open(auth_url)


def complete_auth_user(callback_url): 
    global ACCESS_TOKEN
    global REFRESH_TOKEN
    
    try:
        # Extract the authorization code from the callback URL
        auth_code = extract_code_from_url(callback_url)
        if not auth_code:
            raise Exception("Authorization code not found in the callback URL.")

        # Exchange the authorization code for access and refresh tokens
        token_data = get_access_token(auth_code)
        logging.info("Successfully got token data from Spotify")
        
        ACCESS_TOKEN = token_data['access_token']
        REFRESH_TOKEN = token_data['refresh_token']
        
        if not REFRESH_TOKEN:
            raise Exception("No refresh token received from Spotify")

        logging.info("Saving tokens to auth file...")
        # Save the tokens to auth file
        save_auth_state(ACCESS_TOKEN, REFRESH_TOKEN)
        logging.info("Tokens saved successfully")

        try:
            devices = get_device_id()
            logging.info(f'Successfully connected to Spotify device')
            if not devices:
                logging.error("No devices connected")
        except Exception as e:
            logging.error(f'Error connecting to Spotify device {str(e)}:')
            return generate_failure_response({ 'message': f'Error connecting to Spotify device: {e}' })
        
        return generate_success_response({ 'message': f'User authorized successfully' })
    except Exception as e:
        logging.error(f"Error in complete_auth_user: {str(e)}")
        return generate_failure_response({ 'message': f'Authorization failed: {str(e)}' })

def main():
    """ Main entry point for the Spotify G-Assist plugin.
    
    Listens for commands on a pipe and processes them in a loop until shutdown.
    Handles initialization, command processing, and cleanup.
    
    Returns:
        int: 0 for successful execution, 1 for failure
    """
    global CLIENT_ID
    global CLIENT_SECRET
    global USERNAME
    global ACCESS_TOKEN
    global REFRESH_TOKEN
    SUCCESS = 0
    FAILURE = 1
    TOOL_CALLS_PROPERTY = 'tool_calls'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'params'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'
    CONFIG_FILE = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "config.json")
    AUTH_FILE = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "auth.json")

    try:
        # Read the IP from the configuration file
        logging.info(f'Loading configuration from: {CONFIG_FILE}')
        CLIENT_ID = get_client_id(CONFIG_FILE)
        CLIENT_SECRET = get_client_secret(CONFIG_FILE)
        USERNAME = get_username(CONFIG_FILE)
        
        if CLIENT_ID is None or CLIENT_SECRET is None:
            logging.error('Unable to read the configuration file. CLIENT_ID or CLIENT_SECRET is None')
            logging.error(f'Config file path: {CONFIG_FILE}')
            logging.error(f'Config file exists: {os.path.exists(CONFIG_FILE)}')
        else:
            logging.info(f'Configuration loaded successfully - CLIENT_ID: {CLIENT_ID[:20]}...')
    except Exception as e:
        logging.error(f'Error reading configuration file: {e}')
        logging.exception('Full traceback:')

    # Generate command handler mapping
    commands = generate_command_handlers()

    logging.info('Starting plugin.')
    
    # Initialize setup state machine
    global SETUP_STATE
    state_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "setup_state.json")
    SETUP_STATE = SetupState(state_file)
    logging.info(f'[STATE] Initialized setup state machine: {SETUP_STATE.current_state}')
    
    # Validate configuration on startup
    if SETUP_STATE.current_state == SetupState.CONFIGURED:
        # We think we're configured, but verify credentials still valid
        if not CLIENT_ID or not CLIENT_SECRET or len(CLIENT_ID) < 10:
            logging.warning("[STATE] Previously configured but credentials now invalid, resetting state")
            SETUP_STATE.reset()
        else:
            logging.info("[STATE] Configuration validated")
    
    # PHASE 1: Start heartbeat thread (tethered mode)
    # Determine initial state based on configuration
    initial_state = "ready" if SETUP_STATE.current_state == SetupState.CONFIGURED else "onboarding"
    start_continuous_heartbeat(state=initial_state, interval=5)
    logging.info(f'[TETHER] Started heartbeat thread with state={initial_state}')

    # Try to load existing tokens first
    try:
        ACCESS_TOKEN, REFRESH_TOKEN = get_auth_state(AUTH_FILE)
        if ACCESS_TOKEN is not None and REFRESH_TOKEN is not None:
            logging.info('Successfully loaded tokens from auth file')
            # Verify tokens are still valid
            try:
                devices = get_device_id()
                logging.info('Successfully verified tokens with Spotify')
            except Exception as e:
                logging.error(f'Error verifying tokens: {e}')
                ACCESS_TOKEN = None
                REFRESH_TOKEN = None
    except Exception as e:
        logging.error(f'Error loading auth state: {e}')
        ACCESS_TOKEN = None
        REFRESH_TOKEN = None

    while True:
        function = ''
        response = None
        input = read_command()
        if input is None:
            continue
        
        logging.info(f'Command: "{input}"')
        
        # PHASE 3: Handle user input passthrough messages
        if isinstance(input, dict) and input.get('msg_type') == 'user_input':
            user_input_text = input.get('content', '')
            logging.info(f'[INPUT] Received user input passthrough: "{user_input_text}"')
            
            # Handle during setup wizard
            if SETUP_STATE and SETUP_STATE.current_state != SetupState.CONFIGURED:
                logging.info(f"[WIZARD] User input during setup: '{user_input_text}'")
                
                # Check for help request
                if 'help' in user_input_text.lower():
                    logging.info("[WIZARD] User requested help during setup")
                    try:
                        webbrowser.open("https://developer.spotify.com/dashboard")
                        config_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "config.json")
                        if os.path.exists(config_file):
                            os.startfile(config_file)
                        response = generate_message_response("[OK] Re-opened dashboard and config file for you!\n\nContinue where you left off, then send me another message.")
                        write_response(response)
                        continue
                    except Exception as e:
                        logging.error(f"[WIZARD] Error opening help files: {e}")
                
                # Advance wizard with user input
                try:
                    response = execute_setup_wizard()
                    logging.info(f"[WIZARD] Got response from wizard: {str(response)[:200] if response else 'None'}")
                    
                    if response:
                        write_response(response)
                        logging.info(f"[WIZARD] Sent response to user input, length: {len(str(response))}")
                        
                        # PHASE 3: If response is awaiting more input, restart heartbeat WITHOUT dots
                        # Plugin is now quietly waiting for user - no need for visual dots
                        if response.get('awaiting_input', False):
                            start_continuous_heartbeat(state="onboarding", interval=5, show_dots=False)
                            logging.info("[WIZARD] Restarted heartbeat without dots (awaiting user input)")
                    else:
                        logging.error("[WIZARD] execute_setup_wizard() returned None/False!")
                except Exception as e:
                    logging.error(f"[WIZARD] Exception during user_input wizard execution: {e}")
                    logging.exception("Full traceback:")
                    
                continue
            else:
                # Plugin is configured - user input could be for other purposes
                logging.info(f"[INPUT] User input received (plugin configured): {user_input_text}")
                # For now, just acknowledge
                response = generate_message_response(f"Received: {user_input_text}")
                write_response(response)
                continue
        
        # PHASE 3: Handle termination messages
        if isinstance(input, dict) and input.get('msg_type') == 'terminate':
            logging.info('[TERMINATE] Received termination request from engine')
            reason = input.get('reason', 'unknown')
            response = generate_message_response(f"[OK] Plugin terminating ({reason})")
            write_response(response)
            stop_continuous_heartbeat()
            break  # Exit main loop
        
        # Don't stop heartbeat if we're in setup mode - keep it running!
        # Only stop heartbeat for regular commands when configured
        if SETUP_STATE and SETUP_STATE.current_state == SetupState.CONFIGURED:
            stop_continuous_heartbeat()
            logging.info("[TETHER] Stopped heartbeat (plugin configured)")

        # Check if we're in setup mode - ANY user message advances the wizard
        if isinstance(input, dict) and SETUP_STATE and SETUP_STATE.current_state != SetupState.CONFIGURED:
            # Extract user message if present
            user_message = ""
            if 'messages' in input and len(input['messages']) > 0:
                user_message = input['messages'][-1].get('content', '').lower()
            
            # Handle "help" request
            if 'help' in user_message:
                logging.info("[WIZARD] User requested help during setup")
                try:
                    webbrowser.open("https://developer.spotify.com/dashboard")
                    config_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "config.json")
                    if os.path.exists(config_file):
                        os.startfile(config_file)
                    response = generate_message_response("[OK] Re-opened dashboard and config file for you!\n\nContinue where you left off, then send me another message.")
                    write_response(response)
                    continue
                except Exception as e:
                    logging.error(f"[WIZARD] Error opening help files: {e}")
            
            # If user sent ANY message during setup (not just tool calls), advance wizard
            if user_message or not input.get(TOOL_CALLS_PROPERTY):
                logging.info(f"[WIZARD] User sent message during setup: '{user_message}'")
                response = execute_setup_wizard()
                if response:
                    write_response(response)
                    logging.info(f"[WIZARD] Sent response, length: {len(str(response))}")
                    
                    # PHASE 3: If response is awaiting more input, restart heartbeat WITHOUT dots
                    if response.get('awaiting_input', False):
                        start_continuous_heartbeat(state="onboarding", interval=5, show_dots=False)
                        logging.info("[WIZARD] Restarted heartbeat without dots (awaiting user input)")
                    
                continue
        
        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            logging.info(f'tool_calls: "{tool_calls}"')
            
            # Store the original command for retry after auth
            original_command = None
            
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call: 
                    cmd = tool_call[FUNCTION_PROPERTY]
                    logging.info(f'func: "{cmd}"')
                    
                    if cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND:
                        logging.info(f'cmd: "{cmd}"')
                        response = commands[cmd]()
                    else:
                        # For all other commands, check if we're in setup mode first
                        if SETUP_STATE and SETUP_STATE.current_state != SetupState.CONFIGURED:
                            logging.info(f'[COMMAND] In setup mode (state={SETUP_STATE.current_state}), starting interactive wizard')
                            response = execute_setup_wizard_interactive()
                            logging.info(f'[COMMAND] Interactive wizard completed: {str(response)[:200]}...')
                            
                            # PHASE 3: If wizard response is awaiting input, restart heartbeat WITHOUT dots
                            if response and response.get('awaiting_input', False):
                                start_continuous_heartbeat(state="onboarding", interval=5, show_dots=False)
                                logging.info("[WIZARD] Restarted heartbeat without dots (awaiting user input)")
                            
                            break
                        
                        # Check if app credentials are configured
                        if not CLIENT_ID or not CLIENT_SECRET:
                            logging.error('[COMMAND] CLIENT_ID or CLIENT_SECRET missing - starting interactive setup wizard')
                            response = execute_setup_wizard_interactive()
                            
                            # PHASE 3: If wizard response is awaiting input, restart heartbeat WITHOUT dots
                            if response and response.get('awaiting_input', False):
                                start_continuous_heartbeat(state="onboarding", interval=5, show_dots=False)
                                logging.info("[WIZARD] Restarted heartbeat without dots (awaiting user input)")
                            
                            break
                        
                        # Check if we need user authorization (OAuth tokens)
                        if ACCESS_TOKEN is None or REFRESH_TOKEN is None:
                            # Check if we have an auth_url in the file
                            try:
                                with open(AUTH_FILE, 'r') as file:
                                    data = json.load(file)
                                    if 'auth_url' in data:
                                        logging.info('Found auth_url in file, processing...')
                                        auth_response = execute_auth_command({"callback_url": data['auth_url']})
                                        if auth_response['success']:
                                            # Store the original command for retry
                                            original_command = tool_call
                                            # Break out of the loop to retry the command
                                            break
                            except Exception as e:
                                logging.error(f'Error checking auth file: {e}')
                            
                            # If we get here, we need to start new authorization
                            logging.info('Starting AUTOMATED authorization process...')
                            response = authorize_user_automated()
                            
                            # If authorization succeeded, retry the original command
                            if response.get('success'):
                                logging.info('Authorization successful, retrying original command...')
                                # Retry the command that failed due to auth
                                CONTEXT_PROPERTY = 'messages'
                                SYSTEM_INFO_PROPERTY = 'system_info'
                                if cmd in commands:
                                    response = commands[cmd](
                                        input[PARAMS_PROPERTY] if PARAMS_PROPERTY in input else None,
                                        input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in input else None,
                                        input[SYSTEM_INFO_PROPERTY] if SYSTEM_INFO_PROPERTY in input else None
                                    )
                            break
                        
                        # If we have valid tokens, execute the command
                        try:
                            logging.info(f'Executing command: {cmd} {tool_call}')
                            response = commands[cmd](tool_call[PARAMS_PROPERTY] if PARAMS_PROPERTY in tool_call else {})
                        except Exception as e:
                            response = generate_failure_response({'message': f'Spotify Error: {e}'})
                else:
                    response = generate_failure_response({ 'message': f'Unknown command "{cmd}"' })
            
            # If we have an original command to retry (after successful auth)
            if original_command is not None:
                cmd = original_command[FUNCTION_PROPERTY]
                logging.info(f'Retrying original command after auth: {cmd}')
                try:
                    response = commands[cmd](original_command[PARAMS_PROPERTY] if PARAMS_PROPERTY in original_command else {})
                except Exception as e:
                    response = generate_failure_response({'message': f'Spotify Error: {e}'})
        else:
            response = generate_failure_response({ 'message': 'Malformed input' })

        logging.info(f'Response: {response}')
        write_response(response)
        if function == SHUTDOWN_COMMAND:
            break

    sys.exit(SUCCESS)

def get_auth_state(auth_file: str) -> tuple[str | None, str | None]:
    """Gets the access and refresh tokens from the auth file.
    
    Args:
        auth_file (str): Path to the auth file
        
    Returns:
        tuple[str | None, str | None]: Tuple of (access_token, refresh_token) or (None, None) if not found
    """
    if os.path.exists(auth_file):
        try:
            logging.info(f"Reading auth file: {auth_file}")
            with open(auth_file, 'r') as file:
                content = file.read().strip()
                if not content:
                    logging.error("Auth file is empty")
                    return None, None
                    
                data = json.loads(content)
                logging.info("Auth file contents loaded")
                
                # First check if we have a pending auth URL
                if 'auth_url' in data:
                    logging.info("Found auth_url in file, processing...")
                    # Process the auth URL to get tokens
                    try:
                        complete_auth_user(data['auth_url'])
                        # Remove the auth_url from the file since we've processed it
                        data.pop('auth_url', None)
                        with open(auth_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        logging.info("Successfully processed auth_url and saved tokens")
                    except Exception as e:
                        logging.error(f"Error processing auth URL: {e}")
                        return None, None
                
                # Return the tokens if they exist
                access_token = data.get('access_token')
                refresh_token = data.get('refresh_token')
                
                if access_token and refresh_token:
                    logging.info("Found both access and refresh tokens in auth file")
                elif access_token:
                    logging.error("Found access token but no refresh token")
                    return None, None
                elif refresh_token:
                    logging.error("Found refresh token but no access token")
                    return None, None
                else:
                    logging.error("No tokens found in auth file")
                
                return access_token, refresh_token
        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON in auth file: {e}")
            return None, None
        except Exception as e:
            logging.error(f"Error reading auth file: {e}")
    else:
        logging.info(f"Auth file does not exist: {auth_file}")
    return None, None


def get_client_id(config_file: str) -> str | None:
    ''' Loads the client_id from the configuration file.

    @param[in] config_file  configuration file

    @return the client_id of the Spotify account or `None` if an error occurred
    reading the configuration file
    '''
    id = None
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            data = json.load(file)
            if 'client_id' in data:
                id = data['client_id']

    return id

def get_client_secret(config_file: str) -> str | None:
    ''' Loads the client_secret from the configuration file.

    @param[in] config_file  configuration file

    @return the client_secret of the Spotify account or `None` if an error occurred
    reading the configuration file
    '''
    secret = None
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            data = json.load(file)
            if 'client_secret' in data:
                secret = data['client_secret']

    return secret

def get_username(config_file: str) -> str | None:
    ''' Loads the username from the configuration file.

    @param[in] config_file  configuration file

    @return the username of the Spotify account or `None` if an error occurred
    reading the configuration file
    '''
    username = None
    if os.path.exists(config_file):
        with open(config_file, 'r') as file:
            data = json.load(file)
            if 'username' in data:
                username = data['username']

    return username

def generate_command_handlers() -> dict:
    ''' Generates the mapping of commands to their handlers.

    @return dictionay where the commands is the key and the handler is the value
    '''
    commands = dict()
    commands['initialize'] = execute_initialize_command
    commands['shutdown'] = execute_shutdown_command
    commands['authorize'] = execute_auth_command
    commands['spotify_setup'] = execute_setup_wizard_interactive  # Explicit setup command
    commands['spotify_start_playback'] = execute_play_command
    commands['spotify_pause_playback'] = execute_pause_command
    commands['spotify_next_track'] = execute_next_track_command
    commands['spotify_previous_track'] = execute_previous_track_command
    commands['spotify_shuffle_playback'] = execute_shuffle_command
    commands['spotify_set_volume'] = execute_volume_command
    commands['spotify_get_currently_playing'] = execute_currently_playing_command
    commands['spotify_queue_track'] = execute_queue_track_command
    commands['spotify_get_user_playlists'] = execute_get_user_playlists_command
    return commands

def read_command() -> dict | None:
    ''' Reads a command from the communication pipe.

    Returns:
        Command details if the input was proper JSON; `None` otherwise
    '''
    try:
        STD_INPUT_HANDLE = -10
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)

        # Read in chunks until we get the full message
        chunks = []
        while True:
            BUFFER_SIZE = 4096
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
            
            # Add the chunk we read
            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

             # If we read less than the buffer size, we're done
            if message_bytes.value < BUFFER_SIZE:
                break

        # Combine all chunks and parse JSON
        retval = ''.join(chunks)
        
        # Remove <<END>> token if present
        END_TOKEN = '<<END>>'
        if retval.endswith(END_TOKEN):
            retval = retval[:-len(END_TOKEN)]
        
        return json.loads(retval)

    except json.JSONDecodeError:
        logging.error(f'Received invalid JSON: {retval}')
        return None
    except Exception as e:
        logging.error(f'Exception in read_command(): {str(e)}')
        return None
    
def write_response(response:Response) -> None:
    ''' Writes a response to the communication pipe.

    Parameters:
        response: Response
    '''
    try:
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)
        
        # Log message type for debugging
        msg_type = response.get('type', 'response') if isinstance(response, dict) else 'unknown'
        logging.info(f'[PIPE] Writing message: type={msg_type}, length={message_len} bytes')

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
            None
        )

        if not success:
            error_code = windll.kernel32.GetLastError()
            logging.error(f'[PIPE] Write FAILED - type={msg_type}, error={error_code}')
        else:
            logging.info(f'[PIPE] Write OK - type={msg_type}, bytes={bytes_written.value}/{message_len}')

    except Exception as e:
        logging.error(f'Exception in write_response(): {str(e)}')

# generate_failure_response and generate_success_response moved to top of file (line 134-138)
# to be available for heartbeat function

def call_spotify_api(url: str, request_method: str, data) -> Response:
    """ Makes authenticated requests to the Spotify Web API.
    
    Args:
        url (str): The API endpoint path (will be appended to BASE_URL)
        request_method (str): HTTP method ('GET', 'POST', or 'PUT')
        data (dict, optional): JSON data to send with the request
        
    Returns:
        Response: The HTTP response from the Spotify API
        
    Note:
        Requires valid ACCESS_TOKEN to be set globally. Will attempt to refresh token if request fails with 401.
    """
    if not ACCESS_TOKEN:
        logging.error("No access token available for API call")
        return Response()
        
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    full_url = f"{BASE_URL}{url}"
    logging.info(f"Making {request_method} request to {full_url}")

    def make_request():
        if request_method == 'GET':
            return requests.get(full_url, headers=headers)
        elif request_method == 'POST':
            return requests.post(full_url, headers=headers)      
        elif request_method == 'PUT':
            headers["Content-Type"] = "application/json"
            if data != None:
                return requests.put(full_url, headers=headers, json=data)
            else: 
                return requests.put(full_url, headers=headers)

    # Make initial request
    response = make_request()
    logging.info(f"Initial request status code: {response.status_code}")
    
    # If we get a 401, try refreshing the token and retry once
    if response.status_code == 401:
        logging.info("Received 401, attempting to refresh token...")
        if refresh_access_token():
            # Update headers with new token
            headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
            logging.info("Token refreshed, retrying request...")
            # Retry request with new token
            response = make_request()
            logging.info(f"Retry request status code: {response.status_code}")
        else:
            logging.error("Failed to refresh token")
    
    if response.status_code != 200 and response.status_code != 204:
        logging.error(f"API request failed. Status code: {response.status_code}")
        logging.error(f"Response: {response.text}")
    
    return response

def get_user_id(): 
    ''' Retrieves a user's Spotify User ID from the users's Spotify username provided in the config file
        
    @return User ID from Spotify 
    ''' 
    url = "/me"
    response = call_spotify_api(url, 'GET', None)
    
    if response.status_code == 200:
        data = response.json()
        return data['id']
    else:
        return response.json()

def is_device_active(d):
    ''' Helper function to determine whether a user's Spotify device is active or not
        
    @param[in] d      device object

    @return True (device is active) OR False (device is not active)
    ''' 
    return not d['is_restricted']

def get_device() -> dict:
    """ Gets the first available and active Spotify playback device.
    
    Queries the Spotify API for all devices and returns the first one
    that is not restricted.
    
    Returns:
        dict: Device information containing id, name, type etc.
        None: If no active devices are found
        
    Raises:
        Exception: If API request fails
    """
    url = "/me/player/devices"
    response = call_spotify_api(url=url, request_method='GET', data=None)

    if response.status_code == 200:
        data = response.json()
        if 'devices' in data:
            if data['devices'] != 0:
                available_devices = filter(is_device_active, data['devices'])
                device = list(available_devices)[0]
                return device
    else:
        logging.error(f'Error getting device: {response.json()}')
        return response.json()
    
def get_device_id():
    ''' Get the id of the active device 

    @return the id of the active device
    '''
    device = get_device()
    return device['id']

def get_album_uri(params: dict) -> str:
    ''' Get the URI of the first result of an album query on Spotify 

    @param[in] params  function parameters

    @return the URI of the album
    '''
    try:
        query = f'album:"{params["name"]}"'
        if "artist" in params:
            query += f' artist:"{params["artist"]}"'
        search_term = urlencode({'q': query, 'type': params['type']})
        url = f"/search?{search_term}"
        response = call_spotify_api(url=url, request_method='GET', data=None)
        if response.status_code == 200:
            data = response.json()
            if 'albums' in data:
                return data['albums']['items'][0]['uri']

    except Exception as e:
        logging.error(f'Search error {e}')
        return None

def get_playlist_uri(params: dict) -> str:
    ''' Get the URI of the first result of a playlist query on Spotify 

    @param[in] params  function parameters

    @return the URI of the playlist
    '''
    try:
        query = f'"{params["name"]}"'
        search_term = urlencode({"q": query, 'type': params['type']})
        url = f"/search?{search_term}"
        response = call_spotify_api(url, request_method='GET', data=None)

        if response.status_code == 200:
            data = response.json()
            if 'playlists' in data:
                return data['playlists']['items'][0]['uri']
    except Exception as e:
        logging.error(f'Search error {e}')
        return None

def get_track_uri(params: dict) -> str:
    """ Searches Spotify for a track and returns its URI.
    
    Args:
        params (dict): Search parameters containing:
            - name (str): Track name to search for
            - artist (str, optional): Artist name for better matching
            - type (str): Must be 'track'
            
    Returns:
        str: Spotify URI for the first matching track
        None: If no matches found or search fails
        
    Example:
        params = {'name': 'Yesterday', 'artist': 'The Beatles', 'type': 'track'}
    """
    try:
        query = f'track:"{params["name"]}"'
        if "artist" in params:
            query += f' artist:"{params["artist"]}"'
        search_term = urlencode({"q": query, 'type': params['type']})
        url = f"/search?{search_term}"
        response = call_spotify_api(url, request_method='GET', data=None)

        if response.status_code == 200:
            data = response.json()
            if 'tracks' in data:
                return data['tracks']['items'][0]['uri']    
    except Exception as e:
        logging.error(f'Search error {e}')
        return None
    
def get_generic_uri(params: dict) -> str:
    ''' Get the URI of the first result of a track query on Spotify 

    @param[in] params  function parameters

    @return the URI of the track
    '''
    try:
        query = params["name"]
        if "artist" in params:
            query += f' artist:"{params["artist"]}"'
        search_term = urlencode({"q": query, 'type': 'track'})
        url = f"/search?{search_term}"
        response = call_spotify_api(url, request_method='GET', data=None)

        if response.status_code == 200:
            data = response.json()
            if 'tracks' in data:
                return data['tracks']['items'][0]['uri']   
    except Exception as e:
        logging.error(f'Search error {e}')
        return None

# COMMANDS

def execute_setup_wizard_interactive():
    """
    NON-BLOCKING setup wizard that advances state and returns immediately.
    Relies on background heartbeat thread and user re-triggering for next step.
    
    Returns:
        dict: Immediate response with current step instructions
    """
    global SETUP_STATE, CLIENT_ID, CLIENT_SECRET
    
    # Initialize state machine if needed
    if SETUP_STATE is None:
        state_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "setup_state.json")
        SETUP_STATE = SetupState(state_file)
    
    logging.info(f"[WIZARD] Executing setup wizard step")
    logging.info(f"[WIZARD] Current state: {SETUP_STATE.current_state}")
    
    # Execute current state logic ONCE
    result = execute_setup_wizard_state_once()
    
    # Check if setup is complete
    if SETUP_STATE.current_state == SetupState.CONFIGURED:
        send_state_change("ready")  # Notify engine setup is done
        stop_continuous_heartbeat()  # No longer need heartbeats
        logging.info("[WIZARD] Setup wizard complete - plugin configured")
        return generate_success_response({"message": "[OK] Spotify plugin is now configured and ready!"}, awaiting_input=False)  # PHASE 3: Exit passthrough
    
    # Not complete yet - return current step message
    # Heartbeat thread keeps connection alive
    # User will send another message to advance
    return result if result else generate_success_response({"message": "Please complete the current step and send another message."}, awaiting_input=True)  # PHASE 3: Stay in passthrough


def execute_setup_wizard_state_once() -> dict:
    """
    Execute ONE iteration of the current setup state.
    Checks conditions and advances state if ready.
    
    Returns:
        dict: Response message or None
    """
    global SETUP_STATE, CLIENT_ID, CLIENT_SECRET
    
    logging.info(f"[WIZARD] Executing state: {SETUP_STATE.current_state}")
    
    # State machine logic
    state = SETUP_STATE.current_state
    
    # STATE: UNCONFIGURED - Need to start setup process
    if state == SetupState.UNCONFIGURED:
        # Send initial status
        send_status_message("Starting Spotify plugin setup wizard...")
        
        message = """
SPOTIFY PLUGIN - FIRST TIME SETUP
====================================

Welcome! Let's get your Spotify plugin configured. This takes about 2 minutes.

I'm opening the Spotify Developer Dashboard in your browser right now...

YOUR TASK - Create a Spotify App:
   1. Click "Create App" button
   2. Fill in these EXACT values:
      - App Name: G-Assist Spotify
      - Redirect URI: http://127.0.0.1:8888/callback  [CRITICAL - use IP not localhost!]
      - Select "Web API" checkbox
   3. Click "Create"

When you're done creating the app, just send me ANY message (like "done" or "next")
and I'll guide you through the next step!

Opening dashboard now...
"""
        try:
            send_status_message("Opening Spotify Developer Dashboard...")
            import webbrowser
            # Force browser window to foreground on Windows
            if sys.platform == 'win32':
                webbrowser.get('windows-default').open("https://developer.spotify.com/dashboard", new=2, autoraise=True)
            else:
                webbrowser.open("https://developer.spotify.com/dashboard")
            
            SETUP_STATE.advance(SetupState.WAITING_APP_CREATION, "opened_dashboard")
            logging.info("[WIZARD] Opened dashboard, advanced to WAITING_APP_CREATION")
            
            # Heartbeat managed by interactive wizard polling loop
        except Exception as e:
            SETUP_STATE.record_error(str(e))
            message += f"\nError opening browser: {e}\nPlease manually visit: https://developer.spotify.com/dashboard"
        
        return generate_message_response(message, awaiting_input=True)  # PHASE 3: Stay in passthrough
    
    # STATE: WAITING_APP_CREATION - User is creating the app
    elif state == SetupState.WAITING_APP_CREATION:
        # Send status
        send_status_message("[OK] Dashboard opened. Now guiding you to get credentials...")
        
        message = """
STEP 2 - Get Your App Credentials
=====================================

Great! Now let's get your credentials.

In the Spotify Dashboard:
   1. Click on your app name (the one you just created)
   2. Click "Settings" button
   3. You'll see:
      - Client ID - Copy this!
      - Client Secret - Click "View client secret", then copy it!

I'm opening your config file in Notepad right now...

YOUR TASK - Paste Your Credentials:
   Replace the empty strings with what you copied:
   
   {
     "client_id": "PASTE_CLIENT_ID_HERE",
     "client_secret": "PASTE_CLIENT_SECRET_HERE",
     "username": "your_spotify_username"
   }
   
   SAVE the file!

After saving, send me ANY message (like "done") and I'll verify your credentials!

Opening config.json in Notepad...
"""
        try:
            send_status_message("Opening config.json for editing...")
            config_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "config.json")
            os.makedirs(os.path.dirname(config_file), exist_ok=True)
            
            # Create config file if it doesn't exist
            if not os.path.exists(config_file):
                with open(config_file, 'w') as f:
                    json.dump({"client_id": "", "client_secret": "", "username": ""}, f, indent=2)
            
            # Force Notepad to foreground
            os.startfile(config_file)
            time.sleep(0.5)
            # Try to bring window to front (Windows only)
            if sys.platform == 'win32':
                try:
                    import win32gui
                    import win32con
                    # Find Notepad window
                    def enum_callback(hwnd, results):
                        if 'config.json' in win32gui.GetWindowText(hwnd):
                            win32gui.SetForegroundWindow(hwnd)
                    win32gui.EnumWindows(enum_callback, None)
                except:
                    pass  # win32gui not available, skip focus forcing
            
            SETUP_STATE.advance(SetupState.WAITING_CREDENTIALS, "opened_config")
            logging.info("[WIZARD] Opened config.json, advanced to WAITING_CREDENTIALS")
            
            # Heartbeat managed by interactive wizard polling loop
        except Exception as e:
            SETUP_STATE.record_error(str(e))
            message += f"\nError opening config: {e}"
        
        return generate_message_response(message, awaiting_input=True)  # PHASE 3: Stay in passthrough
    
    # STATE: WAITING_CREDENTIALS - Verify credentials were entered
    elif state == SetupState.WAITING_CREDENTIALS:
        # Heartbeats sent automatically by background thread
        
        # Try to reload config
        config_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "config.json")
        try:
            reloaded_id = get_client_id(config_file)
            reloaded_secret = get_client_secret(config_file)
            
            if reloaded_id and reloaded_secret and len(reloaded_id) > 10:
                # Credentials look valid! Update globals
                CLIENT_ID = reloaded_id
                CLIENT_SECRET = reloaded_secret
                
                send_status_message("[OK] Credentials verified successfully!")
                SETUP_STATE.advance(SetupState.NEED_USER_AUTH, "credentials_verified")
                logging.info(f"[WIZARD] Credentials verified: CLIENT_ID={CLIENT_ID[:20]}...")
                message = """
[OK] CREDENTIALS VERIFIED!
=======================

Perfect! Your app credentials are saved and validated.

FINAL STEP - Authorize Your Account
=======================================

Now I need permission to access YOUR Spotify account.

Send me ANY message (like "authorize" or "go") and I'll:
   1. Open Spotify login in your browser
   2. You log in and click "Accept"
   3. I automatically catch the response
   4. DONE! You can start using Spotify commands!

This is the last step!
"""
                logging.info("[WIZARD] Credentials verified, ready for OAuth")
                return generate_message_response(message, awaiting_input=True)  # PHASE 3: Stay in passthrough
            else:
                # Still empty or invalid
                retry_msg = f" (Retry #{SETUP_STATE.retry_count})" if SETUP_STATE.retry_count > 0 else ""
                message = f"""
[WARNING] CREDENTIALS NOT FOUND{retry_msg}
=====================================

I checked the config file but the credentials are still empty or invalid.

Please make sure you:
   [x] Opened: C:\\ProgramData\\NVIDIA Corporation\\nvtopps\\rise\\plugins\\spotify\\config.json
   [x] Pasted your Client ID and Client Secret
   [x] SAVED the file!

Current values I see:
   - Client ID: {reloaded_id if reloaded_id else '(empty)'}
   - Client Secret: {reloaded_secret[:10] + '...' if reloaded_secret and len(reloaded_secret) > 10 else '(empty or too short)'}

After you save the config file, send me ANY message to verify again.

Need help? I can re-open the files for you - just say "help"
"""
                SETUP_STATE.record_error("credentials_empty")
                # Heartbeat managed by interactive wizard polling loop
                return generate_message_response(message, awaiting_input=True)  # PHASE 3: Stay in passthrough
        except Exception as e:
            SETUP_STATE.record_error(str(e))
            return generate_message_response(f"[ERROR] Error checking credentials: {e}\n\nPlease verify config.json is valid JSON.", awaiting_input=True)  # PHASE 3
    
    # STATE: NEED_USER_AUTH - Ready to start OAuth
    elif state == SetupState.NEED_USER_AUTH:
        # Send status
        send_status_message("[OK] Credentials verified! Starting OAuth authorization...")
        
        SETUP_STATE.advance(SetupState.WAITING_OAUTH, "starting_oauth")
        
        # Start automated OAuth flow
        send_status_message("Opening browser for Spotify login...")
        send_status_message("Please click 'Accept' when prompted to authorize the app.")
        send_status_message("Waiting for authorization (up to 2 minutes)...")
        
        oauth_result = authorize_user_automated()
        
        send_status_message("Processing authorization response...")
        
        if oauth_result.get('success'):
            SETUP_STATE.advance(SetupState.CONFIGURED, "oauth_complete")
            send_state_change("ready")  # Notify engine onboarding is complete
            send_status_message("[OK] Setup complete! Plugin is ready.")
            return generate_message_response("""
[OK] SETUP COMPLETE!
====================

Congratulations! Your Spotify plugin is fully configured and ready to use!

You can now use commands like:
   - "Play my music on Spotify"
   - "Skip to next song"
   - "What's playing on Spotify?"
   - And more!

Enjoy your music!
""", awaiting_input=False)  # PHASE 3: Setup done, exit passthrough
        else:
            SETUP_STATE.record_error(oauth_result.get('message', 'OAuth failed'))
            # Make sure oauth_result has awaiting_input field
            oauth_result['awaiting_input'] = False  # PHASE 3: OAuth failed, exit passthrough
            return oauth_result
    
    # STATE: CONFIGURED - All set up
    elif state == SetupState.CONFIGURED:
        return generate_message_response("[OK] Spotify plugin is already configured and ready to use!", awaiting_input=False)  # PHASE 3: Exit passthrough
    
    # Default fallback
    return generate_message_response("Unknown setup state. Please try again or contact support.", awaiting_input=False)  # PHASE 3: Error, exit passthrough

# Alias for backwards compatibility
def execute_setup_wizard():
    """Legacy name - calls interactive version"""
    return execute_setup_wizard_interactive()


def execute_initialize_command() -> dict:
    ''' Command handler for initialize function

        1. Initializes Spotify Client and authenticates user
        2. Finds active device 
    @return function response
    '''
    global CLIENT_ID, CLIENT_SECRET
    
    # Check if app credentials are configured
    if not CLIENT_ID or not CLIENT_SECRET:
        logging.error('[INIT] CLIENT_ID or CLIENT_SECRET not configured')
        return execute_setup_wizard_interactive()
    
    try:
        # Check if we have tokens in auth.json
        auth_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "auth.json")
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(auth_file), exist_ok=True)
        
        # Check if file exists and has valid content
        needs_auth = True
        if os.path.exists(auth_file):
            try:
                with open(auth_file, 'r') as file:
                    content = file.read().strip()
                    if content:  # Check if file is not empty
                        auth_data = json.loads(content)
                        if 'access_token' in auth_data and 'refresh_token' in auth_data:
                            global ACCESS_TOKEN, REFRESH_TOKEN
                            ACCESS_TOKEN = auth_data['access_token']
                            REFRESH_TOKEN = auth_data['refresh_token']
                            # Verify tokens are still valid
                            try:
                                devices = get_device_id()
                                logging.info('Successfully loaded and verified tokens from auth.json')
                                return generate_success_response({"message": "Successfully connected to Spotify using credentials from auth.json"})
                            except Exception as e:
                                logging.error(f'Error verifying tokens: {e}')
                                # Clear invalid tokens
                                ACCESS_TOKEN = None
                                REFRESH_TOKEN = None
                                # Clear the auth file
                                with open(auth_file, 'w') as f:
                                    json.dump({}, f)
            except json.JSONDecodeError:
                logging.error('Invalid JSON in auth.json, will start new authorization')
                # Clear the invalid file
                with open(auth_file, 'w') as f:
                    json.dump({}, f)
            except Exception as e:
                logging.error(f'Error reading auth file: {e}')
                needs_auth = True

        if needs_auth:
            # Start AUTOMATED authorization with local callback server
            logging.info('[OAuth] No valid tokens found, starting automated authorization...')
            return authorize_user_automated()
    except Exception as e:
        logging.error(f'Error in initialization: {e}')
        return generate_failure_response({'message': f'Error connecting to Spotify: {e}'})


def execute_shutdown_command() -> dict:
    ''' Command handler for shutdown function

        @return function response
    '''
    return generate_success_response()

def execute_auth_command(params) -> dict:
    ''' Command handler for authorization function
    
    Args:
        params (dict): Parameters containing:
            - callback_url (str): The URL that Spotify redirected to after authorization
            
    Returns:
        dict: Response indicating success or failure
    '''
    try:
        if 'callback_url' not in params:
            return generate_failure_response({
                'message': 'Missing callback_url parameter. Please provide the URL you were redirected to after authorizing.'
            })
            
        response = complete_auth_user(params['callback_url'])
        if response['success']:
            # Remove the auth_url from the file since we've processed it
            try:
                with open(os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "auth.json"), 'r') as file:
                    data = json.load(file)
                data.pop('auth_url', None)
                with open(os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "auth.json"), 'w') as file:
                    json.dump(data, file, indent=2)
            except Exception as e:
                logging.error(f"Error cleaning up auth file: {e}")
        return response
    except Exception as e:
        return generate_failure_response({ 
            'message': f'Authorization failed: {str(e)}. Please try the authorization process again.' 
        })
    

def execute_play_command(params: dict) -> dict:
    """ Starts or resumes Spotify playback.
    
    Can play specific tracks, albums, playlists or resume current playback.
    
    Args:
        params (dict): Optional parameters containing:
            - type (str): Content type ('track', 'album', 'playlist')
            - name (str): Name of content to play
            - artist (str, optional): Artist name for better search matching
            
    Returns:
        dict: Response containing:
            - success (bool): Whether the command succeeded
            - message (str): Success/failure message
            
    Example params:
        {'type': 'track', 'name': 'Yesterday', 'artist': 'The Beatles'}
    """
    try:
        device = get_device_id()
        uri = None
        response = None
        url = f"/me/player/play?device_id={device}"

        if params is not None and params != {}:
            if 'type' in params and params['type'] == 'album':
                uri = get_album_uri(params)
                body = ({"context_uri": f'{uri}'})
            elif 'type' in params and params['type'] == 'track':
                uri = get_track_uri(params)
                body = ({"uris": [f'{uri}']})
            elif 'type' in params and params['type'] == 'playlist':
                uri = get_playlist_uri(params)
                body = ({"context_uri": f'{uri}'})
            else: #defaults search type to track 
                uri = get_generic_uri(params)
                body = ({"uris": [f'{uri}']})
                
            response = call_spotify_api(url, request_method='PUT', data=body)
        else:
            #resume current playback
            response = call_spotify_api(url, request_method='PUT', data=None)

        if response is not None and (response.status_code == 204 or response.status_code == 200): 
            return generate_success_response({ 'message': 'Playback successfully started.' })
        elif response is not None and response.status_code == 403:
            # 403 Forbidden - provide helpful guidance
            error_msg = """
[ERROR] Spotify Playback Forbidden (403)

This usually means one of the following:

1. NO ACTIVE DEVICE
   - You need to open Spotify (desktop app or web player)
   - Start playing something to activate a device
   - Then try the command again

2. SPOTIFY PREMIUM REQUIRED
   - Spotify's API requires a Premium subscription for playback control
   - Free accounts cannot use these features

3. DEVICE IN PRIVATE SESSION
   - Check if your Spotify is in "Private Session" mode
   - Turn it off and try again

Please open Spotify, start playing, and try again!
"""
            return generate_failure_response({ 'message': error_msg })
        elif response is not None and response.status_code == 404:
            return generate_failure_response({ 'message': 'Track or device not found. Make sure Spotify is open and try again.' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: Status {response.status_code if response else "No response"}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def execute_pause_command(params: dict) -> dict:
    ''' Command handler for `spotify_start_playback` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        device = get_device_id()
        url = f"/me/player/pause?device_id={device}"
        response = call_spotify_api(url=url, request_method='PUT', data=None)    

        if response.status_code == 204 or response.status_code == 200: 
            return generate_success_response({ 'message': 'Playback has paused.' })
        elif response.status_code == 403:
            return generate_failure_response({ 'message': 'Playback Error (403): You need Spotify Premium and an active device. Open Spotify and start playing, then try again.' })
        elif response.status_code == 404:
            return generate_failure_response({ 'message': 'No active device found. Please open Spotify and start playing.' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: Status {response.status_code}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def execute_next_track_command(params: dict) -> dict:
    ''' Command handler for `spotify_next_track` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        device = get_device_id()
        url = f"/me/player/next?device_id={device}"
        response = call_spotify_api(url=url, request_method='POST', data=None)    

        if response.status_code == 204 or response.status_code == 200: 
            return generate_success_response({ 'message': 'Track was skipped.' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {response}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def execute_previous_track_command(params: dict) -> dict:
    ''' Command handler for `spotify_previous_track` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        device = get_device_id()
        url = f"/me/player/previous?device_id={device}"
        response = call_spotify_api(url=url, request_method='POST', data=None)    
        
        if response.status_code == 204 or response.status_code == 200: 
            return generate_success_response({ 'message': 'Track was skipped to the previous track.' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {response}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def execute_shuffle_command(params: dict) -> dict:    
    ''' Command handler for `spotify_shuffle_playback` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        device = get_device_id()
        url = f"/me/player/shuffle?device_id={device}&state={params['state']}"
        response = call_spotify_api(url=url, request_method='PUT', data=None)    

        if response.status_code == 204 or response.status_code == 200: 
            state_text = ""
            if params['state'] is not None:
                state_text = " on" if params['state'] is True else " off"
            return generate_success_response({ 'message': f'Shuffle was toggled{state_text}.' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {response}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })
    
def execute_volume_command(params: dict) -> dict:
    """ Sets the volume on the active Spotify playback device.
    
    Args:
        params (dict): Parameters containing:
            - volume_level (int): Volume level 0-100
            
    Returns:
        dict: Response containing:
            - success (bool): Whether command succeeded
            - message (str): Success/failure message
            
    Note:
        Only works on devices that support volume control
    """
    try:
        device = get_device()
        device_id = device['id']

        if 'volume_level' in params and 'supports_volume' in device and device['supports_volume'] is True:
            url = f"/me/player/volume?volume_percent={params['volume_level']}&device_id={device_id}"
            response = call_spotify_api(url=url, request_method='PUT', data=None)    
        else:
            return generate_failure_response({ 'message': 'Volume Error: Device does not support volume control.' })
        
        if response.status_code == 204 or response.status_code == 200: 
            volume_text = ""
            if params["volume_level"]:
                volume_text = f" to {params['volume_level']}"
            return generate_success_response({ 'message': f'Volume was set{volume_text}.' })
        else: 
            return generate_failure_response({ 'message': f'Volume Error: {response}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Volume Error: {e}' })
    
def execute_currently_playing_command(params: dict) -> dict:
    ''' Command handler for `spotify_get_currently_playing` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        url = f"/me/player/currently-playing"
        response = call_spotify_api(url=url, request_method='GET', data=None)    

        if response.status_code == 204 or response.status_code == 200: 
            results = response.json()
            
            if results['is_playing'] is True:
                track_name = results['item']['name']
                artist_name = results['item']['artists'][0]['name'] if results['item']['artists'][0]['name'] is not None else ''
                artist_text = f" by {artist_name}" if artist_name else ''
                return generate_success_response({'message': f'You\'re playing "{track_name}"{artist_text}'})
            else:
                track_name = results['item']['name']
                artist_name = results['item']['artists'][0]['name'] if results['item']['artists'][0]['name'] is not None else ''
                artist_text = f" by {artist_name}" if artist_name else ''
                return generate_success_response({'message': f'The current track is "{track_name}"{artist_text}, but it\'s not currently playing.'})
        else: 
            return generate_success_response({ 'message': 'There is no track currently playing.' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def execute_queue_track_command(params:dict) -> dict:
    ''' Command handler for `spotify_queue_track` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        device = get_device_id()

        if params['name']:
            uri = get_track_uri(params)
            url = f"/me/player/queue?uri={uri}&device_id={device}"
            response = call_spotify_api(url=url, request_method='POST', data=None)    

            if response.status_code == 204 or response.status_code == 200: 
                return generate_success_response({ 'message': 'Track was queued.' })
            else: 
                return generate_failure_response({ 'message': f'Playback Error: {response}' })
        return generate_failure_response({ 'message': 'No track was specified.' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def execute_get_user_playlists_command(params: dict) -> dict:
    ''' Command handler for `spotify_get_user_playlists` function

    @param[in] params  function parameters

    @return function response
    '''
    try:
        playlists = None
        limit = 10

        if('limit' in params and params['limit'] is not None):
            limit=params['limit']

        url = f"/me/playlists?limit={limit}"
        response = call_spotify_api(url=url, request_method='GET', data=None)    

        if response.status_code == 200:
            results = response.json()
            items = results['items']
            # Strip emojis and special characters from playlist names
            playlists = list(map(lambda s: ''.join(char for char in s['name'] if ord(char) < 128), items))
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {response}' })
        
        if playlists is not None: 
            playlist_text = '\n\t'.join(playlists)
            return generate_success_response({ 'message': f'Top Playlists:\n\t{playlist_text}' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {results}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

def refresh_access_token() -> bool:
    """Refreshes the access token using the refresh token.
    
    Returns:
        bool: True if refresh was successful, False otherwise
    """
    global ACCESS_TOKEN
    global REFRESH_TOKEN
    
    try:
        logging.info("Attempting to refresh access token...")
        if not REFRESH_TOKEN:
            logging.error("No refresh token available")
            return False
            
        logging.info("Making refresh token request to Spotify...")
        token_response = requests.post(
            AUTH_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": REFRESH_TOKEN,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if token_response.status_code != 200:
            logging.error(f"Error refreshing token. Status code: {token_response.status_code}")
            logging.error(f"Response: {token_response.text}")
            return False

        token_data = token_response.json()
        ACCESS_TOKEN = token_data['access_token']
        logging.info("Successfully refreshed access token")
        
        # Save the new tokens to auth file
        save_auth_state(ACCESS_TOKEN, REFRESH_TOKEN)
        return True
    except Exception as e:
        logging.error(f"Exception in refresh_access_token: {str(e)}")
        return False

def save_auth_state(access_token: str, refresh_token: str) -> None:
    """Saves the access and refresh tokens to the auth file.
    
    Args:
        access_token (str): The access token to save
        refresh_token (str): The refresh token to save
    """
    auth_file = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "spotify", "auth.json")
    try:
        # Ensure directory exists
        os.makedirs(os.path.dirname(auth_file), exist_ok=True)
        
        data = {
            'access_token': access_token,
            'refresh_token': refresh_token
        }
        logging.info(f"Saving tokens to {auth_file}")
        with open(auth_file, 'w') as file:
            json.dump(data, file, indent=2)
        logging.info("Tokens saved successfully")
    except Exception as e:
        logging.error(f"Error saving auth state: {e}")
        raise

if __name__ == '__main__':
    main()
