# 📺 Twitch Status Plugin for NVIDIA G-Assist 🎮

Transform your G-Assist experience with real-time Twitch stream status checking! This plugin lets you monitor your favorite Twitch streamers directly through the G-Assist platform. Whether you want to know if your favorite streamer is live or get details about their current stream, checking Twitch status has never been easier.

## ✨ What Can It Do?
- 🎮 Check if any Twitch streamer is currently live
- 📊 Get detailed stream information including:
  - 🎥 Stream title
  - 🎯 Game being played
  - 👥 Current viewer count
  - ⏰ Stream start time
- 🔐 Automatic OAuth token management
- 📝 Detailed logging for troubleshooting

## 📋 Before You Start
Make sure you have:
- 💻 Windows PC
- 🐍 Python 3.6 or higher installed
- 🔑 Twitch Developer Application credentials
- 🚀 NVIDIA G-Assist installed

💡 **Tip**: Don't have Twitch Developer credentials yet? Visit the [Twitch Developer Console](https://dev.twitch.tv/console) to create them!

## 🛠️ Installation Guide

### 📥 Step 1: Get the Files
```bash
git clone <repo link>
cd twitch
```
This downloads all the necessary files to your computer.

### ⚙️ Step 2: Setup and Build
1. Run the setup script:
```bash
setup.bat
```
This installs all required Python packages.

2. Run the build script:
```bash
build.bat
```
This creates the executable and prepares all necessary files.

### 📦 Step 3: Install the Plugin
1. Navigate to the `dist` folder created by the build script
2. Copy the `twitch` folder to:
```bash
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\twitch
```
💡 **Tip**: Copy and paste this path into File Explorer's address bar for easy navigation!

💡 **Tip**: Make sure all files are copied, including:
- The executable
- manifest.json
- config.json (you'll need to update this with your Twitch credentials)

### 🔐 Step 4: Configure Your Twitch Credentials
1. Open `config.json` in the plugin directory
2. Add your Twitch Developer credentials:
```json
{
    "TWITCH_CLIENT_ID": "your_client_id_here",
    "TWITCH_CLIENT_SECRET": "your_client_secret_here"
}
```

## 💬 How to Use
Once everything is set up, you can check Twitch stream status through simple chat commands! Just talk to your assistant using natural language.

Try these commands:
- 🗣️ "Hey Twitch, is Ninja live?"
- 🎯 "Check if shroud is streaming"
- 🎮 "Is pokimane online right now?"

### 📝 Example Responses

When a streamer is live:
```text
ninja is LIVE!
Title: Friday Fortnite!
Game: Fortnite
Viewers: 45,231
Started At: 2024-03-14T12:34:56Z
```

When a streamer is offline:
```
ninja is OFFLINE
```

## ❓ Troubleshooting Tips

### 🔑 Authentication Issues
- **Getting "Failed to authenticate" errors?**
  - ✅ Verify your Client ID and Secret in config.json
  - ✅ Check if your Twitch Developer Application is still active
  - ✅ Make sure config.json is in the correct location

### 📡 Connection Issues
- **Plugin not responding?**
  - ✅ Check if Python is installed correctly
  - ✅ Verify your internet connection
  - ✅ Make sure the Twitch API is accessible

### 📝 Logging
The plugin logs all activity to:
```
%USERPROFILE%\twitch.log
```
Check this file for detailed error messages and debugging information.

## 🆘 Need Help?
If you run into issues:
1. 📋 Check the log file for specific error messages
2. 🔑 Verify your Twitch Developer credentials are valid
3. 📂 Make sure all files are in the correct locations
4. 🔄 Try restarting the G-Assist platform

## 👥 Contributing
This is an internal NVIDIA project. Please follow NVIDIA's internal contribution guidelines.

## 📄 License
Apache License 2.0 - All rights reserved.

## 🙏 Acknowledgments
- 🎮 Built on the [Twitch API](https://dev.twitch.tv/docs/api/)
- 🚀 Part of the NVIDIA G-Assist platform