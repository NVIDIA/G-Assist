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

# Settings specific to the user's system. This is temporary until a
# configuration file is added to the plugin.
LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'spotify-plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

REDIRECT_URI="https://open.spotify.com"
SCOPE = "user-library-read user-read-currently-playing user-read-playback-state user-modify-playback-state playlist-read-private playlist-read-collaborative"

# Spotify API endpoints
AUTHORIZATION_URL = "https://accounts.spotify.com/authorize"
AUTH_URL = "https://accounts.spotify.com/api/token"
BASE_URL = "https://api.spotify.com/v1"

AUTH_STATE = None
ACCESS_TOKEN = None
REFRESH_TOKEN = None


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

def authorize_user():

    """
    Authorize the user using Spotify's API and return access/refresh tokens.
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
        CLIENT_ID = get_client_id(CONFIG_FILE)
        CLIENT_SECRET = get_client_secret(CONFIG_FILE)
        USERNAME = get_username(CONFIG_FILE)
        if CLIENT_ID is None or CLIENT_SECRET is None:
            logging.error('Unable to read the configuration file. Using default Client')
    except Exception as e:
        logging.error(f'Error reading configuration file: {e}')

    # Generate command handler mapping
    commands = generate_command_handlers()

    logging.info('Starting plugin.')

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
                        # For all other commands, check if we need authorization
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
                            logging.info('Starting new authorization process')
                            authorize_user()
                            response = generate_success_response({
                                "message": "Please follow these steps:\n"
                                          "1. A browser window has opened - log in to Spotify and authorize the app\n"
                                          "2. After authorizing, you'll be redirected to a URL\n"
                                          "3. Copy the ENTIRE URL from your browser\n"
                                          "4. Create or edit the file at this location:\n"
                                          f"   `{AUTH_FILE}`\n"
                                          "5. Add the URL to the file in this format:\n"
                                          "   ```\n"
                                          "   {\n"
                                          "     \"auth_url\": \"YOUR_COPIED_URL\"\n"
                                          "   }\n"
                                          "    \n"
                                          "6. Save the file and try your command again"
                            })
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

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
            None
        )

        if not success:
            logging.error('Error writing to response pipe')

    except Exception as e:
        logging.error(f'Exception in write_response(): {str(e)}')

def generate_failure_response(body:dict=None) -> dict:
    ''' Generates a response indicating failure.

    @param[in] data  information to be attached to the response

    @return dictionary response (to be converted to JSON when writing to the
    communications pipe)
    '''
    response = body.copy() if body is not None else dict()
    response['success'] = False
    return response

def generate_success_response(body:dict=None) -> dict:
    ''' Generates a response indicating success.

    @param[in] data  information to be attached to the response

    @return dictionary response (to be converted to JSON when writing to the
    communications pipe)
    '''
    response = body.copy() if body is not None else dict()
    response['success'] = True
    return response

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

def execute_initialize_command() -> dict:
    ''' Command handler for initialize function

        1. Initializes Spotify Client and authenticates user
        2. Finds active device 
    @return function response
    '''
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
            # Start new authorization
            authorize_user()
            logging.info(f'Opened browser for Spotify authorization')
            return generate_success_response({
                "message": "Please follow these steps:\n"
                          "1. A browser window has opened - log in to Spotify and authorize the app\n"
                          "2. After authorizing, you'll be redirected to a URL\n"
                          "3. Copy the ENTIRE URL from your browser\n"
                          "4. Create or edit the file at this location:\n"
                          f"   `{auth_file}`\n"
                          "5. Add the URL to the file in this format:\n"
                          "   ```\n"
                          "   {\n"
                          "     \"auth_url\": \"YOUR_COPIED_URL\"\n"
                          "   }\n"
                          "   \n"
                          "6. Save the file and try your command again"
            })
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
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {response}' })
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
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {response}' })
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
