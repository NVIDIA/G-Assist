# G-Assist Spotify Plugin

Transform your music experience with G-Assist! This plugin lets you control Spotify using simple voice commands or the G-Assist interface. Whether you want to play your favorite tracks, manage playlists, or control playback, managing your Spotify has never been easier.

## What Can It Do?
- Control Spotify playback (play, pause, next, previous)
- Toggle shuffle mode
- Adjust volume levels
- Access and manage your playlists
- Seamlessly integrates with your G-Assist setup
- Easy to set up and configure

## Before You Start
Make sure you have:
- Windows PC
- Python 3.x installed on your computer
- Spotify Account (Free or Premium)
- Spotify Developer Account
- G-Assist installed on your system

💡 **Tip**: Some Spotify Web API functions are only available to Premium subscribers. Check the [API documentation](https://developer.spotify.com/documentation/web-api) for details!

## Installation Guide

### Step 1: Set Up Your Spotify Account
1. Sign up for Spotify at https://accounts.spotify.com/en/login
2. Create a Developer Account at https://developer.spotify.com/
3. Accept the developer terms of service

### Step 2: Create Your Spotify App
1. Go to https://developer.spotify.com/dashboard
2. Click "Create App" and enter:
   - App Name: My App
   - App Description: This is my first Spotify app
   - Redirect URI: "https://open.spotify.com"
   - Select "Web API" in Permissions
3. Accept the Developer Terms of Service and create the app

### Step 3: Configure the Plugin
Create a `config.json` file with your app credentials:
```json
{
    "client_id": "<Your Client ID>",
    "client_secret": "<Your Client Secret>",
    "username": "<Your Spotify Username>"
}
```

### Step 4: Set Up Python Environment
Run our setup script to create a virtual environment and install dependencies:
```bash
setup.bat
```

### Step 5: Build the Plugin
```bash
build.bat
```
This will create a `dist\spotify` folder containing all the required files for the plugin.

### Step 6: Install the Plugin
1. Copy the entire `dist\spotify` folder to:
   ```
   %PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\
   ```

💡 **Tip**: Make sure all G-Assist clients are closed when copying files!

## How to Use
Once installed, you can control Spotify through G-Assist. Try these commands:

### Play Music
- Start Playback: `Hey Spotify, play my music!`
- Play a song: `Hey Spotify, play Life Itself by Glass Animals`
- Play an album: `Hey Spotify, play reputation by Taylor Swift`
- Play a playlist: `Hey Spotify play my Gametime Music playlist`

### Playback
- Pause playback: `Hey Spotify, pause it`
- Skip track: `Hey Spotify, go to the next song`
- Skip to previous track: `Hey Spotify, go to the previous song`
- Toggle shuffle: `Hey Spotify, turn shuffle [on/off]`
- Volume control: `Hey Spotify, set the volume to 30`
- Queue a track: `Hey Spotify, add Heat Waves by Glass Animals to the queue`

### Reading Spotify Info
- Get current playback: `Hey Spotify, what song is playing?`
- Get top playlists: `Hey Spotify, what are my top 5 playlists`

### Authentication Flow
The plugin uses OAuth 2.0 for authentication with Spotify. Here's how it works:

1. **First-time Setup**
   - Run any Spotify command (e.g., `Hey Spotify, what are my top playlists?`)
   - A browser window will open automatically
   - Log in to Spotify and authorize the app
   - You'll be redirected to a URL - copy the ENTIRE URL from your browser
   - Create or edit the file at `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\auth.json`
   - Add the URL in this format:
     ```json
     {
       "auth_url": "YOUR_COPIED_URL"
     }
     ```
   - Save the file
   - The plugin will automatically:
     - Process the authorization URL
     - Save your access and refresh tokens

2. **Subsequent Uses**
   - The plugin automatically uses your saved tokens
   - If tokens expire, they are automatically refreshed
   - No manual intervention needed after initial setup

3. **Troubleshooting Authentication**
   - If you see authentication errors, try deleting the `auth.json` file
   - The plugin will prompt you to re-authenticate on next use
   - Check the log file at `%USERPROFILE%\spotify-plugin.log` for detailed error messages

💡 **Tip**: The plugin automatically handles token refresh and command retry, so you only need to authenticate once!

## Available Functions
The plugin includes these main functions:
- `spotify_start_playback`: Start playing music
- `spotify_pause_playback`: Pause the current track
- `spotify_next_track`: Skip to next track
- `spotify_previous_track`: Go to previous track
- `spotify_shuffle_playback`: Toggle shuffle mode
- `spotify_set_volume`: Adjust volume
- `spotify_get_currently_playing`: Get current track info
- `spotify_queue_track`: Add a track to queue
- `spotify_get_user_playlists`: List your playlists

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\spotify-plugin.log
```
Check this file for detailed error messages and debugging information.

## Troubleshooting Tips
- **Plugin not working?** Verify all files are copied to the plugins folder and restart G-Assist
- **Can't authenticate?** Double-check your client ID and secret in config.json, delete auth.json

## Developer Documentation

### Architecture Overview
The Spotify plugin is implemented as a Python-based service that communicates with Spotify's Web API to handle interactions for music playback control, playlist management, and user information retrieval.

### Core Components

### Core Components

#### Command Handling
- `read_command()`: Reads JSON-formatted commands from G-Assist's input pipe
  - Uses Windows API to read from STDIN
  - Returns parsed JSON command or None if invalid
  - Handles chunked input for large messages

- `write_response()`: Sends JSON-formatted responses back to G-Assist
  - Uses Windows API to write to STDOUT
  - Appends `<<END>>` marker to indicate message completion
  - Response format: `{"success": bool, "message": Optional[str]}`

### Configuration

#### API Credentials
- Stored in `config.json`
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\config.json`
- Required fields:
  ```json
  {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret",
    "username": "your_spotify_username"
  }
  ```

#### Available Commands

##### Playback Control
- `execute_play_command()`: Start/resume playback
  - Supports tracks, albums, playlists
  - Handles device selection
  - Parameters: type, name, artist
- `execute_pause_command()`: Pause playback
- `execute_next_track_command()`: Skip to next track
- `execute_previous_track_command()`: Go to previous track
- `execute_shuffle_command()`: Toggle shuffle mode
- `execute_volume_command()`: Adjust volume (0-100)

##### Information Retrieval
- `execute_currently_playing_command()`: Get current track info
- `execute_get_user_playlists_command()`: List user playlists
- `get_device()`: Get active playback device (helper function)

##### Search Functions
- `get_track_uri()`: Search for tracks (helper function)
- `get_album_uri()`: Search for albums (helper function)
- `get_playlist_uri()`: Search for playlists (helper function)
- `get_generic_uri()`: Generic search with artist support (helper function)

#### Key Functions

##### Main Entry Point (`main()`)
- Initializes the plugin and enters command processing loop
- Handles command routing and response generation
- Manages authentication state
- Supports commands: `initialize`, `shutdown`, `authorize`, and various Spotify control commands

##### Authentication Flow
1. `execute_initialize_command()`: Initiates OAuth flow
2. `authorize_user()`: Opens browser for user login
3. `complete_auth_user()`: Handles OAuth callback and token management
4. Token storage in `auth.json`

##### Spotify API Integration
- `call_spotify_api()`: Core function for making authenticated API calls
- Handles GET, POST, and PUT requests
- Manages authentication headers and error handling
- Base URL: `https://api.spotify.com/v1`

#### Authentication State
- Stored in `auth.json`
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\auth.json`
- Contains OAuth state and tokens

### Logging
- Log file: `%USERPROFILE%\spotify-plugin.log`
- Log level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Comprehensive logging for debugging and error tracking

### Error Handling
- API error responses are captured and logged
- User-friendly error messages
- Fallback mechanisms for common issues
- Detailed error logging with stack traces

### Adding New Features
To add new features:
1. Add new command to `generate_command_handlers()`
2. Implement corresponding execute function
3. Add proper error handling and logging
4. Update the manifest.json with new function definition:
   ```json
   {
      "name": "new_command",
      "description": "Description of what the command does",
      "tags": ["relevant", "tags"],
      "properties": {
         "parameter_name": {
            "type": "string",
            "description": "Description of the parameter"
         }
      }
   }
   ```
5. Test the feature:
   - First, run the script:
      ``` bash
      python plugin.py
      ```
   - Test initialization and authentication

   - Run the new command:
      ``` json
      {
         "tool_calls" : "new_command", 
         "params": {
            "parameter_name": "parameter_value"
         }
      }
      ```   
   - Verify error handling
   - Check logging output
6. Run the setup & build scripts as outlined above, install the plugin by placing the files in the proper location and test your updated plugin. Use variations of standard user messages to make sure the function is adequately documented in the `manifest.json`


## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.