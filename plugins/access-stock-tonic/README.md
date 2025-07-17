# Access Stock Tonic – G-Assist Plugin

## How NVIDIA Project G-Assist Uses AI Natively

NVIDIA's Project G-Assist leverages the power of GeForce RTX GPUs to run a Small Language Model (SLM) locally on the user's PC, enabling fast, private, and offline AI assistance. Key features include:

- **Local AI Processing:** An 8B-parameter Llama-based SLM runs directly on RTX GPUs, processing natural language (voice or text) without cloud dependency.
- **Context-Aware Assistance:** Integrates with NVIDIA's ecosystem, using computer vision and system telemetry to provide in-game tips, system diagnostics, and real-time recommendations tailored to the user's context.
- **System Optimization:** Interprets hardware/software configurations, offering actionable advice, safe overclocking, and control of NVIDIA features and peripherals—all via local AI.
- **Plugin Architecture:** Supports extensibility through custom plugins (JSON, Python), allowing community-driven enhancements and integrations, all processed locally.
- **Low Performance Impact:** Designed as an overlay, it analyzes frames only when needed, ensuring minimal impact on gaming or system performance.

By running AI natively on RTX GPUs, G-Assist delivers privacy, speed, and efficiency, making it a powerful tool for gamers and creators to optimize and enhance their experience—without relying on external servers.

---

**Access Stock Tonic** is an accessibility-focused G-Assist plugin that makes market news, sentiment, and predictions instantly accessible—especially for users with auditory or mobility handicaps—by changing your keyboard’s lighting in real time based on financial events and analysis. The plugin supports both audio (voice) and keyboard (text) input for maximum accessibility.

## What Can It Do?
- **Visual Market Alerts:** Changes your keyboard color based on how soon a major news event or earnings report is due, using a configurable color gradient.
- **Accessible Market Summaries:** Surfaces market news, sentiment, and predictions as visual cues, making financial information accessible to everyone.
- **Automated Stock Analysis:** Uses yfinance to build a live-updating calendar of news events for your selected tickers.
- **AI-Powered Advisory:** Runs advanced predictions using the latest market data and the plugin’s agent workflow.
- **Flexible Input:** Supports both audio (voice) and keyboard (text) commands for all interactions.

## How It Works

1. **Install and Run the Plugin**
   - Launch the plugin and you’ll be greeted with a welcome/configuration screen.
   - Enter your stock tickers and configure your preferences (color scheme, update frequency, etc.).

2. **News Calendar Generation**
   - The plugin uses yfinance to fetch a calendar of upcoming news events, earnings, and press releases for your selected stocks.
   - The calendar updates regularly to ensure you never miss an important event.

3. **Prediction and Advisory**
   - For each event, the plugin uses `/src/tools/stockpredictions.py` to generate market predictions.
   - The workflow in `/src/workflow/state_machine.py` and the agents in `/src/agents/` analyze the data and produce actionable advisories.

4. **Keyboard Color Feedback**
   - The plugin changes your keyboard’s color based on how close you are to a news event:
     - **Far from event:** One color (e.g., blue)
     - **Approaching event:** Gradually shifts to another color (e.g., yellow)
     - **Event imminent:** Alert color (e.g., red)
   - The color mapping and transition are fully configurable.

5. **Continuous Updates**
   - The system regularly refreshes the news calendar and predictions, keeping your visual alerts up to date.

---

## Installation Guide

### Prerequisites

- Windows PC
- Python 3.12 or higher installed
- G-Assist installed on your system
- pywin32 >= 223
- (Optional) API keys for advanced LLM/MCP features (OpenAI, Anthropic, HuggingFace)
- Basic knowledge of Python
- A compatible RGB keyboard (for lighting feedback)

---

## Installation Guide

### Step 1: Get the Files
```bash
git clone <repo link>
cd access-stock-tonic
```
This downloads all the necessary files to your computer.

### Step 2: Set Up Python Environment

```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```

### Step 3: Configure the Plugin
1. Edit `config.json` (if present) to set your preferences and API keys.
2. (Optional) Set up a `.env` file for environment variables (API keys, etc).

### Step 4: Build the Plugin (if required)
If a build step is needed (e.g., for C++/binary components), follow the instructions in the repo. For pure Python, you can skip this step.

### Step 5: Install the Plugin
Copy the plugin folder to your G-Assist plugins directory, e.g.:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\access-stock-tonic
```

## How to Use
Once installed, you can interact with Access Stock Tonic through G-Assist using voice or text commands. Example commands:
- "Hey stock tonic, what's the news for AAPL?"
- "/access-stock-tonic Show me upcoming earnings for MSFT"
- "/access-stock-tonic Give me a market prediction for TSLA"
- "Change my keyboard color to reflect the next market event"


### Keyboard Color Feedback
- The plugin automatically changes your keyboard’s color based on how close you are to a news event or earnings report:
  - **Far from event:** Calm color (e.g., blue)
  - **Approaching event:** Transition color (e.g., yellow)
  - **Event imminent:** Alert color (e.g., red)
- Color mapping and timing are configurable in `config.json`.


### Supported Commands
- **configure color feedback [none / near / imminent] [color]**
- **add [stockticker] to calendar**  
  Adds the specified stock ticker to your tracked calendar.
- **update calendar**  
  Refreshes the news/events calendar for all tracked tickers.
- **get today's events**  
  Lists all news, earnings, and press release events scheduled for today.
- **get [stockticker] analysis**  
  Provides a prediction and advisory for the specified stock.
- **get [stockticker] data**  
  Returns the latest data and news for the specified stock.
  
### Example Usage
- **Voice:**
  - "Add AAPL to calendar"
  - "Get today's events"
  - "Get TSLA analysis"
- **Text:**
  - `add MSFT to calendar`
  - `get GOOGL data`

### Example Response
When a major news event is approaching:
```
AAPL: Earnings report in 2 hours. Keyboard color set to orange (alert).
```

When no events are near:
```
No major news for your tracked tickers in the next 24 hours. Keyboard color set to blue.
```

---

## Advanced Stock Prediction Entrypoints

Access Stock Tonic now provides advanced AI-powered stock prediction entrypoints for G-Assist, supporting daily, hourly, and 15-minute intervals. These entrypoints leverage the latest market data, technical indicators, and ensemble AI models for robust, actionable predictions.

### Prediction Entrypoints
- **predict_daily**: Get daily-level predictions and analysis for a stock.
- **predict_hourly**: Get hourly-level predictions and analysis for a stock (market hours only).
- **predict_min15**: Get 15-minute interval predictions and analysis for a stock (market hours only).

#### Parameters (all entrypoints)
- `symbol` (str): Stock ticker symbol (e.g., "AAPL")
- `prediction_days` (int): Number of days (or intervals) to predict
- `lookback_days` (int): Historical lookback window
- `strategy` (str): Prediction strategy ("chronos" or "technical")
- `use_ensemble` (bool): Use ensemble models (default: True)
- `use_regime_detection` (bool): Use market regime detection (default: True)
- `use_stress_testing` (bool): Run stress test scenarios (default: True)
- `risk_free_rate` (float): Annual risk-free rate (default: 0.02)
- `market_index` (str): Market index for correlation (default: "^GSPC")
- `chronos_weight`, `technical_weight`, `statistical_weight` (float): Ensemble weights
- `random_real_points` (int): Number of random real points for context
- `use_smoothing` (bool): Apply smoothing to predictions
- `smoothing_type` (str): Smoothing algorithm ("exponential", etc.)
- `smoothing_window` (int): Smoothing window size
- `smoothing_alpha` (float): Smoothing alpha
- `use_covariates` (bool): Use covariate data (default: True)
- `use_sentiment` (bool): Use sentiment analysis (default: True)

#### Example G-Assist Command
- "Get a daily prediction for AAPL"
- "Show me hourly stock prediction for TSLA"
- "Give me a 15-minute forecast for MSFT"

#### Example JSON Tool Call
```json
{
  "tool_calls": [{
    "func": "predict_daily",
    "params": {
      "symbol": "AAPL",
      "prediction_days": 30,
      "lookback_days": 365
    },
    "messages": [],
    "system_info": ""
  }]
}
```

#### Output
Each prediction entrypoint returns a structured dictionary with:
- Trading signals (RSI, MACD, Bollinger, SMA, overall)
- Interactive plot (if supported)
- Product metrics (market cap, sector, ratios, etc.)
- Risk metrics (Sharpe, VaR, drawdown, etc.)
- Sector metrics
- Regime and stress test results
- Ensemble and advanced signals
- Historical and predicted data arrays

---

## Project Structure and Technical Overview

The Access Stock Tonic plugin is built to integrate seamlessly with the G-Assist plugin architecture. Here’s how the project is organized and how the system works under the hood:

### Directory Structure

```
plugins/access-stock-tonic/
├── plugin.py                # Main entry point for the plugin (pipe-based command handler)
├── manifest.json            # Plugin manifest (function definitions, tags, parameters)
├── config.json              # User configuration (API keys, color preferences, etc.)
├── src/
│   ├── agents/              # Modular agents for query processing, stock picking, analysis, summarization, bundling
│   ├── tools/               # Tools for stock prediction, yfinance integration, etc.
│   └── workflow/            # Workflow orchestration (state machine, config)
└── ... (docs, requirements, etc.)
```

### G-Assist Plugin Architecture
- **Pipe-Based Communication:**
  - The plugin communicates with G-Assist via standard input/output pipes. All commands and responses are JSON-formatted.
  - `plugin.py` sits in a loop, reading commands, dispatching them to the correct handler, and writing responses back.
- **Manifest-Driven:**
  - `manifest.json` describes the available functions, their parameters, and tags. This allows G-Assist to discover and invoke plugin capabilities.
- **Configurable:**
  - `config.json` (and optionally `.env`) stores user preferences, API keys, and color mappings.

### Command Flow
1. **User Input:**
   - The user issues a command via voice or keyboard (e.g., "get TSLA analysis").
2. **G-Assist Dispatch:**
   - G-Assist parses the command and sends a JSON request to the plugin’s input pipe.
3. **Command Handling:**
   - `plugin.py` receives the command, looks up the corresponding function (e.g., `get_analysis`), and invokes the appropriate logic.
4. **Agent/Tool Processing:**
   - The plugin leverages agents in `src/agents/` and tools in `src/tools/` to fetch data, run predictions, and analyze results.
   - For example, `src/tools/stockpredictions.py` is used for advanced market analysis.
5. **Workflow Orchestration:**
   - The workflow logic in `src/workflow/state_machine.py` manages multi-step processes, such as updating the calendar, running analyses, and bundling results.
6. **Keyboard Feedback:**
   - Based on the analysis and event timing, the plugin uses keyboard control libraries to set the color of your keyboard, providing a visual alert.
7. **Response:**
   - The plugin sends a JSON-formatted response back to G-Assist, which is then surfaced to the user (via text or audio output).

### Extensibility
- **Adding New Commands:**
  - Implement a new function in `plugin.py` and register it in the command handler and `manifest.json`.
  - Add supporting logic in `src/agents/` or `src/tools/` as needed.
- **Custom Workflows:**
  - Modify or extend the state machine in `src/workflow/state_machine.py` to support new multi-step processes.
- **Color Feedback:**
  - Update `config.json` to change color mappings or add new feedback modes.

---

## Troubleshooting Tips
- **Plugin not starting?** Check Python version and dependencies.
- **No keyboard color change?** Ensure your keyboard supports lighting control and the required drivers are installed.
- **No news events?** Double-check your ticker symbols and internet connection.
- **Missing logs?** Ensure write permissions in your user profile directory.

---

## Developer Documentation

### Command Structure
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
- `configure color feedback [none / near / imminent] [color]` : configures the keyboard colors
- `add_to_calendar`: Adds a stock ticker to the calendar
- `update_calendar`: Refreshes the calendar
- `get_todays_events`: Lists today's events
- `get_analysis`: Provides prediction/advisory for a stock
- `get_data`: Returns latest data/news for a stock
- `set_keyboard_color`: Manually set keyboard color
- `auto_color_update`: Automatically update keyboard color based on event proximity
- `predict_daily`: Advanced daily stock prediction and analysis
- `predict_hourly`: Advanced hourly stock prediction and analysis
- `predict_min15`: Advanced 15-minute interval stock prediction and analysis

### Calendar/Event Tracking & Testing

#### CalendarTool Functionality
- Track any number of stock tickers for important calendar events (earnings, dividends, etc.)
- Uses yfinance to fetch and update event data for each ticker
- Supports commands:
  - `add [ticker] to calendar` (track a ticker)
  - `remove [ticker] from calendar` (untrack a ticker)
  - `update calendar` (refresh all tracked tickers' events)
  - `get today's events` (list all events for today)
  - `get events for [ticker]` (list all known events for a ticker)
- Persists tracked tickers in a JSON file for continuity

#### Testing
- Comprehensive test suite in `tests/test_calendar_tool.py`
- Tests cover: add/remove, persistence, event fetching, updating, today's events, and the tool's main interface
- All yfinance calls are mocked for reliability and speed
- To run tests:
  ```bash
  pytest plugins/access-stock-tonic/tests/test_calendar_tool.py --disable-warnings -v
  ```
- All tests must pass for a valid build

### Logging
- All activity is logged to `%USERPROFILE%\access_stock_tonic.log`
- Logs include command processing, event detection, color changes, and errors

---

### Extending Prediction Entrypoints
The prediction entrypoints are implemented in `src/tools/predictions.py` and registered in `plugin.py`. To add new prediction types or customize the analysis, extend these functions and update the command handler and manifest as needed. All entrypoints support robust error handling and parameterization for advanced use cases.

### Adding New Features
To add new features:
1. Add a new command to the `commands` dictionary in `plugin.py`
2. Implement the corresponding function with proper type hints and error handling
3. Add the function to the `functions` list in `manifest.json`:
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
4. Manually test the function using G-Assist or by running the plugin directly

---

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.