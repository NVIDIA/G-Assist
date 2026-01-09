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
   - App Name: G-Assist Spotify Plugin
   - App Description: Spotify integration for G-Assist
   - Redirect URI: `http://127.0.0.1:8888/callback`
   - Select "Web API" in Permissions
3. Accept the Developer Terms of Service and create the app

⚠️ **IMPORTANT - Redirect URI Must Match Exactly!**

The Redirect URI **MUST** be exactly: `http://127.0.0.1:8888/callback`

| ❌ Won't Work | ✅ Use This |
|--------------|-------------|
| `http://localhost:8888/callback` | `http://127.0.0.1:8888/callback` |
| `https://127.0.0.1:8888/callback` | `http://127.0.0.1:8888/callback` |
| `http://127.0.0.1:8888/callback/` | `http://127.0.0.1:8888/callback` |

Spotify requires an **exact string match**. Using `localhost` instead of `127.0.0.1` will cause an "INVALID_CLIENT: Invalid redirect URI" error.

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
- Play an artist: `Hey Spotify, play Taylor Swift`

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
The plugin uses **fully automated OAuth 2.0** authentication. No manual steps required!

1. **First-time Setup**
   - Run any Spotify command (e.g., `Hey Spotify, what are my top playlists?`)
   - A browser window will open automatically
   - Log in to Spotify and authorize the app
   - **That's it!** The plugin automatically:
     - Catches the OAuth callback on 127.0.0.1:8888
     - Exchanges the code for access/refresh tokens
     - Saves tokens to `auth.json`
     - Retries your original command
   
   💡 **No URL copying needed!** The plugin handles everything automatically.

2. **Subsequent Uses**
   - The plugin automatically uses your saved tokens
   - If tokens expire, they are automatically refreshed
   - No manual intervention needed

3. **Troubleshooting Authentication**
   - If you see authentication errors, delete `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\auth.json`
   - The plugin will re-authenticate automatically on next use
   - Check the log file at `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\spotify-plugin.log` for detailed error messages
   - Make sure port 8888 is not blocked by firewall

💡 **Tip**: The entire OAuth flow is automated - just authorize once in the browser and you're done!

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
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\spotify-plugin.log
```
Check this file for detailed error messages and debugging information.

## Troubleshooting Tips
- **Plugin not working?** Verify all files are copied to the plugins folder and restart G-Assist
- **Can't authenticate?** Double-check your client ID and secret in config.json, delete auth.json
- **"INVALID_CLIENT: Invalid redirect URI" error?** Your Spotify app's redirect URI doesn't match exactly. Make sure it's `http://127.0.0.1:8888/callback` (not `localhost`, not `https`, no trailing slash)

## Developer Documentation

### Architecture Overview
The Spotify plugin is built using the G-Assist SDK (`gassist_sdk`) and communicates with Spotify's Web API for music playback control and user information retrieval.

### Core Components

#### Plugin Setup
The plugin uses the SDK's decorator-based command registration:
```python
from gassist_sdk import Plugin

plugin = Plugin(name="spotify", version="2.0.0", description="Control Spotify playback")

@plugin.command("spotify_start_playback")
def spotify_start_playback(name: str = "", type: str = "track", artist: str = ""):
    # Implementation
    pass
```

### Configuration

#### API Credentials
- Stored in `config.json`
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\config.json`
- Required fields:
  ```json
  {
    "client_id": "your_client_id",
    "client_secret": "your_client_secret"
  }
  ```

#### Available Commands

##### Playback Control
- `spotify_start_playback()`: Start/resume playback
  - Supports tracks, albums, and artists
  - Handles device selection and search
  - Parameters: type, name, artist
- `spotify_pause_playback()`: Pause playback
- `spotify_next_track()`: Skip to next track
- `spotify_previous_track()`: Go to previous track
- `spotify_shuffle_playback()`: Toggle shuffle mode
- `spotify_set_volume()`: Adjust volume (0-100)
- `spotify_queue_track()`: Add track to queue

##### Information Retrieval
- `spotify_get_currently_playing()`: Get current track info
- `spotify_get_user_playlists()`: List user playlists

##### Helper Functions
- `spotify_api()`: Core function for making authenticated API calls
- `get_device_id()`: Get active playback device
- `do_oauth_flow()`: Perform OAuth 2.0 authorization
- `refresh_token()`: Refresh expired access tokens

#### Authentication Flow
1. First command triggers setup wizard if not configured
2. `do_oauth_flow()`: Opens browser, starts local callback server
3. User authorizes in browser, callback receives auth code
4. Code exchanged for access/refresh tokens
5. Tokens saved to `auth.json` for future use
6. Automatic token refresh on 401 errors

#### Authentication State
- Stored in `auth.json`
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\auth.json`
- Contains access_token and refresh_token

### Logging
- Log file: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\spotify\spotify-plugin.log`
- Log level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Error Handling
- API errors are logged with status codes and response bodies
- User-friendly error messages returned to G-Assist
- Automatic re-authentication on 401 errors
- Premium-required (403) errors handled gracefully

### Adding New Features
1. Create a new function with the `@plugin.command()` decorator
2. Add proper error handling and logging
3. Update `manifest.json` with the new function definition:
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
4. Test locally by running `python plugin.py`
5. Build and install the updated plugin


## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.