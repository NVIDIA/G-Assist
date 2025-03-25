# G-Assist Spotify Plugin

Transform your music experience with G-Assist! This plugin lets you control Spotify using simple voice commands or the G-Assist interface. Whether you want to play your favorite tracks, manage playlists, or control playback, managing your Spotify has never been easier.

## ✨ What Can It Do?
- 🎵 Control Spotify playback (play, pause, next, previous)
- 🔀 Toggle shuffle mode
- 🔊 Adjust volume levels
- 📑 Access and manage your playlists
- 🎮 Seamlessly integrates with your G-Assist setup
- 🔧 Easy to set up and configure

## 📋 Before You Start
Make sure you have:
- Windows PC
- Python 3.x installed on your computer
- Spotify Account (Free or Premium)
- Spotify Developer Account
- G-Assist installed on your system

💡 **Tip**: Some Spotify Web API functions are only available to Premium subscribers. Check the [API documentation](https://developer.spotify.com/documentation/web-api) for details!

## 🚀 Installation Guide

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
💡 **Tip**: The script will display "Setup complete" when successful!

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

## 🎮 Available Functions
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

## 🔍 Troubleshooting Tips
- **Build failed?** Make sure Python is in your system PATH
- **Plugin not working?** Verify all files are copied to the plugins folder
- **Can't authenticate?** Double-check your client ID and secret in config.json

## 🆘 Need Help?
If you run into issues:
1. Verify your Spotify credentials are correct
2. Check that G-Assist is running
3. Ensure your `config.json` is properly formatted
4. Try restarting G-Assist

## 🙏 Acknowledgments
- 🎮 Built using the [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- 🚀 Part of the NVIDIA G-Assist platform