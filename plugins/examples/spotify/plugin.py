"""
Spotify Plugin for G-Assist - V2 SDK Version

Control Spotify playback with OAuth authentication.
"""

import os
import sys

# ============================================================================
# PATH SETUP - Must be FIRST before any third-party imports!
# ============================================================================
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# Now we can import third-party libraries
import json
import logging
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Any, Dict, Optional
from urllib.parse import urlencode, urlparse, parse_qs
import threading
import time

import requests

try:
    from gassist_sdk import Plugin
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "spotify"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
AUTH_FILE = os.path.join(PLUGIN_DIR, "auth.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Spotify API endpoints
AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
AUTH_URL = "https://accounts.spotify.com/api/token"
BASE_URL = "https://api.spotify.com/v1"
SCOPE = "user-library-read user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative"

DEFAULT_CONFIG = {
    "client_id": "",
    "client_secret": "",
    "username": "",
    "redirect_port": 8888,
}

# ============================================================================
# GLOBAL STATE
# ============================================================================
CLIENT_ID: Optional[str] = None
CLIENT_SECRET: Optional[str] = None
ACCESS_TOKEN: Optional[str] = None
REFRESH_TOKEN: Optional[str] = None
WIZARD_STEP = 0

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


def load_config() -> Dict[str, Any]:
    """Load Spotify configuration."""
    global CLIENT_ID, CLIENT_SECRET
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            CLIENT_ID = config.get("client_id", "")
            CLIENT_SECRET = config.get("client_secret", "")
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()


def load_tokens():
    """Load OAuth tokens from auth file."""
    global ACCESS_TOKEN, REFRESH_TOKEN
    try:
        if os.path.isfile(AUTH_FILE):
            with open(AUTH_FILE, "r") as f:
                auth = json.load(f)
            ACCESS_TOKEN = auth.get("access_token")
            REFRESH_TOKEN = auth.get("refresh_token")
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")


def save_tokens():
    """Save OAuth tokens to auth file."""
    try:
        with open(AUTH_FILE, "w") as f:
            json.dump({
                "access_token": ACCESS_TOKEN,
                "refresh_token": REFRESH_TOKEN
            }, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")


def is_configured() -> bool:
    """Check if Spotify is properly configured."""
    return bool(CLIENT_ID and len(CLIENT_ID) > 20 and CLIENT_SECRET and len(CLIENT_SECRET) > 20)


def is_authenticated() -> bool:
    """Check if we have valid tokens."""
    return bool(ACCESS_TOKEN and REFRESH_TOKEN)


def get_redirect_uri() -> str:
    """Get OAuth redirect URI."""
    config = load_config()
    port = config.get("redirect_port", 8888)
    return f"http://127.0.0.1:{port}/callback"


def get_setup_step1() -> str:
    """First setup step - create Spotify app."""
    return f"""_
**Spotify Plugin - Setup (1/2)**

Let's set up your Spotify plugin. This takes about **2 minutes**.

---

**Step 1: Create a Spotify App**

I'm opening the Spotify Developer Dashboard now...

1. Click **Create App**
2. Fill in:
   - App Name: `G-Assist Spotify`
   - Redirect URI: `{get_redirect_uri()}`
   - Select **Web API** checkbox
3. Click **Create**

When done, send me any message to continue!\r"""


def get_setup_step2() -> str:
    """Second setup step - enter credentials."""
    return f"""_
**Spotify Plugin - Setup (2/2)**

Great! Now let's add your credentials.

---

**Step 2: Get Your Credentials**

1. Click **Settings** in your app
2. Copy your **Client ID**
3. Click **View client secret** and copy it

---

**Step 3: Configure the Plugin**

Open the config file at:
```
{CONFIG_FILE}
```

Paste your credentials:
```
{{
  "client_id": "YOUR_CLIENT_ID_HERE",
  "client_secret": "YOUR_CLIENT_SECRET_HERE",
  "username": "your_spotify_username"
}}
```

Save the file and try the command again!\r"""


# OAuth Callback Handler
oauth_callback_code = None
oauth_callback_error = None
oauth_server_running = False


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global oauth_callback_code, oauth_callback_error, oauth_server_running
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if 'code' in params:
            oauth_callback_code = params['code'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<h1>Authentication Successful!</h1><p>You can close this window.</p>")
        elif 'error' in params:
            oauth_callback_error = params['error'][0]
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(f"<h1>Authentication Failed</h1><p>{oauth_callback_error}</p>".encode())
        
        oauth_server_running = False
    
    def log_message(self, format, *args):
        pass


def do_oauth_flow() -> tuple[bool, str]:
    """Perform OAuth authorization flow."""
    global oauth_callback_code, oauth_callback_error, oauth_server_running
    global ACCESS_TOKEN, REFRESH_TOKEN
    
    oauth_callback_code = None
    oauth_callback_error = None
    oauth_server_running = True
    
    config = load_config()
    port = config.get("redirect_port", 8888)
    
    # Start callback server
    server = HTTPServer(('127.0.0.1', port), OAuthCallbackHandler)
    server_thread = threading.Thread(target=lambda: server.handle_request(), daemon=True)
    server_thread.start()
    
    # Open auth URL
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": get_redirect_uri(),
        "scope": SCOPE,
    }
    auth_url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
    webbrowser.open(auth_url)
    
    # Wait for callback
    timeout = 120
    start = time.time()
    while oauth_server_running and (time.time() - start) < timeout:
        time.sleep(0.5)
    
    if oauth_callback_code:
        # Exchange code for tokens
        try:
            response = requests.post(AUTH_URL, data={
                "grant_type": "authorization_code",
                "code": oauth_callback_code,
                "redirect_uri": get_redirect_uri(),
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            })
            data = response.json()
            if "access_token" in data:
                ACCESS_TOKEN = data["access_token"]
                REFRESH_TOKEN = data.get("refresh_token")
                save_tokens()
                return True, "Successfully authenticated with Spotify!"
            else:
                return False, f"Token exchange failed: {data}"
        except Exception as e:
            return False, f"OAuth error: {e}"
    elif oauth_callback_error:
        return False, f"Authorization failed: {oauth_callback_error}"
    else:
        return False, "Authorization timeout"


def refresh_token() -> bool:
    """Refresh the access token."""
    global ACCESS_TOKEN
    
    if not REFRESH_TOKEN:
        return False
    
    try:
        response = requests.post(AUTH_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": REFRESH_TOKEN,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        })
        data = response.json()
        if "access_token" in data:
            ACCESS_TOKEN = data["access_token"]
            save_tokens()
            return True
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
    return False


def spotify_api(endpoint: str, method: str = "GET", data: Dict = None):
    """Make authenticated Spotify API request."""
    global ACCESS_TOKEN
    
    if not ACCESS_TOKEN:
        return None
    
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    url = f"{BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            r = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            r = requests.post(url, headers=headers, timeout=10)
        elif method == "PUT":
            headers["Content-Type"] = "application/json"
            r = requests.put(url, headers=headers, json=data, timeout=10)
        else:
            return None
        
        # Retry with refresh if 401
        if r.status_code == 401:
            if refresh_token():
                headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
                if method == "GET":
                    r = requests.get(url, headers=headers, timeout=10)
                elif method == "POST":
                    r = requests.post(url, headers=headers, timeout=10)
                elif method == "PUT":
                    r = requests.put(url, headers=headers, json=data, timeout=10)
        
        return r
    except Exception as e:
        logger.error(f"API error: {e}")
        return None


def get_device_id():
    """Get first available Spotify device."""
    r = spotify_api("/me/player/devices")
    if r and r.status_code == 200:
        data = r.json()
        devices = data.get("devices", [])
        for d in devices:
            if not d.get("is_restricted"):
                return d["id"]
    return None


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Control Spotify playback"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("spotify_start_playback")
def spotify_start_playback(name: str = "", type: str = "track", artist: str = ""):
    """
    Start or resume Spotify playback.
    
    Args:
        name: Track/album/playlist name to play
        type: Content type (track, album, playlist)
        artist: Artist name for better matching
    """
    load_config()
    load_tokens()
    
    if not is_configured():
        plugin.set_keep_session(True)
        try:
            webbrowser.open("https://developer.spotify.com/dashboard")
        except:
            pass
        return get_setup_step1()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg  # Already escaped by prior stream
    
    device = get_device_id()
    if not device:
        return (
            "**No active Spotify device found.**\n\n"
            "Please open Spotify on any device and start playing something, then try again."
        )
    
    if name:
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream(f"_Searching for {type}: {name}..._")
        
        # Search for content
        query = f'{type}:"{name}"'
        if artist:
            query += f' artist:"{artist}"'
        
        search_url = f"/search?{urlencode({'q': query, 'type': type})}"
        r = spotify_api(search_url)
        
        if r and r.status_code == 200:
            data = r.json()
            
            uri = None
            if type == "track" and data.get("tracks", {}).get("items"):
                uri = data["tracks"]["items"][0]["uri"]
                body = {"uris": [uri]}
            elif type == "album" and data.get("albums", {}).get("items"):
                uri = data["albums"]["items"][0]["uri"]
                body = {"context_uri": uri}
            elif type == "playlist" and data.get("playlists", {}).get("items"):
                uri = data["playlists"]["items"][0]["uri"]
                body = {"context_uri": uri}
            else:
                return f"Could not find {type}: {name}"
            
            r = spotify_api(f"/me/player/play?device_id={device}", "PUT", body)
            if r and r.status_code in [200, 204]:
                return f"**Now playing:** {name}"
            else:
                return "**Error:** Failed to start playback."
        else:
            return f"**Error:** Search failed for: {name}"
    else:
        # Resume playback
        r = spotify_api(f"/me/player/play?device_id={device}", "PUT")
        if r and r.status_code in [200, 204]:
            return "Playback resumed."
        elif r and r.status_code == 403:
            return "**Spotify Premium required** for playback control. Please open Spotify and start playing."
        else:
            return "**Error:** Failed to resume playback."


@plugin.command("spotify_pause_playback")
def spotify_pause_playback():
    """Pause Spotify playback."""
    load_tokens()
    
    if not is_authenticated():
        return "_ Not authenticated. Please use a playback command first."
    
    device = get_device_id()
    if not device:
        return "_ No active Spotify device found."
    
    r = spotify_api(f"/me/player/pause?device_id={device}", "PUT")
    if r and r.status_code in [200, 204]:
        return "_ Playback paused."
    return "_ **Error:** Failed to pause playback."


@plugin.command("spotify_next_track")
def spotify_next_track():
    """Skip to next track."""
    load_tokens()
    
    if not is_authenticated():
        return "_ Not authenticated. Please use a playback command first."
    
    device = get_device_id()
    r = spotify_api(f"/me/player/next?device_id={device}", "POST")
    if r and r.status_code in [200, 204]:
        return "_ Skipped to next track."
    return "_ **Error:** Failed to skip track."


@plugin.command("spotify_previous_track")
def spotify_previous_track():
    """Go to previous track."""
    load_tokens()
    
    if not is_authenticated():
        return "_ Not authenticated."
    
    device = get_device_id()
    r = spotify_api(f"/me/player/previous?device_id={device}", "POST")
    if r and r.status_code in [200, 204]:
        return "_ Playing previous track."
    return "_ **Error:** Failed to go back."


@plugin.command("spotify_get_currently_playing")
def spotify_get_currently_playing():
    """Get currently playing track."""
    load_tokens()
    
    if not is_authenticated():
        return "_ Not authenticated. Please use a playback command first."
    
    r = spotify_api("/me/player/currently-playing")
    if r and r.status_code == 200:
        data = r.json()
        if data.get("is_playing"):
            track = data.get("item", {}).get("name", "Unknown")
            artist = data.get("item", {}).get("artists", [{}])[0].get("name", "Unknown")
            return f"_ **Now playing:** {track} by {artist}"
        else:
            track = data.get("item", {}).get("name", "Nothing")
            return f"_ **Paused:** {track}"
    return "_ Nothing is playing."


@plugin.command("spotify_set_volume")
def spotify_set_volume(volume_level: int = 50):
    """
    Set Spotify volume.
    
    Args:
        volume_level: Volume 0-100
    """
    load_tokens()
    
    if not is_authenticated():
        return "_ Not authenticated."
    
    device = get_device_id()
    r = spotify_api(f"/me/player/volume?volume_percent={volume_level}&device_id={device}", "PUT")
    if r and r.status_code in [200, 204]:
        return f"_ Volume set to {volume_level}%."
    return "_ **Error:** Failed to set volume."


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global WIZARD_STEP
    
    load_config()
    
    if not is_configured():
        # Not configured - setup wizard
        if WIZARD_STEP == 0:
            WIZARD_STEP = 1
            plugin.set_keep_session(True)
            try:
                if not os.path.exists(CONFIG_FILE):
                    with open(CONFIG_FILE, "w") as f:
                        json.dump(DEFAULT_CONFIG, f, indent=2)
                os.startfile(CONFIG_FILE)
            except:
                pass
            return get_setup_step2()
        else:
            # Check if config is now valid
            load_config()
            if is_configured():
                plugin.stream("_ ")  # Close engine's italic
                plugin.stream("_Credentials verified! Starting authorization..._\n\n")
                success, msg = do_oauth_flow()
                WIZARD_STEP = 0
                plugin.set_keep_session(False)
                return msg  # Already escaped by prior stream
            else:
                plugin.set_keep_session(True)
                return (
                    "_ **Credentials not found or invalid.**\n\n"
                    "Please make sure you:\n"
                    "  1. Pasted your Client ID and Client Secret\n"
                    "  2. SAVED the file\n\n"
                    "Then send me another message."
                )
    else:
        # Configured but maybe not authenticated
        load_tokens()
        if not is_authenticated():
            plugin.stream("_ ")  # Close engine's italic
            plugin.stream("_Starting Spotify authorization..._\n\n")
            success, msg = do_oauth_flow()
            plugin.set_keep_session(False)
            return msg  # Already escaped by prior stream
        else:
            plugin.set_keep_session(False)
            return "_ _Spotify is configured and ready!_"


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Spotify plugin (SDK version)...")
    load_config()
    load_tokens()
    plugin.run()
