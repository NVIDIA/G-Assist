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
    # Step 1: Open the Spotify login page in the browser
    auth_url = get_spotify_auth_url()
    webbrowser.open(auth_url)


def complete_auth_user(callback_url): 
    global ACCESS_TOKEN
    global REFRESH_TOKEN
    
    # Step 3: Extract the authorization code from the callback URL
    auth_code = extract_code_from_url(callback_url)
    if not auth_code:
        raise Exception("Authorization code not found in the callback URL.")

    # Step 4: Exchange the authorization code for access and refresh tokens
    token_data = get_access_token(auth_code)
    ACCESS_TOKEN = token_data['access_token']
    REFRESH_TOKEN = token_data['refresh_token']

    print(ACCESS_TOKEN)
    print(REFRESH_TOKEN)
    try:
        devices = get_device_id()
        print(devices)
        if not devices:
            logging.error("No devices connected")
    except Exception as e:
        logging.error(f"Error connecting to Spotify device {str(e)}:")
        return generate_failure_response({ 'message': f'Error connecting to Spotify device: {e}' })
    
    return generate_success_response()

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

    try:
        AUTH_URL = get_auth_state(AUTH_FILE)
        logging.info(f'AUTH_URL: {AUTH_URL}')
        if AUTH_URL is not None:    
            logging.info(f'Executing auth command')
            execute_auth_command({"callback_url": AUTH_URL})
            logging.info(f'ACCESS_TOKEN: {ACCESS_TOKEN}')
    except Exception as e:
        logging.error(f'Error getting auth state: {e}')

    # Generate command handler mapping
    commands = generate_command_handlers()

    # For demo purposes, we need to manually enter the Client ID and Secret
    try:
        logging.info('Starting plugin.')
    except Exception as e:
        sys.exit(FAILURE)

    while True:
        FUNCTION_PROPERTY = 'func'
        PARAMS_PROPERTY = 'params'

        function = ''
        response = None
        input = read_command()
        if input is None:
            # Error reading command; continue
            continue
        logging.info(f'Command: "{input}"')

        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            logging.info(f'tool_calls: "{tool_calls}"')
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call: 
                    cmd = tool_call[FUNCTION_PROPERTY]
                    logging.info(f'func: "{cmd}"')
                    if(cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND):
                        logging.info(f'cmd: "{cmd}"')
                        response = commands[cmd]()
                    else: 
                        try: 
                            if ACCESS_TOKEN is None:
                                logging.info(f'Authorizing Spotify')
                                AUTH_URL = get_auth_state(AUTH_FILE)
                                logging.info(f'AUTH_URL: {AUTH_URL}')
                                if AUTH_URL is not None:
                                    logging.info(f'Executing auth command')
                                    execute_auth_command({"callback_url": AUTH_URL})
                                else: 
                                    execute_initialize_command()
                                    continue
                            logging.info(f'Executing command: {cmd} {tool_call}')
                            response = commands[cmd](tool_call[PARAMS_PROPERTY] if PARAMS_PROPERTY in tool_call else {})
                        except Exception as e:
                            response = generate_failure_response({'message': f'Spotify Error: {e}'})
                else:
                    response = generate_failure_response({ 'message': f'Unknown command "{cmd}"' })
        else:
            response = generate_failure_response({ 'message': 'Malformed input' })

        logging.info(f'Response: {response}')
        write_response(response)
        if function == SHUTDOWN_COMMAND:
            break

    sys.exit(SUCCESS)

def get_auth_state(auth_file: str) -> str | None:
    if os.path.exists(auth_file):
        with open(auth_file, 'r') as file:
            data = json.load(file)
            if 'auth_state' in data:
                return data['auth_state']
            else:
                logging.info(f'No auth state found in {auth_file}')
                return None
    else:
        logging.info(f'No auth file found in {auth_file}')
        return None


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
        Requires valid ACCESS_TOKEN to be set globally
    """
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    full_url = f"{BASE_URL}{url}"

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
        authorize_user()
        logging.info(f'Connected to Spotify for ID {CLIENT_ID}')
        return generate_success_response({"message": "Grant permissions and paste the full URL you were redirected to here: "})
    except Exception as e:
        logging.error(f'Error connecting to Spotify for ID {CLIENT_ID}')
        return generate_failure_response({'message': f'Error connecting to Spotify. Could not find credentials. {e}'})


def execute_shutdown_command() -> dict:
    ''' Command handler for shutdown function

        @return function response
    '''
    return generate_success_response()

def execute_auth_command(params) -> dict:
    ''' Command handler for shutdown function

        @return function response
    '''

    complete_auth_user(params['callback_url'])

    return generate_success_response({ 'message': f'User authorized' })
    

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
            return generate_success_response({ 'message': f'Playback successfully started.' })
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
            return generate_success_response({ 'message': f'Playback has paused.' })
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
            return generate_success_response({ 'message': f'Track was skipped.' })
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
            return generate_success_response({ 'message': f'Track was skipped to the previous track.' })
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
            return generate_failure_response({ 'message': f'Volume Error: Device does not support volume control.' })
        
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
                return generate_success_response({'message': f"You're playing {track_name}{artist_text}"})
            else:
                track_name = results['item']['name']
                artist_name = results['item']['artists'][0]['name'] if results['item']['artists'][0]['name'] is not None else ''
                artist_text = f" by {artist_name}" if artist_name else ''
                return generate_success_response({'message': f'The current track is "{track_name}"{artist_text}, but it\'s not currently playing.'})
        else: 
            return generate_success_response({ 'message': f'There is no track currently playing.' })
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
                return generate_success_response({ 'message': f'Track was queued.' })
            else: 
                return generate_failure_response({ 'message': f'Playback Error: {response}' })
        return generate_failure_response({ 'message': f'No track was specified.' })
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
            return generate_success_response({ 'message': f'Top Playlists: \n{playlist_text}' })
        else: 
            return generate_failure_response({ 'message': f'Playback Error: {results}' })
    except Exception as e:
        return generate_failure_response({ 'message': f'Playback Error: {e}' })

if __name__ == '__main__':
    main()
