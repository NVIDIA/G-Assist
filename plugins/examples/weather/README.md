# Weather Plugin for NVIDIA G-Assist

Stay informed about weather conditions anywhere in the world with this powerful G-Assist plugin! Get instant access to current weather data, temperature readings, and atmospheric conditions for any city you're interested in. Perfect for planning your day, checking conditions before travel, or simply satisfying your weather curiosity.

## What Can It Do?
- Get current weather conditions for any city worldwide
- Real-time weather data including:
  - Temperature (Celsius)
  - Humidity percentage
  - Wind speed (km/h)
  - Weather conditions (clear, cloudy, rain, snow, etc.)
- **No API key required** — uses the free Open-Meteo API
- Automatic city geocoding (just type the city name)
- Detailed logging for troubleshooting

## Before You Start
Make sure you have:
- Windows PC
- Python 3.8 or higher installed
- NVIDIA G-Assist installed

> **Note:** This plugin uses the [Open-Meteo API](https://open-meteo.com/) which is free and requires no API key!

## Quickstart

### Step 1: Setup
From the `plugins/examples` directory, run:
```bash
setup.bat weather
```
This installs dependencies to the `libs/` folder and copies the G-Assist SDK.

### Step 2: Deploy
```bash
setup.bat weather -deploy
```
This copies the plugin files to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\weather
```

💡 **Tip**: Make sure G-Assist is closed when deploying!

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
London, GB: Partly cloudy, 15.0C, 10 km/h wind, Humidity 65%
```

```text
Santa Clara, US: Clear sky, 22.5C, 8 km/h wind, Humidity 45%
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Could not find coordinates" | Try using just the city name (e.g., "London" instead of "London, UK") |
| Request timed out | Check your internet connection and try again |
| Plugin not loading | Verify files are deployed and restart G-Assist |
| Wrong city returned | Be more specific with the city name or add country |

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\weather\weather.log
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
    "description": "Get weather information for a given city.",
    "executable": "plugin.py",
    "persistent": false,
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "get_weather_info",
            "description": "Fetches weather information for a given city.",
            "tags": ["weather", "forecast"],
            "properties": {
                "city": {
                    "type": "string",
                    "description": "The name of the city to get the weather for."
                }
            }
        }
    ]
}
```

### Plugin Code (`plugin.py`)

The SDK handles all protocol communication automatically. The plugin uses Open-Meteo's geocoding API to resolve city names to coordinates, then fetches weather data:

```python
from gassist_sdk import Plugin

PLUGIN_NAME = "weather"

plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Weather information via Open-Meteo (no API key required)"
)

@plugin.command("get_weather_info")
def get_weather_info(city: str = ""):
    """Get current weather for a city."""
    if not city:
        return "City parameter is required."
    
    plugin.stream(f"Checking weather for {city}...")
    
    # Step 1: Geocode the city using Open-Meteo
    geo_resp = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 5, "language": "en", "format": "json"},
        timeout=10
    )
    results = geo_resp.json().get("results", [])
    if not results:
        return f"Could not find coordinates for '{city}'."
    
    lat, lon = results[0]["latitude"], results[0]["longitude"]
    location = f"{results[0]['name']}, {results[0].get('country_code', '')}"
    
    # Step 2: Get weather data
    weather_resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={"latitude": lat, "longitude": lon, "current_weather": True},
        timeout=10
    )
    current = weather_resp.json().get("current_weather", {})
    
    temp = current.get("temperature", "N/A")
    wind = current.get("windspeed", "N/A")
    code = current.get("weathercode", 0)
    condition = describe_weather_code(code)  # Maps code to description
    
    return f"{location}: {condition}, {temp}C, {wind} km/h wind"

if __name__ == "__main__":
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

The plugin integrates with the **Open-Meteo API** (free, no API key required):

| Endpoint | Purpose |
|----------|---------|
| `https://geocoding-api.open-meteo.com/v1/search` | Convert city names to coordinates |
| `https://api.open-meteo.com/v1/forecast` | Get weather data for coordinates |

**Data extracted:**
- Temperature (°C)
- Weather condition (from weather code)
- Wind speed (km/h)
- Humidity (%)

**Weather codes** are mapped to human-readable descriptions (e.g., code 0 = "Clear sky", code 61 = "Slight rain").

### Logging

- Log file: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\weather\weather.log`
- Log level: INFO
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
       }
   }
   ```

### Testing

1. **Local test** - Run directly to check for syntax errors:
   ```bash
   python plugin.py
   ```

2. **Deploy** - From `plugins/examples` directory:
   ```bash
   setup.bat weather -deploy
   ```

3. **Plugin emulator** - Test commands without G-Assist:
   ```bash
   python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
   ```
   Then select the weather plugin and test commands interactively.

4. **G-Assist test** - Open G-Assist and try: "What's the weather in London?"


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
- Built using the [Open-Meteo API](https://open-meteo.com/) — free weather data, no API key required
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
