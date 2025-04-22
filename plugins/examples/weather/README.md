# 🌤️ Weather Plugin for NVIDIA G-Assist

Stay informed about weather conditions anywhere in the world with this powerful G-Assist plugin! Get instant access to current weather data, temperature readings, and atmospheric conditions for any city you're interested in. Perfect for planning your day, checking conditions before travel, or simply satisfying your weather curiosity.

## ✨ What Can It Do?
- 🌡️ Get current weather conditions for any city
- 🌤️ Real-time weather data including:
  - 🌡️ Temperature
  - 💧 Humidity
  - 🌪️ Wind conditions
  - ☁️ Cloud coverage
- 📝 Detailed logging for troubleshooting

## 📋 Before You Start
Make sure you have:
- 💻 Windows PC
- 🐍 Python 3.6 or higher installed
- 🚀 NVIDIA G-Assist installed

## 🛠️ Quickstart

### 📥 Step 1: Get the Files
```bash
git clone <repo link>
cd weather
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
2. Copy the `weather` folder to:
```bash
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\weather
```
💡 **Tip**: Copy and paste this path into File Explorer's address bar for easy navigation!

💡 **Tip**: Make sure all files are copied, including:
- The executable
- manifest.json
- config.json

## 💬 How to Use
Once everything is set up, you can check weather information through simple chat commands! Just talk to your assistant using natural language.

Try these commands:
- 🗣️ "Hey, what's the weather like in London?"
- 🌡️ "Check the temperature in New York"
- 🌤️ "What's the forecast for Tokyo?"

### 📝 Example Responses

When checking weather:
```text
Current weather in London: Partly cloudy, 15°C, Humidity: 65%, Wind: 10 km/h
```

## ❓ Troubleshooting Tips

### 🌐 API Issues
- **Getting "Failed to fetch weather data" errors?**
  - ✅ Check if the city name is correct
  - ✅ Verify your internet connection
  - ✅ Make sure the weather service is accessible

### 📡 Connection Issues
- **Plugin not responding?**
  - ✅ Check if Python is installed correctly
  - ✅ Verify your internet connection
  - ✅ Make sure the weather service is accessible

### 📝 Logging
The plugin logs all activity to:
```
%USERPROFILE%\weather_plugin.log
```
Check this file for detailed error messages and debugging information.

## 🚀 Next Steps
- **Feature Enhancements**
  - Add weather forecasts
  - Implement weather alerts
  - Add historical weather data
  - Create favorite locations feature

- **Documentation**
  - Add usage examples
  - Write troubleshooting guide
  - Document common issues and solutions

## 🆘 Need Help?
If you run into issues:
1. 📋 Check the log file for specific error messages
2. 🌐 Verify your internet connection
3. 📂 Make sure all files are in the correct locations
4. 🔄 Try restarting the G-Assist platform

## 👥 Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## 📄 License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments
- 🌤️ Built using the [wttr.in API](https://wttr.in/)
- 🚀 Part of the NVIDIA G-Assist platform
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
