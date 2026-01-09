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
from typing import Any, Callable, Dict, Optional
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
SETUP_COMPLETE = False
WIZARD_STEP = 0
PENDING_CALL: Optional[Dict[str, Any]] = None  # {"func": callable, "args": {...}}

# OAuth callback server state
oauth_callback_code = None
oauth_callback_error = None
oauth_server_running = False


def store_pending_call(func: Callable, **kwargs):
    """Store a function call to execute after setup completes."""
    global PENDING_CALL
    PENDING_CALL = {"func": func, "args": kwargs}
    logger.info(f"[SETUP] Stored pending call: {func.__name__}({kwargs})")


def execute_pending_call() -> Optional[str]:
    """Execute the stored pending call if one exists. Returns result or None."""
    global PENDING_CALL
    if not PENDING_CALL:
        return None
    
    func = PENDING_CALL["func"]
    args = PENDING_CALL["args"]
    PENDING_CALL = None  # Clear before executing
    
    logger.info(f"[SETUP] Executing pending call: {func.__name__}({args})")
    return func(_from_pending=True, **args)


def load_config() -> Dict[str, Any]:
    """Load Spotify configuration."""
    global CLIENT_ID, CLIENT_SECRET, SETUP_COMPLETE
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            CLIENT_ID = config.get("client_id", "")
            CLIENT_SECRET = config.get("client_secret", "")
            
            if CLIENT_ID and len(CLIENT_ID) > 20 and \
               CLIENT_SECRET and len(CLIENT_SECRET) > 20:
                SETUP_COMPLETE = True
                logger.info("Config loaded successfully")
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


def get_setup_instructions_step1() -> str:
    """Return first step of setup wizard."""
    return f"""_
**Spotify Plugin - First Time Setup (1/2)**

Welcome! Let's set up your Spotify app. This takes about **2 minutes**.

---

**Create Your Spotify App**

I'm opening the Spotify Developer Dashboard for you now...

1. Log in with your Spotify account
2. Click **Create App**
3. Fill in the form:
   - App Name: `G-Assist Spotify`
   - Redirect URI: `{get_redirect_uri()}`
   - Select **Web API** checkbox
4. Click **Create**

Say **"next"** or **"continue"** when you're ready for the next step.\r"""


def get_setup_instructions_step2() -> str:
    """Return second step of setup wizard."""
    return f"""_
**Spotify Plugin - First Time Setup (2/2)**

Great! Now let's add your credentials.

---

**Get Your Credentials**

1. Click **Settings** in your app
2. Copy your **Client ID**
3. Click **View client secret** and copy it

_(Keep your client secret private!)_

---

**Add Them to the Config File**

I'm opening the config file for you:
```
{CONFIG_FILE}
```

Paste your credentials:
```
{{
  "client_id": "YOUR_CLIENT_ID_HERE",
  "client_secret": "YOUR_CLIENT_SECRET_HERE"
}}
```

Say **"next"** or **"continue"** when you've saved the file, and I'll complete your original request.\r"""


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
    
    logger.info("Starting OAuth flow...")
    
    oauth_callback_code = None
    oauth_callback_error = None
    oauth_server_running = True
    
    config = load_config()
    port = config.get("redirect_port", 8888)
    
    # Start callback server
    try:
        server = HTTPServer(('127.0.0.1', port), OAuthCallbackHandler)
        logger.info(f"Started callback server on port {port}")
    except Exception as e:
        logger.error(f"Failed to start callback server: {e}")
        return False, f"Could not start auth server on port {port}. Is it in use?"
    
    server_thread = threading.Thread(target=lambda: server.handle_request(), daemon=True)
    server_thread.start()
    
    # Open auth URL
    redirect_uri = get_redirect_uri()
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
    }
    auth_url = f"{AUTHORIZATION_URL}?{urlencode(params)}"
    logger.info(f"Opening auth URL with redirect_uri: {redirect_uri}")
    
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")
        return False, f"Could not open browser: {e}"
    
    # Wait for callback
    timeout = 120
    start = time.time()
    while oauth_server_running and (time.time() - start) < timeout:
        time.sleep(0.5)
    
    elapsed = time.time() - start
    logger.info(f"OAuth wait completed after {elapsed:.1f}s. code={bool(oauth_callback_code)}, error={oauth_callback_error}")
    
    if oauth_callback_code:
        # Exchange code for tokens
        try:
            logger.info("Exchanging code for tokens...")
            response = requests.post(AUTH_URL, data={
                "grant_type": "authorization_code",
                "code": oauth_callback_code,
                "redirect_uri": redirect_uri,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
            })
            data = response.json()
            logger.info(f"Token response keys: {data.keys()}")
            if "access_token" in data:
                ACCESS_TOKEN = data["access_token"]
                REFRESH_TOKEN = data.get("refresh_token")
                save_tokens()
                logger.info("OAuth successful!")
                return True, "Successfully authenticated with Spotify!"
            else:
                logger.error(f"Token exchange failed: {data}")
                return False, f"Token exchange failed: {data.get('error_description', data)}"
        except Exception as e:
            logger.error(f"OAuth error: {e}")
            return False, f"OAuth error: {e}"
    elif oauth_callback_error:
        logger.error(f"OAuth callback error: {oauth_callback_error}")
        return False, f"Authorization failed: {oauth_callback_error}"
    else:
        logger.error("OAuth timeout - no callback received")
        return False, "Authorization timeout - did the browser open? Check your redirect URI in Spotify Dashboard."


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
def spotify_start_playback(name: str = "", type: str = "track", artist: str = "", _from_pending: bool = False):
    """
    Start or resume Spotify playback.
    
    Args:
        name: Track/album/artist name to play
        type: Content type (track, album, artist)
        artist: Artist name for better matching
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global SETUP_COMPLETE
    
    load_config()
    load_tokens()
    
    if not SETUP_COMPLETE or not CLIENT_ID or not CLIENT_SECRET:
        global WIZARD_STEP
        WIZARD_STEP = 0  # Reset in case of re-setup
        store_pending_call(spotify_start_playback, name=name, type=type, artist=artist)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        try:
            webbrowser.open("https://developer.spotify.com/dashboard")
        except:
            pass
        return get_setup_instructions_step1()
    
    if not is_authenticated():
        if not _from_pending:
            plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    
    device = get_device_id()
    if not device:
        return (
            "**No active Spotify device found.**\n\n"
            "Please open Spotify on any device and start playing something, then try again."
        )
    
    if name:
        if not _from_pending:
            plugin.stream("_ ")  # Close engine's italic
        plugin.stream(f"_Searching for {type}: {name}..._\n\n")
        
        # Search for content - artists don't use type prefix in query
        if type == "artist":
            query = name
        else:
            query = f'{type}:"{name}"'
            if artist:
                query += f' artist:"{artist}"'
        
        search_url = f"/search?{urlencode({'q': query, 'type': type})}"
        logger.info(f"Search URL: {search_url}")
        r = spotify_api(search_url)
        
        if r and r.status_code == 200:
            try:
                data = r.json()
                if not data:
                    return f"Could not find {type}: {name}"
                    
                logger.info(f"Search response keys: {data.keys()}")
                
                uri = None
                body = None
                display_info = ""
                
                if type == "track":
                    tracks_data = data.get("tracks") or {}
                    items = tracks_data.get("items") or []
                    # Filter out None items
                    items = [i for i in items if i]
                    if items:
                        track = items[0]
                        uri = track.get("uri")
                        body = {"uris": [uri]}
                        
                        track_name = track.get("name", "Unknown Track")
                        artists = ", ".join(a.get("name", "") for a in (track.get("artists") or []))
                        album_data = track.get("album") or {}
                        album_name = album_data.get("name", "")
                        
                        display_info = f"Now playing **{track_name}**"
                        if artists:
                            display_info += f" by {artists}"
                        if album_name:
                            display_info += f" from *{album_name}*"
                        
                elif type == "album":
                    albums_data = data.get("albums") or {}
                    items = albums_data.get("items") or []
                    items = [i for i in items if i]
                    if items:
                        album = items[0]
                        uri = album.get("uri")
                        body = {"context_uri": uri}
                        
                        album_name = album.get("name", "Unknown Album")
                        artists = ", ".join(a.get("name", "") for a in (album.get("artists") or []))
                        total_tracks = album.get("total_tracks", 0)
                        release_date = album.get("release_date") or ""
                        release_year = release_date[:4] if release_date else ""
                        
                        display_info = f"Now playing album **{album_name}**"
                        if artists:
                            display_info += f" by {artists}"
                        if release_year:
                            display_info += f" ({release_year})"
                        if total_tracks:
                            display_info += f" — {total_tracks} tracks"
                        
                elif type == "artist":
                    artists_data = data.get("artists") or {}
                    items = artists_data.get("items") or []
                    items = [i for i in items if i]
                    if items:
                        artist_item = items[0]
                        uri = artist_item.get("uri")
                        body = {"context_uri": uri}
                        
                        artist_name = artist_item.get("name", "Unknown Artist")
                        genres = artist_item.get("genres") or []
                        followers_data = artist_item.get("followers") or {}
                        followers = followers_data.get("total", 0)
                        
                        display_info = f"Now playing **{artist_name}**"
                        if genres:
                            display_info += f" ({', '.join(genres[:2])})"
                        if followers:
                            display_info += f" — {followers:,} followers"
                
                if not uri or not body:
                    return f"Could not find {type}: {name}"
                
                r = spotify_api(f"/me/player/play?device_id={device}", "PUT", body)
                if r and r.status_code in [200, 204]:
                    return display_info
                elif r and r.status_code == 403:
                    # Parse Spotify error for more info
                    try:
                        error_data = r.json()
                        reason = error_data.get("error", {}).get("reason", "")
                        if reason == "PREMIUM_REQUIRED":
                            return "**Spotify Premium required** for playback control. Please open Spotify and start playing manually."
                        logger.error(f"Playback 403 error: {error_data}")
                    except:
                        pass
                    return "**Spotify Premium required** for playback control. Please open Spotify and start playing."
                else:
                    status = r.status_code if r else "No response"
                    logger.error(f"Failed to start playback, status: {status}")
                    return "**Error:** Failed to start playback."
                    
            except Exception as e:
                import traceback
                logger.error(f"Error processing search results: {e}\n{traceback.format_exc()}")
                return f"Error: {e}"
        else:
            status = r.status_code if r else "No response"
            logger.error(f"Search failed with status: {status}")
            return f"**Error:** Search failed for: {name}"
    else:
        # Resume playback
        r = spotify_api(f"/me/player/play?device_id={device}", "PUT")
        logger.info(f"Resume playback response: r={r is not None}, status={r.status_code if r else 'None'}")
        if r and r.status_code in [200, 204]:
            # Get current track info
            time.sleep(0.3)
            
            current = spotify_api("/me/player/currently-playing")
            if current and current.status_code == 200:
                data = current.json()
                item = data.get("item", {})
                if item:
                    track_name = item.get("name", "Unknown")
                    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
                    return f"Resumed **{track_name}** by {artists}"
            
            return "Playback resumed"
        elif r and r.status_code == 403:
            # Parse Spotify error for more info
            try:
                error_data = r.json()
                reason = error_data.get("error", {}).get("reason", "")
                message = error_data.get("error", {}).get("message", "")
                logger.error(f"Resume playback 403: reason={reason}, message={message}")
                if reason == "PREMIUM_REQUIRED":
                    return "**Spotify Premium required** for playback control. Please open Spotify and start playing manually."
            except Exception as e:
                logger.error(f"Could not parse 403 response: {e}")
            return "**Spotify Premium required** for playback control. Please open Spotify and start playing."
        else:
            status = r.status_code if r else "No response"
            try:
                error_body = r.json() if r else None
                logger.error(f"Resume playback failed: status={status}, body={error_body}")
            except:
                logger.error(f"Resume playback failed: status={status}")
            return "**Error:** Failed to resume playback."


@plugin.command("spotify_pause_playback")
def spotify_pause_playback():
    """Pause Spotify playback."""
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    device = get_device_id()
    if not device:
        return "No active Spotify device found."
    
    r = spotify_api(f"/me/player/pause?device_id={device}", "PUT")
    if r and r.status_code in [200, 204]:
        return "Paused"
    return "Failed to pause playback."


@plugin.command("spotify_next_track")
def spotify_next_track():
    """Skip to next track."""
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    device = get_device_id()
    r = spotify_api(f"/me/player/next?device_id={device}", "POST")
    if r and r.status_code in [200, 204]:
        # Brief delay to let Spotify update, then get current track
        time.sleep(0.5)
        
        current = spotify_api("/me/player/currently-playing")
        if current and current.status_code == 200:
            data = current.json()
            item = data.get("item", {})
            if item:
                track_name = item.get("name", "Unknown")
                artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
                return f"Skipped to **{track_name}** by {artists}"
        
        return "Skipped to next track"
    return "Failed to skip track."


@plugin.command("spotify_previous_track")
def spotify_previous_track():
    """Go to previous track."""
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    device = get_device_id()
    r = spotify_api(f"/me/player/previous?device_id={device}", "POST")
    if r and r.status_code in [200, 204]:
        # Brief delay to let Spotify update, then get current track
        time.sleep(0.5)
        
        current = spotify_api("/me/player/currently-playing")
        if current and current.status_code == 200:
            data = current.json()
            item = data.get("item", {})
            if item:
                track_name = item.get("name", "Unknown")
                artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
                return f"Back to **{track_name}** by {artists}"
        
        return "Playing previous track"
    return "Failed to go back."


@plugin.command("spotify_get_currently_playing")
def spotify_get_currently_playing():
    """Get currently playing track."""
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    r = spotify_api("/me/player/currently-playing")
    if r and r.status_code == 200:
        data = r.json()
        item = data.get("item", {})
        
        if not item:
            return "Nothing is playing."
        
        track_name = item.get("name", "Unknown Track")
        artists = ", ".join(a.get("name", "") for a in item.get("artists", []))
        album_name = item.get("album", {}).get("name", "")
        duration_ms = item.get("duration_ms", 0)
        progress_ms = data.get("progress_ms", 0)
        
        # Format duration as mm:ss
        def format_time(ms):
            seconds = ms // 1000
            return f"{seconds // 60}:{seconds % 60:02d}"
        
        progress_str = f"{format_time(progress_ms)} / {format_time(duration_ms)}"
        
        if data.get("is_playing"):
            status = "Now playing"
        else:
            status = "Paused"
        
        response = f"{status}: **{track_name}** by {artists}"
        if album_name:
            response += f" from *{album_name}*"
        response += f" ({progress_str})"
        
        return response
    return "Nothing is playing."


@plugin.command("spotify_set_volume")
def spotify_set_volume(volume_level: int = 50):
    """
    Set Spotify volume.
    
    Args:
        volume_level: Volume 0-100
    """
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    # Clamp volume to valid range
    volume_level = max(0, min(100, volume_level))
    
    device = get_device_id()
    r = spotify_api(f"/me/player/volume?volume_percent={volume_level}&device_id={device}", "PUT")
    if r and r.status_code in [200, 204]:
        return f"Volume set to {volume_level}%"
    return "**Error:** Failed to set volume."


@plugin.command("spotify_shuffle_playback")
def spotify_shuffle_playback(state: bool = True):
    """
    Toggle shuffle mode.
    
    Args:
        state: True to enable shuffle, False to disable
    """
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    device = get_device_id()
    state_str = "true" if state else "false"
    r = spotify_api(f"/me/player/shuffle?state={state_str}&device_id={device}", "PUT")
    if r and r.status_code in [200, 204]:
        return f"Shuffle {'enabled' if state else 'disabled'}"
    return "**Error:** Failed to set shuffle mode."


@plugin.command("spotify_queue_track")
def spotify_queue_track(name: str = "", type: str = "track", artist: str = ""):
    """
    Add a track to the playback queue.
    
    Args:
        name: Track/album name to queue
        type: Content type (track, album)
        artist: Artist name for better matching
    """
    load_config()
    load_tokens()
    
    if not is_authenticated():
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        plugin.stream("_ ")  # Close engine's italic
    
    if not name:
        return "Please specify a track name to queue."
    
    # Search for the track
    query = f'{type}:"{name}"'
    if artist:
        query += f' artist:"{artist}"'
    
    search_url = f"/search?{urlencode({'q': query, 'type': 'track'})}"
    r = spotify_api(search_url)
    
    if r and r.status_code == 200:
        data = r.json()
        if data.get("tracks", {}).get("items"):
            track = data["tracks"]["items"][0]
            uri = track["uri"]
            track_name = track.get("name", "Unknown")
            artists = ", ".join(a.get("name", "") for a in track.get("artists", []))
            
            # Add to queue
            r = spotify_api(f"/me/player/queue?uri={uri}", "POST")
            if r and r.status_code in [200, 204]:
                return f"Added **{track_name}** by {artists} to queue"
            else:
                return "**Error:** Failed to add to queue."
        else:
            return f"Could not find: {name}"
    return "**Error:** Search failed."


@plugin.command("spotify_get_user_playlists")
def spotify_get_user_playlists(limit: int = 10, _from_pending: bool = False):
    """
    Get user's playlists.
    
    Args:
        limit: Number of playlists to return (default 10)
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global SETUP_COMPLETE
    
    load_config()
    load_tokens()
    
    # Check if configured
    if not SETUP_COMPLETE or not CLIENT_ID or not CLIENT_SECRET:
        global WIZARD_STEP
        WIZARD_STEP = 0
        store_pending_call(spotify_get_user_playlists, limit=limit)
        logger.info("[COMMAND] Not configured - starting setup wizard")
        plugin.set_keep_session(True)
        try:
            webbrowser.open("https://developer.spotify.com/dashboard")
        except:
            pass
        return get_setup_instructions_step1()
    
    # Check if authenticated, trigger OAuth if not
    if not is_authenticated():
        if not _from_pending:
            plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_Starting Spotify authorization..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
    else:
        if not _from_pending:
            plugin.stream("_ ")  # Close engine's italic
    
    limit = max(1, min(50, limit))  # Clamp to valid range
    
    logger.info(f"Fetching playlists with limit={limit}")
    r = spotify_api(f"/me/playlists?limit={limit}")
    
    if r is None:
        logger.error("spotify_get_user_playlists: API returned None")
        return "Could not connect to Spotify API."
    
    logger.info(f"Playlists response status: {r.status_code}")
    
    # Handle 401 by re-authenticating
    if r.status_code == 401:
        plugin.stream("_Token expired, re-authenticating..._\n\n")
        success, msg = do_oauth_flow()
        if not success:
            return msg
        # Retry the request
        r = spotify_api(f"/me/playlists?limit={limit}")
        if r is None:
            return "Could not connect to Spotify API."
    
    if r.status_code == 200:
        try:
            data = r.json()
            playlists = data.get("items", [])
            
            if not playlists:
                return "You don't have any playlists."
            
            lines = [f"Your top {len(playlists)} playlists:"]
            for i, p in enumerate(playlists, 1):
                name = p.get("name", "Unknown")
                tracks = p.get("tracks", {}).get("total", 0)
                lines.append(f"{i}. **{name}** ({tracks} tracks)")
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Error parsing playlists: {e}")
            return "Failed to parse playlist data."
    else:
        try:
            error_data = r.json()
            logger.error(f"Playlists API error: {error_data}")
        except:
            logger.error(f"Playlists API error: {r.text}")
        return f"Failed to get playlists (status {r.status_code})."


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE, WIZARD_STEP
    
    load_config()
    load_tokens()
    
    if SETUP_COMPLETE:
        # Config is valid - verify with OAuth and execute pending call
        if not is_authenticated():
            plugin.stream("_ ")  # Close engine's italic
            plugin.stream("_Spotify credentials verified! Starting authorization..._\n\n")
            success, msg = do_oauth_flow()
            if success:
                result = execute_pending_call()
                if result is not None:
                    plugin.set_keep_session(False)
                    return result
                else:
                    plugin.set_keep_session(False)
                    return msg
            else:
                plugin.set_keep_session(True)
                return (
                    "**Authorization failed.** Could not complete Spotify OAuth.\n\n"
                    "Please try again or check your credentials."
                )
        else:
            # Already authenticated
            plugin.stream("_ ")  # Close engine's italic
            plugin.stream("_Spotify plugin configured!_\n\n")
            result = execute_pending_call()
            if result is not None:
                plugin.set_keep_session(False)
                return result
            else:
                plugin.set_keep_session(False)
                return ""
    
    # Advance wizard
    if WIZARD_STEP == 0:
        WIZARD_STEP = 1
        plugin.set_keep_session(True)
        # Open config file
        try:
            if not os.path.exists(CONFIG_FILE):
                os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
                with open(CONFIG_FILE, "w") as f:
                    json.dump({"client_id": "", "client_secret": ""}, f, indent=2)
            os.startfile(CONFIG_FILE)
        except:
            pass
        return get_setup_instructions_step2()
    else:
        # User says done but config not valid
        plugin.set_keep_session(True)
        return (
            "**Credentials not found.** The config file is still empty or invalid.\n\n"
            "Please make sure you:\n"
            "1. Pasted your **Client ID** and **Client Secret**\n"
            "2. **Saved** the file\n\n"
            "Then say **\"next\"** or **\"continue\"** to verify."
        )


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Spotify plugin (SDK version)...")
    load_config()
    load_tokens()
    plugin.run()
