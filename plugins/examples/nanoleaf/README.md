# Nanoleaf Illumination Plugin for G-Assist

Transform your Nanoleaf LED panels into an interactive lighting experience with G-Assist! This plugin lets you control your Nanoleaf lights using simple voice commands or the G-Assist interface. Whether you want to set the mood for a movie night or brighten up your workspace, controlling your Nanoleaf panels has never been easier.

## ✨ What Can It Do?
- 🎨 Change your Nanoleaf panel colors with voice or text commands
- 🗣️ Use natural language: speak or type your commands
- 🔌 Works with any Nanoleaf device that supports the [Nanoleaf API](https://nanoleafapi.readthedocs.io/en/latest/index.html)
- 🎮 Seamlessly integrates with your G-Assist setup
- 🔧 Easy to set up and configure

## 📋 Before You Start
Make sure you have:
- Windows PC
- Python 3.x installed on your computer
- Your Nanoleaf device set up and connected to your 2.4GHz WiFi network
- G-Assist installed on your system
- Your Nanoleaf device's IP address 

💡 **Tip**: Nanoleaf devices only work on 2.4GHz networks, not 5GHz. Make sure your device is connected to the correct network band!

💡 **Tip**: Not sure about your Nanoleaf's IP address? You can find it in your router's admin page under connected devices

## 🚀 Installation Guide

### Step 1: Get the Files
```bash
git clone <repo link>
cd nanoleaf
```
This downloads all the necessary files to your computer.

### Step 2: Set Up Python Packages
```bash
python -m pip install -r requirements.txt
```
This installs all the required software that makes the plugin work.

### Step 3: Configure Your Device
1. Find the `config.json` file in the folder
2. Open it with any text editor (like Notepad)
3. Replace the IP address with your Nanoleaf's IP address:
```json
{
  "ip": "192.168.1.100"  # Replace with your Nanoleaf's IP address
}
```

### Step 4: Build It
The easiest way is to use our build script:
```bash
build.bat
```

If that doesn't work, you can try the manual way:
```bash
pyinstaller --onedir --name g-assist-plugin-nanoleaf nanoleaf.py
copy manifest.json dist\g-assist-plugin-nanoleaf\manifest.json
copy config.json dist\g-assist-plugin-nanoleaf\config.json
```

### Step 5: Install the Plugin
1. Create a new folder here (if it doesn't exist):
   ```
   %programdata%\NVIDIA Corporation\nvtopps\rise\plugins\nanoleaf
   ```
   💡 **Tip**: You can copy this path and paste it into File Explorer's address bar!

2. Copy these three files from the `dist\g-assist-plugin-nanoleaf` folder to the folder you just created:
   - `g-assist-plugin-nanoleaf.exe`
   - `manifest.json`
   - `config.json`

## 🎮 How to Use
Once everything is set up, you can control your Nanoleaf panels through G-Assist! Try these commands (either by voice or text):
- "Change my room lights to blue"
- "Hey nanoleaf, set my lights to rainbow"
- "/nanoleaf set my lights to red"

💡 **Tip**: You can use either voice commands or type your requests directly into G-Assist - whatever works best for you!

## 🔍 Troubleshooting Tips
- **Can't find your Nanoleaf's IP?** Make sure your Nanoleaf is connected to your 2.4GHz WiFi network (5GHz networks are not supported)
- **Commands not working?** Double-check that all three files were copied to the plugins folder
- **Build script failed?** Make sure Python is added to your system's PATH

## 👥 Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## 📄 License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

## 🆘 Need Help?
If you run into any issues, check the troubleshooting section above. You can also:
1. Make sure your Nanoleaf device is powered on and connected to your network
2. Verify that G-Assist is running
3. Try restarting both your Nanoleaf device and G-Assist