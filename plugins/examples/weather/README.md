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

###  Step 2: Setup and Build
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

###  Step 3: Install the Plugin
1. Navigate to the `dist` folder created by the build script
2. Copy the `weather` folder to:
```bash
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins
```

💡 **Tip**: Make sure all files are copied, including:
- The executable
- manifest.json

## How to Use
Once everything is set up, you can check weather information through simple chat commands.

Try these commands:
-  "Hey weather, what's the weather like in London?"
-  "/weather Check the temperature in New York"
-  "/weather What's the forecast for Tokyo?"

### Example Responses

When checking weather:
```text
Partly cloudy, 15 degrees Celsius, Humidity: 65%
```

## Troubleshooting Tips

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\weather_plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Plugin Architecture
The weather plugin is built as a Python-based G-Assist plugin that communicates with the wttr.in weather service. The plugin follows a command-based architecture where it continuously listens for commands from G-Assist and processes weather requests through standard input/output pipes.

### Core Components

#### Command Handling
- `read_command()`: Reads JSON-formatted commands from G-Assist's input pipe
  - Uses Windows API to read from STDIN
  - Returns parsed JSON command or None if invalid
  - Handles chunked input for large messages
  - Buffer size: 4096 bytes

- `write_response()`: Sends JSON-formatted responses back to G-Assist
  - Uses Windows API to write to STDOUT
  - Appends `<<END>>` marker to indicate message completion
  - Response format: `{"success": bool, "message": Optional[str]}`

#### Weather Service Integration
The plugin integrates with wttr.in service:
- Base URL: `https://wttr.in/{city}?format=j1`
- Response format: JSON with current conditions
- Data extraction:
  - Temperature (°C)
  - Weather condition
  - Humidity (%)
- Timeout: 10 seconds for requests

### Available Commands

#### `initialize`
Initializes the plugin and sets up the environment.
- No parameters required
- Returns: `{"success": true, "message": "Plugin initialized"}`

#### `shutdown`
Gracefully terminates the plugin.
- No parameters required
- Returns: `{"success": true, "message": "Plugin shutdown"}`

#### `get_weather_info`
Retrieves weather information for a specified city.
- Parameters:
  ```json
  {
    "city": "string"  // Required: Name of the city
  }
  ```
- Returns:
  ```json
  {
    "success": true,
    "message": "Partly cloudy, 15 degrees Celsius, Humidity: 65%"
  }
  ```

### Command Processing
The plugin processes commands through a JSON-based protocol:

1. Input Format:
```json
{
    "tool_calls": [
        {
            "func": "command_name",
            "params": {
                "city": "London"
            }
        }
    ]
}
```

2. Output Format:
```json
{
    "success": true|false,
    "message": "Response message or error description"
}
```

### Error Handling
- All operations are wrapped in try-except blocks
- Specific error handling for:
  - Missing city parameter
  - Request timeouts
  - HTTP request errors
  - JSON parsing errors
  - Unexpected exceptions
- All errors are logged with detailed information
- Failed operations return a failure response with descriptive message

### Logging
- Log file location: `%USERPROFILE%\weather-plugin.log`
- Logging level: INFO
- Format: `%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s`
- Logged events:
  - Command reception
  - Function calls
  - Parameter validation
  - API requests
  - Error conditions
  - Response generation

### Dependencies
- Python 3.6+
- Required Python packages:
  - requests: For HTTP requests to wttr.in
  - Standard library modules:
    - json: For message serialization/deserialization
    - logging: For operation logging
    - os: For file path operations
    - ctypes: For Windows API interaction

### Adding New Commands
To add a new command:
1. Implement command function with signature: `def new_command(params: dict = None) -> dict`
2. Add command to `commands` dictionary in `main()`
3. Implement proper error handling and logging
4. Return standardized response format
5. Add the function to the `functions` list in `manifest.json`:
   ```json
   {
       "name": "new_command",
       "description": "Description of what the command does",
       "parameters": {
           "parameter_name": {
               "type": "string",
               "description": "Description of the parameter"
           }
       }
   }
   ```
6. Manually test the function:

   First, run the script:
   ``` bash
   python plugin.py
   ```

   Run the initialize command: 
      ``` json
      {
         "tool_calls" : "initialize"
      }
      ```
   Run the new command:
      ``` json
      {
         "tool_calls" : "new_command", 
         "params": {
            "parameter_name": "parameter_value"
         }
      }
      ```
7. Run the setup & build scripts as outlined above, install the plugin by placing the files in the proper location and test your updated plugin. Use variations of standard user messages to make sure the function is adequately documented in the `manifest.json`


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
