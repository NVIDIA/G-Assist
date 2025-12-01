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
from typing import Any, Dict, Optional

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
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================
API_KEY: Optional[str] = None
SETUP_COMPLETE = False

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
    return f"""
STOCK PLUGIN - FIRST TIME SETUP
================================

Welcome! Let's get your free Twelve Data API key. This takes about 1 minute.

YOUR TASK - Get Your Free API Key:
   1. Visit: https://twelvedata.com/pricing
   2. Click "Get Free API Key" (no credit card required)
   3. Sign up with your email
   4. Copy your API key from the dashboard
   5. Open this file: {CONFIG_FILE}
   6. Replace the empty quotes with your API key:
      {{"TWELVE_DATA_API_KEY": "your_key_here"}}
   7. Save the file

After saving, send me ANY message (like "done") and I'll verify it!

Note: The free tier includes 800 API calls per day - plenty for personal use!
"""

# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("get_stock_price")
def get_stock_price(ticker: str = None, company_name: str = None):
    """
    Get current stock price for a given ticker or company name.
    
    Args:
        ticker: Stock ticker symbol (e.g., NVDA)
        company_name: Company name to look up
    """
    global API_KEY, SETUP_COMPLETE
    
    # Check if setup is needed
    load_config()
    if not SETUP_COMPLETE or not API_KEY:
        logger.info("[COMMAND] API key not configured - showing setup wizard")
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    query = ticker or company_name
    if not query:
        return "Please provide either a ticker symbol or company name."
    
    plugin.stream(f"Fetching stock price for {query}...")
    
    url = f"https://api.twelvedata.com/quote?symbol={query}&apikey={API_KEY}"
    try:
        data = requests.get(url, timeout=10).json()
        if "symbol" not in data:
            logger.error(f"No quote found for that input. {data}")
            return f"No quote found for '{query}'."
        
        is_market_open = data.get("is_market_open", False)
        price = data.get("close", "0")
        price_type = "current" if is_market_open else "closing"
        timestamp = data.get("datetime", "unknown time")
        change = data.get("change", "0")
        percent_change = data.get("percent_change", "0")
        
        logger.info(f"Stock price: {price}, Timestamp: {timestamp}, Market Open: {is_market_open}")
        return (
            f"The {price_type} stock price for {data['symbol']} is ${price} USD (as of {timestamp}). "
            f"Change: ${change} ({percent_change}%)"
        )
    except Exception as e:
        logger.error(f"Error in get_stock_price: {str(e)}")
        return "Failed to fetch stock price."


@plugin.command("get_ticker_from_company")
def get_ticker_from_company(company_name: str = ""):
    """
    Get stock ticker symbol from company name.
    
    Args:
        company_name: Name of the company to look up
    """
    global API_KEY, SETUP_COMPLETE
    
    load_config()
    if not SETUP_COMPLETE or not API_KEY:
        plugin.set_keep_session(True)
        return get_setup_instructions()
    
    if not company_name:
        return "Missing company_name."
    
    plugin.stream(f"Looking up ticker for {company_name}...")
    
    url = f"https://api.twelvedata.com/symbol_search?symbol={company_name}&apikey={API_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        results = response.get("data", [])
        if not results:
            logger.error(f"No match found for company name. {response}")
            return "No match found for company name."
        best = results[0]
        logger.info(f"Found ticker for '{best['instrument_name']}' on {best['exchange']}: {best['symbol']}")
        return f"Found ticker for '{best['instrument_name']}' on {best['exchange']}: {best['symbol']}"
    except Exception as e:
        logger.error(f"Error in get_ticker_from_company: {str(e)}")
        return "Failed to get ticker from company name."


@plugin.command("on_input")
def on_input(content: str = ""):
    """Handle user input during setup wizard."""
    global SETUP_COMPLETE, API_KEY
    
    load_config()
    if SETUP_COMPLETE and API_KEY:
        plugin.set_keep_session(False)
        return "✓ API key configured! You can now ask about stock prices. Try: 'What's the price of NVDA?'"
    else:
        plugin.set_keep_session(True)
        return get_setup_instructions()


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Stock plugin (SDK version)...")
    load_config()
    plugin.run()
