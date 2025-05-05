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
- Twelve Data API key
- NVIDIA G-Assist installed

💡 **Tip**: Don't have a Twelve Data API key yet? Visit [Twelve Data](https://twelvedata.com/pricing) to get a free API key!

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
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\stock
```
💡 **Tip**: Copy and paste this path into File Explorer's address bar for easy navigation!

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
Once everything is set up, you can check stock prices through simple chat commands! Just talk to your assistant using natural language.

Try these commands:
- "Hey, what's the stock price for NVIDIA?"
- "Check the price of AMC"
- "What's the ticker symbol for GameStop?"

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
  - Make sure config.json is in the correct location

### Connection Issues
- **Plugin not responding?**
  - Check if Python is installed correctly
  - Verify your internet connection
  - Make sure the Twelve Data API is accessible

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\stock_plugin.log
```
Check this file for detailed error messages and debugging information.

## Next Steps
- **Feature Enhancements**
  - Add historical price data
  - Implement market news
  - Add technical indicators
  - Create watchlist features

- **Documentation**
  - Add usage examples
  - Write troubleshooting guide
  - Document common issues and solutions

## Need Help?
If you run into issues:
1. Check the log file for specific error messages
2. Verify your API key is valid
3. Make sure all files are in the correct locations
4. Try restarting the G-Assist platform

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the [Twelve Data API](https://twelvedata.com/docs)
- Part of the NVIDIA G-Assist platform
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.