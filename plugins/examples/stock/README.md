# Stock Market Plugin for NVIDIA G-Assist

Transform your G-Assist experience with real-time stock market data! This plugin lets you check stock prices and company information directly through the G-Assist platform. Whether you want to know the current price of a stock or look up a company's ticker symbol, getting market data has never been easier.

## What Can It Do?
- Get current stock prices for any publicly traded company
- Look up stock ticker symbols from company names
- Real-time market data including:
  - Current/closing price
  - Price changes with trend direction
  - Market status (open/closed)
- **Exchange support** — defaults to NASDAQ, with optional override for NYSE, AMEX, etc.
- **Interactive setup wizard** — guides you through configuration step-by-step
- Detailed logging for troubleshooting

## Before You Start
Make sure you have:
- Python 3.8 or higher installed
- NVIDIA G-Assist installed
- Internet connection

> **Note:** You'll need a Twelve Data API key, but the plugin will guide you through getting one for free during first-time setup!

## Quickstart

### Step 1: Setup
From the `plugins/examples` directory, run:
```bash
setup.bat stock
```
This installs dependencies to the `libs/` folder and copies the G-Assist SDK.

### Step 2: Deploy
```bash
setup.bat stock -deploy
```
This copies the plugin files to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\stock
```

💡 **Tip**: Make sure G-Assist is closed when deploying!

### Step 3: Start Using It!
Just ask G-Assist about any stock — the plugin will automatically guide you through setup if needed!

## First-Time Setup

When you first use the Stock plugin, it automatically launches an **interactive setup wizard**:

1. **Ask about any stock** — for example: *"What's the NVIDIA stock price?"*
2. **The wizard opens automatically** — it will:
   - Open the Twelve Data signup page in your browser
   - Open the config file for you to edit
   - Display step-by-step instructions
3. **Get your free API key** (takes ~1 minute, no credit card required)
4. **Paste it in the config file** and save
5. **Say "next" or "continue"** — the plugin verifies your key and completes your original request!

The free tier includes **800 API calls per day** — plenty for personal use.

## How to Use

Once set up, check stock prices through simple chat commands:

**Stock Prices:**
- "What's the stock price for NVIDIA?"
- "Check the price of AMC"
- "What's Tesla trading at?"
- "How much is NVDA?"
- "Get the price of AAPL on NYSE"

**Ticker Lookup:**
- "What's the ticker symbol for GameStop?"
- "Find the ticker for Apple"
- "Look up Microsoft on NYSE"

### Example Responses

**Stock Price:**
```
NVDA — $96.91 USD (-4.51% down)

Change: $-4.58 · Market Closed · 2024-03-14 16:00:00
```

**Ticker Lookup:**
```
NVIDIA Corporation — NVDA

Exchange: NASDAQ
```

## Configuration

The plugin stores its configuration at:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\stock\config.json
```

**Config format:**
```json
{
  "TWELVE_DATA_API_KEY": "your_api_key_here"
}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "No quote found" errors | Use exact ticker symbol (e.g., `NVDA` not `NVIDIA`). Try looking up the ticker first. |
| "Connection error" messages | Check internet connection, verify API key, check if you've exceeded daily limit (800 calls/day) |
| Setup wizard keeps appearing | Make sure you saved the config file. API key must be at least 10 characters. |
| Plugin not loading | Verify files are deployed and restart G-Assist |

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\stock\stock-plugin.log
```
Check this file for detailed error messages and debugging information.

## Developer Documentation

### Architecture Overview
The Stock plugin is built on the **G-Assist SDK (V2)** and communicates with the Twelve Data API to provide real-time stock market data.

### Core Components

#### Plugin Setup
```python
plugin = Plugin(
    name="stock",
    version="2.0.0",
    description="Stock price lookup via Twelve Data API"
)
```

#### Commands
Commands are registered using the `@plugin.command()` decorator:

| Command | Description | Parameters |
|---------|-------------|------------|
| `get_stock_price` | Get current stock price | `ticker`, `company_name`, `exchange` (default: NASDAQ) |
| `get_ticker_from_company` | Look up ticker symbol | `company_name`, `exchange` (default: NASDAQ) |
| `on_input` | Handle setup wizard input | `content` |

#### Setup Wizard Flow
The plugin implements a pending call pattern for seamless setup:
1. User requests stock data
2. Plugin detects missing API key
3. Original request is stored via `store_pending_call()`
4. Setup wizard launches (opens browser + config file)
5. User completes setup and says "next"
6. `execute_pending_call()` runs the original request

### Configuration
- **API:** Twelve Data (`https://api.twelvedata.com`)
- **Config file:** `config.json` in plugin directory
- **Log level:** INFO
- **Log format:** `%(asctime)s - %(levelname)s - %(message)s`

### Adding New Features

1. Add a new command using the `@plugin.command()` decorator:
   ```python
   @plugin.command("my_new_command")
   def my_new_command(param1: str = "", _from_pending: bool = False):
       """Command description."""
       # Check setup
       load_config()
       if not SETUP_COMPLETE or not API_KEY:
           store_pending_call(my_new_command, param1=param1)
           plugin.set_keep_session(True)
           return start_setup_wizard()
       
       # Your logic here
       return "Result"
   ```

2. Add the function to `manifest.json`:
   ```json
   {
     "name": "my_new_command",
     "description": "Description of what the command does",
     "tags": ["relevant", "tags"],
     "properties": {
       "param1": {
         "type": "string",
         "description": "Description of the parameter"
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
   setup.bat stock -deploy
   ```

3. **Plugin emulator** - Test commands without G-Assist:
   ```bash
   python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
   ```
   Then select the stock plugin and test commands interactively.

4. **G-Assist test** - Open G-Assist and try: "What's the stock price of NVIDIA?"

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
- Built using the [Twelve Data API](https://twelvedata.com/docs)
- Powered by the G-Assist SDK V2
- We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.
