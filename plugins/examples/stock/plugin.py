"""
Stock Price Plugin for G-Assist - V2 SDK Version

Provides stock price information via the Twelve Data API.
"""

import os
import sys

# ============================================================================
# PATH SETUP - Must be FIRST before any third-party imports!
# ============================================================================
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# Now we can import third-party libraries
import json
import logging
import webbrowser
from typing import Any, Callable, Dict, Optional

import requests

try:
    from gassist_sdk import Plugin
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "stock"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================
API_KEY: Optional[str] = None
SETUP_COMPLETE = False
PENDING_CALL: Optional[Dict[str, Any]] = None  # {"func": callable, "args": {...}}


def load_config():
    """Load API key from config file."""
    global API_KEY, SETUP_COMPLETE
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
        API_KEY = config.get("TWELVE_DATA_API_KEY", "")
        if API_KEY and len(API_KEY) > 10:
            SETUP_COMPLETE = True
            logger.info(f"Successfully loaded API key from {CONFIG_FILE}")
        else:
            logger.warning(f"API key is empty or invalid in {CONFIG_FILE}")
            API_KEY = None
    except FileNotFoundError:
        logger.error(f"Config file not found at {CONFIG_FILE}")
    except Exception as e:
        logger.error(f"Error loading config: {e}")


def store_pending_call(func: Callable, **kwargs):
    """Store a function call to execute after setup completes."""
    global PENDING_CALL
    PENDING_CALL = {"func": func, "args": kwargs}
    logger.info(f"[SETUP] Stored pending call: {func.__name__}({kwargs})")


def execute_pending_call() -> Optional[str]:
    """Execute the stored pending call if one exists. Returns result or None."""
    global PENDING_CALL
    if not PENDING_CALL:
        return None
    
    func = PENDING_CALL["func"]
    args = PENDING_CALL["args"]
    PENDING_CALL = None  # Clear before executing
    
    logger.info(f"[SETUP] Executing pending call: {func.__name__}({args})")
    return func(_from_pending=True, **args)

# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Stock price lookup via Twelve Data API"
)

def get_setup_instructions() -> str:
    """Return setup wizard instructions."""
    return f"""_
**Stock Plugin - First Time Setup**

Welcome! Let's get your free Twelve Data API key. This takes about **1 minute**.

---

**Step 1: Get Your Free API Key**

I'm opening the Twelve Data signup page for you now...

1. Click **Get Free API Key** (no credit card required)
2. Sign up with your email
3. Copy your API key from the dashboard

---

**Step 2: Configure the Plugin**

I'm opening the config file for you:
```
{CONFIG_FILE}
```

Add your API key:
```
{{"TWELVE_DATA_API_KEY": "your_key_here"}}
```

_(The free tier includes 800 API calls per day — plenty for personal use!)_

Save the file and say **"next"** or **"continue"** when done, and I'll complete your original request.\r"""

# ============================================================================
# COMMANDS
# ============================================================================
def start_setup_wizard() -> str:
    """Start the setup wizard, opening browser and config file."""
    # Open Twelve Data signup page
    try:
        webbrowser.open("https://twelvedata.com/pricing")
    except Exception:
        pass
    # Create and open config file
    try:
        if not os.path.exists(CONFIG_FILE):
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            with open(CONFIG_FILE, "w") as f:
                json.dump({"TWELVE_DATA_API_KEY": ""}, f, indent=2)
        os.startfile(CONFIG_FILE)
    except Exception:
        pass
    return get_setup_instructions()


@plugin.command("get_stock_price")
def get_stock_price(ticker: str = None, company_name: str = None, _from_pending: bool = False):
    """
    Get current stock price for a given ticker or company name.
    
    Args:
        ticker: Stock ticker symbol (e.g., NVDA)
        company_name: Company name to look up
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global API_KEY, SETUP_COMPLETE
    
    # Check if setup is needed
    load_config()
    if not SETUP_COMPLETE or not API_KEY:
        store_pending_call(get_stock_price, ticker=ticker, company_name=company_name)
        logger.info("[COMMAND] API key not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return start_setup_wizard()
    
    query = ticker or company_name
    if not query:
        return (
            "**What should I look up?**\n\n"
            "Please provide a ticker symbol (e.g., `NVDA`) or company name."
        )
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream(f"_Fetching stock price for **{query}**..._\n\n")
    
    url = f"https://api.twelvedata.com/quote?symbol={query}&apikey={API_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "symbol" not in data:
            logger.error(f"No quote found for that input. {data}")
            return (
                f"**No quote found for `{query}`**\n\n"
                "Please check the ticker symbol and try again.\n\n"
                "_Tip: Use the exact ticker symbol (e.g., `NVDA` for NVIDIA)._"
            )
        
        is_market_open = data.get("is_market_open", False)
        price = data.get("close", "0")
        timestamp = data.get("datetime", "unknown time")
        change = data.get("change", "0")
        percent_change = data.get("percent_change", "0")
        
        # Determine price movement direction
        try:
            change_val = float(change)
            if change_val > 0:
                trend = "up"
            elif change_val < 0:
                trend = "down"
            else:
                trend = "unchanged"
        except (ValueError, TypeError):
            trend = "unchanged"
        
        # Format market status
        market_status = "Market Open" if is_market_open else "Market Closed"
        
        logger.info(f"Stock price: {price}, Timestamp: {timestamp}, Market Open: {is_market_open}")
        return (
            f"**{data['symbol']}** — **${price}** USD\n\n"
            f"| | |\n"
            f"|---|---|\n"
            f"| **Change** | ${change} ({percent_change}%) {trend} |\n"
            f"| **Status** | {market_status} |\n"
            f"| **As of** | {timestamp} |"
        )
    except Exception as e:
        logger.error(f"Error in get_stock_price: {str(e)}")
        return (
            "**Connection error.**\n\n"
            "Unable to fetch stock price. Please check your internet connection and try again."
        )


@plugin.command("get_ticker_from_company")
def get_ticker_from_company(company_name: str = "", _from_pending: bool = False):
    """
    Get stock ticker symbol from company name.
    
    Args:
        company_name: Name of the company to look up
        _from_pending: Internal flag, True when called from execute_pending_call
    """
    global API_KEY, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not API_KEY:
        store_pending_call(get_ticker_from_company, company_name=company_name)
        logger.info("[COMMAND] API key not configured - starting setup wizard")
        plugin.set_keep_session(True)
        return start_setup_wizard()
    
    if not company_name:
        return "**What company?** Please provide a company name to look up."
    
    if not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream(f"_Looking up ticker for **{company_name}**..._\n\n")
    
    url = f"https://api.twelvedata.com/symbol_search?symbol={company_name}&apikey={API_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        results = response.get("data", [])
        if not results:
            logger.error(f"No match found for company name. {response}")
            return (
                f"**No match found for \"{company_name}\"**\n\n"
                "Please check the spelling and try again.\n\n"
                "_Tip: Try the full company name or a well-known abbreviation._"
            )
        best = results[0]
        logger.info(f"Found ticker for '{best['instrument_name']}' on {best['exchange']}: {best['symbol']}")
        return (
            f"**{best['instrument_name']}**\n\n"
            f"| | |\n"
            f"|---|---|\n"
            f"| **Ticker** | `{best['symbol']}` |\n"
            f"| **Exchange** | {best['exchange']} |"
        )
    except Exception as e:
        logger.error(f"Error in get_ticker_from_company: {str(e)}")
        return (
            "**Connection error.**\n\n"
            "Unable to look up ticker. Please check your internet connection and try again."
        )


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE
    
    load_config()
    if SETUP_COMPLETE:
        plugin.stream("_ ")  # Close engine's italic
        plugin.stream("_API key verified!_\n\n")
        result = execute_pending_call()
        if result is not None:
            plugin.set_keep_session(False)
            return result
        else:
            plugin.set_keep_session(False)
            return (
                "**You're all set!**\n\n"
                "You can now:\n\n"
                "- Get **stock prices** by ticker (e.g., `NVDA`)\n"
                "- Look up **ticker symbols** by company name\n\n"
                "_Try: \"What's the stock price of NVIDIA?\"_"
            )
    else:
        plugin.set_keep_session(True)
        return (
            "**API key not found.**\n\n"
            "The config file is still empty or invalid.\n\n"
            "---\n\n"
            "Please make sure you:\n"
            "1. Pasted your **Twelve Data API Key**\n"
            "2. **Saved** the file\n\n"
            f"_Config:_ `{CONFIG_FILE}`\n\n"
            "Say **\"next\"** or **\"continue\"** when ready."
        )


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Stock plugin (SDK version)...")
    load_config()
    plugin.run()
