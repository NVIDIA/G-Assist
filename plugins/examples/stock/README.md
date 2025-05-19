# Stock Market Plugin for NVIDIA G-Assist

Transform your G-Assist experience with real-time stock market data! This plugin lets you check stock prices and company information directly through the G-Assist platform. Whether you want to know the current price of a stock or look up a company's ticker symbol, getting market data has never been easier.

## What Can It Do?
- Get current stock prices for any publicly traded company
- Look up stock ticker symbols from company names
- Real-time market data including:
  - Current/closing price
  - Price changes
  - Market status
- Detailed logging for troubleshooting

## Before You Start
Make sure you have:
- Python 3.6 or higher installed
- Twelve Data API key - Visit [Twelve Data](https://twelvedata.com/pricing) to get a free API key
- NVIDIA G-Assist installed

## Quickstart

### Step 1: Get the Files
```bash
git clone <repo link>
cd stock
```
This downloads all the necessary files to your computer.

### Step 2: Setup and Build
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

### Step 3: Install the Plugin
1. Navigate to the `dist` folder created by the build script
2. Copy the `stock` folder to:
```bash
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins
```

💡 **Tip**: Make sure all files are copied, including:
- The executable
- manifest.json
- config.json (you'll need to update this with your API key)

### Step 4: Configure Your API Key
1. Open `config.json` in the plugin directory
2. Add your Twelve Data API key:
```json
{
    "TWELVE_DATA_API_KEY": "your_api_key_here"
}
```

## How to Use
Once everything is set up, you can check stock prices through simple chat commands!

Try these commands:
- `Hey stock, what's the stock price for NVIDIA?`
- `/stock Check the price of AMC`
- `/stock What's the ticker symbol for GameStop?`

### Example Responses

When checking a stock price:
```text
The current stock price for NVDA is $96.91 USD (as of 2024-03-14). Change: $-4.58 (-4.51%)
```

When looking up a ticker:
```text
Found ticker for 'NVIDIA Corporation' on NASDAQ: NVDA
```

## Troubleshooting Tips

### API Issues
- **Getting "Failed to fetch stock price" errors?**
  - Verify your API key in config.json
  - Check if you've exceeded your API limit

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\stock_plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Architecture Overview
The Stock plugin is implemented as a Python-based service that communicates the Twelve Data API to provide real-time stock market data and company information.

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

#### Command Structure
Commands are sent as JSON with the following structure:
```json
{
  "tool_calls": [{
    "func": "command_name",
    "params": {
      "param1": "value1"
    },
    "messages": [],
    "system_info": ""
  }]
}
```

### Available Commands

#### Stock Price Lookup
- `execute_get_stock_price_command()`: Get current stock price
  - Parameters:
    - `ticker`: Stock symbol (e.g., "NVDA")
    - `company_name`: Company name (e.g., "NVIDIA")
  - Returns:
    - Current/closing price
    - Price change
    - Market status
    - Timestamp

#### Company Information
- `execute_get_ticker_from_company_command()`: Look up stock symbol
  - Parameters:
    - `company_name`: Name of the company
  - Returns:
    - Ticker symbol
    - Exchange
    - Company name

### Configuration

#### API Integration
- Uses Twelve Data API for market data
- API key stored in `config.json`:
  ```json
  {
    "TWELVE_DATA_API_KEY": "your_api_key_here"
  }
  ```
- Base URL: `https://api.twelvedata.com`

### Error Handling
- Comprehensive error handling for API calls
- User-friendly error messages
- Detailed logging of errors and responses
- Type checking for parameters
- Validation of API responses

### Logging
- Log file: `%USERPROFILE%\stock_plugin.log`
- Log level: DEBUG
- Format: `%(asctime)s - %(levelname)s - %(message)s`
- Logs include:
  - Command processing
  - API requests and responses
  - Error details
  - Plugin lifecycle events

### Adding New Features
To add new features:
1. Add new command to the `commands` dictionary in `main()`
2. Implement corresponding execute function with proper type hints
3. Add proper error handling and logging
4. Add the function to the `functions` list in `manifest.json` file: 
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
5. Manually test the function:

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
6. Run the setup & build scripts as outlined above, install the plugin by placing the files in the proper location and test your updated plugin. Use variations of standard user messages to make sure the function is adequately documented in the `manifest.json`

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the [Twelve Data API](https://twelvedata.com/docs)
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.