# Weather Plugin for NVIDIA G-Assist

Stay informed about weather conditions anywhere in the world with this powerful G-Assist plugin! Get instant access to current weather data, temperature readings, and atmospheric conditions for any city you're interested in. Perfect for planning your day, checking conditions before travel, or simply satisfying your weather curiosity.

## What Can It Do?
-  Get current weather conditions for any city
-  Real-time weather data including:
    -  Temperature
    -  Humidity
    -  Wind conditions
    -  Cloud coverage
-  Detailed logging for troubleshooting

##  Before You Start
Make sure you have:
-  Windows PC
-  Python 3.6 or higher installed
-  NVIDIA G-Assist installed

##  Quickstart

###  Step 1: Get the Files
```bash
git clone <repo link>
```
This downloads all the necessary files to your computer.

### Step 2: Setup
From the `examples/` folder, run:
```bash
setup.bat weather
```
This installs all required Python packages and copies the SDK to `libs/`.

### Step 3: Install the Plugin
Copy the entire `weather` folder to:
```bash
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins
```

💡 **Tip**: Python plugins run directly—no build step required! Make sure all files are copied, including:
- `plugin.py` (main plugin script)
- `manifest.json`
- `libs/` folder (contains the G-Assist SDK)

## How to Use
Once everything is set up, you can check weather information through simple chat commands.

Try these commands:
- "Hey weather, what's the weather like in London?"
- "Check the temperature in New York"
- "What's the forecast for Tokyo?"
- "How's the weather in Santa Clara?"

### Example Responses

When checking weather:
```text
Partly cloudy, 15 degrees Celsius, Humidity: 65%
```

## Troubleshooting Tips

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\weather\weather-plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Architecture Overview

The Weather plugin is built using the **G-Assist SDK (Protocol V2)**, which handles all communication with G-Assist via JSON-RPC 2.0. The SDK abstracts away the protocol details so you can focus on business logic.

### Project Structure

```
weather/
├── plugin.py           # Main plugin code using gassist_sdk
├── manifest.json       # Plugin configuration (protocol_version: "2.0")
├── requirements.txt    # Python dependencies
├── libs/               # SDK folder (auto-added to PYTHONPATH)
│   └── gassist_sdk/    # G-Assist Plugin SDK
└── README.md
```

### Manifest File (`manifest.json`)

```json
{
    "manifestVersion": 1,
    "name": "weather",
    "version": "2.0.0",
    "description": "Get weather information for any city",
    "executable": "plugin.py",
    "persistent": false,
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "get_weather_info",
            "description": "Fetches weather information for a given city.",
            "tags": ["weather", "forecast", "temperature"],
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The name of the city to get the weather for."
                }
            },
            "required": ["city"]
        }
    ]
}
```

### Plugin Code (`plugin.py`)

The SDK handles all protocol communication automatically:

```python
import os
import sys
import logging
import requests

# SDK import (from libs/ folder)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

from gassist_sdk import Plugin, Context

# Configuration
PLUGIN_NAME = "weather"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create plugin instance
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Get weather information for any city"
)

@plugin.command("get_weather_info")
def get_weather_info(city: str, context: Context = None):
    """
    Get current weather information for a city.
    
    Args:
        city: The name of the city to get weather for
        context: Conversation context (provided by engine)
    
    Returns:
        Weather information string
    """
    logger.info(f"Getting weather for: {city}")
    
    try:
        response = requests.get(
            f"https://wttr.in/{city}?format=j1",
            timeout=10
        )
        response.raise_for_status()
        
        data = response.json()
        current = data.get("current_condition", [{}])[0]
        
        condition = current.get("weatherDesc", [{}])[0].get("value", "Unknown")
        temp_c = current.get("temp_C", "N/A")
        humidity = current.get("humidity", "N/A")
        
        return f"{condition}, {temp_c} degrees Celsius, Humidity: {humidity}%"
        
    except requests.exceptions.Timeout:
        logger.error(f"Timeout getting weather for {city}")
        return f"**Error:** Weather service timed out for {city}"
    except Exception as e:
        logger.error(f"Error getting weather: {e}")
        return f"**Error:** Could not get weather for {city}"

if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin...")
    plugin.run()
```

### Key SDK Features Used

| Feature | Description |
|---------|-------------|
| `@plugin.command()` | Decorator to register command handlers |
| `plugin.run()` | Starts the plugin main loop (handles all protocol communication) |
| `plugin.stream()` | Send streaming output during long operations |

### Protocol V2 Benefits

The SDK handles all protocol details automatically:
- ✅ JSON-RPC 2.0 with length-prefixed framing
- ✅ Automatic ping/pong responses (no heartbeat code needed!)
- ✅ Error handling and graceful shutdown
- ✅ No need to implement pipe communication manually

### Weather Service Integration

The plugin integrates with wttr.in service:
- Base URL: `https://wttr.in/{city}?format=j1`
- Response format: JSON with current conditions
- Data extraction: Temperature (°C), Weather condition, Humidity (%)
- Timeout: 10 seconds for requests

### Logging

- Log file location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\weather\weather-plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Adding New Commands

1. Add a new function with the `@plugin.command()` decorator:
   ```python
   @plugin.command("get_forecast")
   def get_forecast(city: str, days: int = 3, context: Context = None):
       """Get weather forecast for a city."""
       # Your implementation
       return "Forecast here"
   ```

2. Add the function to `manifest.json`:
   ```json
   {
       "name": "get_forecast",
       "description": "Get weather forecast for a city",
       "tags": ["weather", "forecast"],
       "properties": {
           "city": {
               "type": "string",
               "description": "The name of the city"
           },
           "days": {
               "type": "integer",
               "description": "Number of days to forecast (default: 3)"
           }
       },
       "required": ["city"]
   }
   ```

3. Test locally by running `python plugin.py` and using the plugin emulator

4. Deploy by copying the folder to the plugins directory


## Next Steps
- **Ideas for Feature Enhancements**
  - Add weather forecasts
  - Implement weather alerts
  - Add historical weather data

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
-  Built using the [wttr.in API](https://wttr.in/)
-  We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
