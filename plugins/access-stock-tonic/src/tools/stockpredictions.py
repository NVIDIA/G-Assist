import gradio as gr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf
import torch
from chronos import ChronosPipeline
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sklearn.preprocessing import MinMaxScaler, StandardScaler
import plotly.express as px
from typing import Dict, List, Tuple, Optional, Union
import json
import spaces
import gc
import pytz
import time
import random
from scipy import stats
from scipy.optimize import minimize
import warnings
import threading
from dataclasses import dataclass
from transformers import GenerationConfig
warnings.filterwarnings('ignore')

# Additional imports for advanced features
try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    print("Warning: hmmlearn not available. Regime detection will use simplified methods.")

try:
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.linear_model import LinearRegression, Ridge, Lasso
    from sklearn.svm import SVR
    from sklearn.neural_network import MLPRegressor
    from sklearn.model_selection import TimeSeriesSplit, cross_val_score
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    ENSEMBLE_AVAILABLE = True
except ImportError:
    ENSEMBLE_AVAILABLE = False
    print("Warning: scikit-learn not available. Ensemble methods will be simplified.")

# Additional imports for enhanced features
try:
    import requests
    import re
    from textblob import TextBlob
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False
    print("Warning: sentiment analysis not available.")

try:
    from arch import arch_model
    GARCH_AVAILABLE = True
except ImportError:
    GARCH_AVAILABLE = False
    print("Warning: arch not available. GARCH modeling will be simplified.")

# Market status management
@dataclass
class MarketStatus:
    """Data class to hold market status information"""
    is_open: bool
    status_text: str
    next_trading_day: str
    last_updated: str
    time_until_open: str
    time_until_close: str
    current_time_et: str
    market_name: str
    market_type: str
    market_symbol: str

# Global configuration for market status updates
MARKET_STATUS_UPDATE_INTERVAL_MINUTES = 10  # Update every 10 minutes

# Market configurations for different exchanges
MARKET_CONFIGS = {
    'US_STOCKS': {
        'name': 'US Stock Market',
        'symbol': '^GSPC',  # S&P 500
        'type': 'stocks',
        'timezone': 'US/Eastern',
        'open_time': '09:30',
        'close_time': '16:00',
        'days': [0, 1, 2, 3, 4],  # Monday to Friday
        'description': 'NYSE, NASDAQ, AMEX'
    },
    'US_FUTURES': {
        'name': 'US Futures Market',
        'symbol': 'ES=F',  # E-mini S&P 500
        'type': 'futures',
        'timezone': 'US/Eastern',
        'open_time': '18:00',  # Previous day
        'close_time': '17:00',  # Current day
        'days': [0, 1, 2, 3, 4, 5, 6],  # 24/7 trading
        'description': 'CME, ICE, CBOT'
    },
    'FOREX': {
        'name': 'Forex Market',
        'symbol': 'EURUSD=X',
        'type': 'forex',
        'timezone': 'UTC',
        'open_time': '00:00',
        'close_time': '23:59',
        'days': [0, 1, 2, 3, 4, 5, 6],  # 24/7 trading
        'description': 'Global Currency Exchange'
    },
    'CRYPTO': {
        'name': 'Cryptocurrency Market',
        'symbol': 'BTC-USD',
        'type': 'crypto',
        'timezone': 'UTC',
        'open_time': '00:00',
        'close_time': '23:59',
        'days': [0, 1, 2, 3, 4, 5, 6],  # 24/7 trading
        'description': 'Bitcoin, Ethereum, Altcoins'
    },
    'COMMODITIES': {
        'name': 'Commodities Market',
        'symbol': 'GC=F',  # Gold Futures
        'type': 'commodities',
        'timezone': 'US/Eastern',
        'open_time': '18:00',  # Previous day
        'close_time': '17:00',  # Current day
        'days': [0, 1, 2, 3, 4, 5, 6],  # 24/7 trading
        'description': 'Gold, Silver, Oil, Natural Gas'
    },
    'EUROPE': {
        'name': 'European Markets',
        'symbol': '^STOXX50E',  # EURO STOXX 50
        'type': 'stocks',
        'timezone': 'Europe/London',
        'open_time': '08:00',
        'close_time': '16:30',
        'days': [0, 1, 2, 3, 4],  # Monday to Friday
        'description': 'London, Frankfurt, Paris'
    },
    'ASIA': {
        'name': 'Asian Markets',
        'symbol': '^N225',  # Nikkei 225
        'type': 'stocks',
        'timezone': 'Asia/Tokyo',
        'open_time': '09:00',
        'close_time': '15:30',
        'days': [0, 1, 2, 3, 4],  # Monday to Friday
        'description': 'Tokyo, Hong Kong, Shanghai'
    }
}

class MarketStatusManager:
    """Manages market status with periodic updates for multiple markets"""
    
    def __init__(self):
        self.update_interval = MARKET_STATUS_UPDATE_INTERVAL_MINUTES * 60  # Convert to seconds
        self._statuses = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._update_thread = None
        self._start_update_thread()
    
    def _get_current_market_status(self, market_key: str = 'US_STOCKS') -> MarketStatus:
        """Get current market status with detailed information for specific market"""
        config = MARKET_CONFIGS[market_key]
        now = datetime.now()
        
        # Convert to market timezone
        market_tz = pytz.timezone(config['timezone'])
        market_time = now.astimezone(market_tz)
        
        # Parse market hours
        open_hour, open_minute = map(int, config['open_time'].split(':'))
        close_hour, close_minute = map(int, config['close_time'].split(':'))
        
        # Check if it's a trading day
        is_trading_day = market_time.weekday() in config['days']
        
        # Create market open/close times
        market_open_time = market_time.replace(hour=open_hour, minute=open_minute, second=0, microsecond=0)
        market_close_time = market_time.replace(hour=close_hour, minute=close_minute, second=0, microsecond=0)
        
        # Handle 24/7 markets and overnight sessions
        if config['type'] in ['futures', 'forex', 'crypto', 'commodities']:
            # 24/7 markets are always considered open
            is_open = True
            status_text = f"{config['name']} is currently open (24/7)"
        else:
            # Traditional markets
            if not is_trading_day:
                is_open = False
                status_text = f"{config['name']} is closed (Weekend)"
            elif market_open_time <= market_time <= market_close_time:
                is_open = True
                status_text = f"{config['name']} is currently open"
            else:
                is_open = False
                if market_time < market_open_time:
                    status_text = f"{config['name']} is closed (Before opening)"
                else:
                    status_text = f"{config['name']} is closed (After closing)"
        
        # Calculate next trading day
        next_trading_day = self._get_next_trading_day(market_time, config['days'])
        
        # Calculate time until open/close
        time_until_open = self._get_time_until_open(market_time, market_open_time, config)
        time_until_close = self._get_time_until_close(market_time, market_close_time, config)
        
        return MarketStatus(
            is_open=is_open,
            status_text=status_text,
            next_trading_day=next_trading_day.strftime('%Y-%m-%d'),
            last_updated=market_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
            time_until_open=time_until_open,
            time_until_close=time_until_close,
            current_time_et=market_time.strftime('%H:%M:%S %Z'),
            market_name=config['name'],
            market_type=config['type'],
            market_symbol=config['symbol']
        )
    
    def _get_next_trading_day(self, current_time: datetime, trading_days: list) -> datetime:
        """Get the next trading day for a specific market"""
        next_day = current_time + timedelta(days=1)
        
        # Skip non-trading days
        while next_day.weekday() not in trading_days:
            next_day += timedelta(days=1)
        
        return next_day
    
    def _get_time_until_open(self, current_time: datetime, market_open_time: datetime, config: dict) -> str:
        """Calculate time until market opens"""
        if config['type'] in ['futures', 'forex', 'crypto', 'commodities']:
            return "N/A (24/7 Market)"
        
        if current_time.weekday() not in config['days']:
            # Weekend - calculate to next trading day
            days_until_next = 1
            while (current_time + timedelta(days=days_until_next)).weekday() not in config['days']:
                days_until_next += 1
            
            next_trading_day = current_time + timedelta(days=days_until_next)
            next_open = next_trading_day.replace(
                hour=int(config['open_time'].split(':')[0]),
                minute=int(config['open_time'].split(':')[1]),
                second=0, microsecond=0
            )
            time_diff = next_open - current_time
        else:
            if current_time < market_open_time:
                time_diff = market_open_time - current_time
            else:
                # Market already opened today, next opening is tomorrow
                tomorrow = current_time + timedelta(days=1)
                if tomorrow.weekday() in config['days']:
                    next_open = tomorrow.replace(
                        hour=int(config['open_time'].split(':')[0]),
                        minute=int(config['open_time'].split(':')[1]),
                        second=0, microsecond=0
                    )
                    time_diff = next_open - current_time
                else:
                    # Next day is weekend, calculate to next trading day
                    days_until_next = 1
                    while (current_time + timedelta(days=days_until_next)).weekday() not in config['days']:
                        days_until_next += 1
                    
                    next_trading_day = current_time + timedelta(days=days_until_next)
                    next_open = next_trading_day.replace(
                        hour=int(config['open_time'].split(':')[0]),
                        minute=int(config['open_time'].split(':')[1]),
                        second=0, microsecond=0
                    )
                    time_diff = next_open - current_time
        
        return self._format_time_delta(time_diff)
    
    def _get_time_until_close(self, current_time: datetime, market_close_time: datetime, config: dict) -> str:
        """Calculate time until market closes"""
        if config['type'] in ['futures', 'forex', 'crypto', 'commodities']:
            return "N/A (24/7 Market)"
        
        if current_time.weekday() not in config['days']:
            return "N/A (Weekend)"
        
        if current_time < market_close_time:
            time_diff = market_close_time - current_time
            return self._format_time_delta(time_diff)
        else:
            return "Market closed for today"
    
    def _format_time_delta(self, time_diff: timedelta) -> str:
        """Format timedelta into human-readable string"""
        total_seconds = int(time_diff.total_seconds())
        if total_seconds < 0:
            return "N/A"
        
        days = total_seconds // 86400
        hours = (total_seconds % 86400) // 3600
        minutes = (total_seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def _update_loop(self):
        """Background thread loop for updating market status"""
        while not self._stop_event.is_set():
            try:
                new_statuses = {}
                for market_key in MARKET_CONFIGS.keys():
                    new_statuses[market_key] = self._get_current_market_status(market_key)
                
                with self._lock:
                    self._statuses = new_statuses
                time.sleep(self.update_interval)
            except Exception as e:
                print(f"Error updating market status: {str(e)}")
                time.sleep(60)  # Wait 1 minute before retrying
    
    def _start_update_thread(self):
        """Start the background update thread"""
        if self._update_thread is None or not self._update_thread.is_alive():
            self._stop_event.clear()
            self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
            self._update_thread.start()
    
    def get_status(self, market_key: str = 'US_STOCKS') -> MarketStatus:
        """Get current market status (thread-safe)"""
        with self._lock:
            if market_key not in self._statuses:
                # Initialize if not exists
                self._statuses[market_key] = self._get_current_market_status(market_key)
            return self._statuses[market_key]
    
    def get_all_markets_status(self) -> Dict[str, MarketStatus]:
        """Get status for all markets"""
        with self._lock:
            return self._statuses.copy()
    
    def stop(self):
        """Stop the update thread"""
        self._stop_event.set()
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=5)

# Initialize global variables
pipeline = None
scaler = MinMaxScaler(feature_range=(-1, 1))
scaler.fit_transform([[-1, 1]])

# Global market data cache
market_data_cache = {}
cache_expiry = {}
CACHE_DURATION = 3600  # 1 hour cache

# Initialize market status manager
market_status_manager = MarketStatusManager()

# Enhanced covariate data sources
COVARIATE_SOURCES = {
    'market_indices': ['^GSPC', '^DJI', '^IXIC', '^VIX', '^TNX', '^TYX'],
    'sectors': ['XLF', 'XLK', 'XLE', 'XLV', 'XLI', 'XLP', 'XLU', 'XLB', 'XLY'],
    'commodities': ['GC=F', 'SI=F', 'CL=F', 'NG=F', 'ZC=F', 'ZS=F'],
    'currencies': ['EURUSD=X', 'GBPUSD=X', 'JPYUSD=X', 'CHFUSD=X', 'CADUSD=X']
}

# Economic indicators (using yfinance symbols for simplicity)
ECONOMIC_INDICATORS = {
    'inflation': '^TNX',  # 10-year Treasury yield as proxy
    'volatility': '^VIX',  # VIX volatility index
    'dollar': 'UUP',      # US Dollar Index
    'gold': 'GLD',        # Gold ETF
    'oil': 'USO'          # Oil ETF
}

def retry_yfinance_request(func, max_retries=3, initial_delay=1):
    """
    Retry mechanism for yfinance requests with exponential backoff up to 8 seconds.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
    
    Returns:
        Result of the function call if successful, or None if all attempts fail
    """
    for attempt in range(max_retries):
        try:
            result = func()
            # Check if result is None (common with yfinance for unavailable data)
            if result is None:
                if attempt == max_retries - 1:
                    print(f"Function returned None after {max_retries} attempts")
                    return None
                else:
                    print(f"Function returned None (attempt {attempt + 1}/{max_retries}), retrying...")
                    time.sleep(initial_delay * (2 ** attempt))
                    continue
            return result
        except Exception as e:
            error_str = str(e).lower()
            
            # Check if this is the last attempt
            if attempt == max_retries - 1:
                print(f"Final attempt failed after {max_retries} retries: {str(e)}")
                return None  # Return None instead of raising to avoid crashes
            
            # Determine delay based on error type and attempt number
            if "401" in error_str or "unauthorized" in error_str:
                # Authentication errors - longer delay
                delay = min(8.0, initial_delay * (2 ** attempt) + random.uniform(0, 2))
                print(f"Authentication error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f}s: {str(e)}")
            elif "429" in error_str or "rate limit" in error_str or "too many requests" in error_str:
                # Rate limiting - longer delay
                delay = min(8.0, initial_delay * (2 ** attempt) + random.uniform(1, 3))
                print(f"Rate limit error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f}s: {str(e)}")
            elif "500" in error_str or "502" in error_str or "503" in error_str or "504" in error_str:
                # Server errors - moderate delay
                delay = min(8.0, initial_delay * (2 ** attempt) + random.uniform(0.5, 1.5))
                print(f"Server error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f}s: {str(e)}")
            elif "timeout" in error_str or "connection" in error_str:
                # Network errors - shorter delay
                delay = min(8.0, initial_delay * (2 ** attempt) + random.uniform(0, 1))
                print(f"Network error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f}s: {str(e)}")
            else:
                # Generic errors - standard exponential backoff
                delay = min(8.0, initial_delay * (2 ** attempt) + random.uniform(0, 1))
                print(f"Generic error (attempt {attempt + 1}/{max_retries}), retrying in {delay:.2f}s: {str(e)}")
            
            time.sleep(delay)

def clear_gpu_memory():
    """Clear GPU memory cache"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()

@spaces.GPU()
def load_pipeline():
    """Load the Chronos model without GPU configuration"""
    global pipeline
    try:
        if pipeline is None:
            clear_gpu_memory()
            print("Loading Chronos model...")
            pipeline = ChronosPipeline.from_pretrained(
                "amazon/chronos-t5-large",
                device_map="cuda",  # Force CUDA device mapping
                torch_dtype=torch.float16,
                low_cpu_mem_usage=True,
                trust_remote_code=True,
                use_safetensors=True
            )
            # Set model to evaluation mode
            pipeline.model = pipeline.model.eval()
            # Disable gradient computation
            for param in pipeline.model.parameters():
                param.requires_grad = False
            print("Chronos model loaded successfully")
        return pipeline
    except Exception as e:
        print(f"Error loading pipeline: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Error details: {str(e)}")
        raise RuntimeError(f"Failed to load model: {str(e)}")

def is_market_open() -> bool:
    """Check if the US stock market is currently open (legacy function for backward compatibility)"""
    return market_status_manager.get_status('US_STOCKS').is_open

def get_next_trading_day() -> datetime:
    """Get the next trading day for US stocks (legacy function for backward compatibility)"""
    next_day_str = market_status_manager.get_status('US_STOCKS').next_trading_day
    return datetime.strptime(next_day_str, '%Y-%m-%d')

def get_market_status_display() -> str:
    """Get formatted market status for display with multiple markets"""
    all_statuses = market_status_manager.get_all_markets_status()
    
    if not all_statuses:
        # Fallback to US stocks only
        status = market_status_manager.get_status('US_STOCKS')
        return _format_single_market_status(status)
    
    # Create comprehensive market status display
    status_message = "## 🌍 Global Market Status\n\n"
    
    # Group markets by type
    market_groups = {
        'stocks': ['US_STOCKS', 'EUROPE', 'ASIA'],
        '24/7': ['FOREX', 'CRYPTO', 'US_FUTURES', 'COMMODITIES']
    }
    
    for group_name, market_keys in market_groups.items():
        status_message += f"### {group_name.upper()} MARKETS\n\n"
        
        for market_key in market_keys:
            if market_key in all_statuses:
                status = all_statuses[market_key]
                status_message += _format_market_status_line(status)
        
        status_message += "\n"
    
    # Add summary
    open_markets = sum(1 for status in all_statuses.values() if status.is_open)
    total_markets = len(all_statuses)
    status_message += f"**Summary:** {open_markets}/{total_markets} markets currently open\n\n"
    status_message += f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    
    return status_message

def _format_single_market_status(status: MarketStatus) -> str:
    """Format single market status for display"""
    status_icon = "🟢" if status.is_open else "🔴"
    
    status_message = f"""
    ### {status_icon} {status.market_name}: {status.status_text}
    
    **Current Time ({status.current_time_et.split()[-1]}):** {status.current_time_et}  
    **Next Trading Day:** {status.next_trading_day}  
    **Last Updated:** {status.last_updated}
    
    """
    
    if status.is_open:
        status_message += f"**Time Until Close:** {status.time_until_close}"
    else:
        status_message += f"**Time Until Open:** {status.time_until_open}"
    
    return status_message

def _format_market_status_line(status: MarketStatus) -> str:
    """Format a single line for market status display"""
    status_icon = "🟢" if status.is_open else "🔴"
    market_type_icon = {
        'stocks': '📈',
        'futures': '📊',
        'forex': '💱',
        'crypto': '₿',
        'commodities': '🏭'
    }.get(status.market_type, '📊')
    
    time_info = ""
    if status.is_open:
        if status.time_until_close != "N/A (24/7 Market)":
            time_info = f" | Closes in: {status.time_until_close}"
    else:
        if status.time_until_open != "N/A (24/7 Market)":
            time_info = f" | Opens in: {status.time_until_open}"
    
    return f"{status_icon} {market_type_icon} **{status.market_name}** ({status.market_symbol}){time_info}\n"

def update_market_status() -> str:
    """Function to update market status display (called by Gradio every parameter)"""
    return get_market_status_display()

def cleanup_on_exit():
    """Cleanup function to stop market status manager when application exits"""
    try:
        market_status_manager.stop()
        print("Market status manager stopped successfully")
    except Exception as e:
        print(f"Error stopping market status manager: {str(e)}")

def get_historical_data(symbol: str, timeframe: str = "1d", lookback_days: int = 365) -> pd.DataFrame:
    """
    Fetch historical data using yfinance with enhanced support for intraday data.
    Uses recommended API methods for better reliability.
    
    Args:
        symbol (str): The stock symbol (e.g., 'AAPL')
        timeframe (str): The timeframe for data ('1d', '1h', '15m')
        lookback_days (int): Number of days to look back
    
    Returns:
        pd.DataFrame: Historical data with OHLCV and technical indicators
    """
    try:
        # Check if market is open for intraday data
        if timeframe in ["1h", "15m"] and not is_market_open():
            next_trading_day = get_next_trading_day()
            raise Exception(f"Market is currently closed. Next trading day is {next_trading_day.strftime('%Y-%m-%d')}")
        
        # Map timeframe to yfinance interval and adjust lookback period
        tf_map = {
            "1d": {"interval": "1d", "period": f"{lookback_days}d"},
            "1h": {"interval": "1h", "period": f"{min(lookback_days * 24, 730)}h"},  # Max 730 hours (30 days)
            "15m": {"interval": "15m", "period": f"{min(lookback_days * 96, 60)}d"}  # Max 60 days for 15m
        }
        
        if timeframe not in tf_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}. Supported: {list(tf_map.keys())}")
        
        interval_config = tf_map[timeframe]
        
        # Create ticker object
        ticker = yf.Ticker(symbol)
        
        # Fetch historical data with retry mechanism
        def fetch_history():
            return ticker.history(
                period=interval_config["period"],
                interval=interval_config["interval"],
                prepost=True,
                actions=True,
                auto_adjust=True,
                back_adjust=True,
                repair=True
            )
        
        df = retry_yfinance_request(fetch_history)
        
        if df is None or df.empty:
            raise Exception(f"No data returned for {symbol}")
        
        # Validate data quality
        if len(df) < 10:
            raise Exception(f"Insufficient data for {symbol}: only {len(df)} data points")
        
        # Check for missing values in critical columns
        critical_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_data = df[critical_columns].isnull().sum()
        if missing_data.sum() > len(df) * 0.1:  # More than 10% missing data
            print(f"Warning: Significant missing data for {symbol}: {missing_data.to_dict()}")
        
        # Fill any remaining missing values with forward fill then backward fill
        df = df.fillna(method='ffill').fillna(method='bfill')
        
        # Calculate returns and volatility
        df['Returns'] = df['Close'].pct_change()
        df['Volatility'] = df['Returns'].rolling(window=20).std()
        
        # Calculate technical indicators
        df = calculate_technical_indicators(df)
        
        print(f"Successfully fetched {len(df)} data points for {symbol} ({timeframe})")
        return df
        
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {str(e)}")
        raise

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Relative Strength Index"""
    # Handle None values by forward filling
    prices = prices.ffill().bfill()
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series]:
    """Calculate MACD and Signal line"""
    # Handle None values by forward filling
    prices = prices.ffill().bfill()
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd, signal_line

def calculate_bollinger_bands(prices: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculate Bollinger Bands"""
    # Handle None values by forward filling
    prices = prices.ffill().bfill()
    middle_band = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper_band = middle_band + (std * std_dev)
    lower_band = middle_band - (std * std_dev)
    return upper_band, middle_band, lower_band

def predict_technical_indicators(df: pd.DataFrame, price_prediction: np.ndarray, 
                               timeframe: str = "1d") -> Dict[str, np.ndarray]:
    """
    Predict technical indicators based on price predictions.
    
    Args:
        df (pd.DataFrame): Historical data with technical indicators
        price_prediction (np.ndarray): Predicted prices
        timeframe (str): Data timeframe for scaling
    
    Returns:
        Dict[str, np.ndarray]: Predicted technical indicators
    """
    try:
        predictions = {}
        
        # Get last values for initialization
        last_rsi = df['RSI'].iloc[-1]
        last_macd = df['MACD'].iloc[-1]
        last_macd_signal = df['MACD_Signal'].iloc[-1]
        last_bb_upper = df['BB_Upper'].iloc[-1] if 'BB_Upper' in df.columns else None
        last_bb_middle = df['BB_Middle'].iloc[-1] if 'BB_Middle' in df.columns else None
        last_bb_lower = df['BB_Lower'].iloc[-1] if 'BB_Lower' in df.columns else None
        
        # Predict RSI
        rsi_predictions = []
        for i, pred_price in enumerate(price_prediction):
            # RSI tends to mean-revert, so we use a simple mean reversion model
            if last_rsi > 70:  # Overbought
                rsi_change = -0.5 * (i + 1)  # Gradual decline
            elif last_rsi < 30:  # Oversold
                rsi_change = 0.5 * (i + 1)   # Gradual rise
            else:  # Neutral zone
                rsi_change = 0.1 * np.random.normal(0, 1)  # Small random change
            
            predicted_rsi = max(0, min(100, last_rsi + rsi_change))
            rsi_predictions.append(predicted_rsi)
        
        predictions['RSI'] = np.array(rsi_predictions)
        
        # Predict MACD
        macd_predictions = []
        macd_signal_predictions = []
        
        # MACD follows price momentum
        price_changes = np.diff(price_prediction, prepend=price_prediction[0])
        
        for i, price_change in enumerate(price_changes):
            # MACD change based on price momentum
            macd_change = price_change / price_prediction[i] * 100  # Scale to MACD range
            predicted_macd = last_macd + macd_change * 0.1  # Dampened change
            
            # MACD signal line (slower moving average of MACD)
            signal_change = macd_change * 0.05  # Even slower
            predicted_signal = last_macd_signal + signal_change
            
            macd_predictions.append(predicted_macd)
            macd_signal_predictions.append(predicted_signal)
        
        predictions['MACD'] = np.array(macd_predictions)
        predictions['MACD_Signal'] = np.array(macd_signal_predictions)
        
        # Predict Bollinger Bands if available
        if all(x is not None for x in [last_bb_upper, last_bb_middle, last_bb_lower]):
            bb_upper_predictions = []
            bb_middle_predictions = []
            bb_lower_predictions = []
            
            # Calculate rolling statistics for Bollinger Bands
            window_size = 20
            for i in range(len(price_prediction)):
                if i < window_size:
                    # Use historical data + predictions for calculation
                    window_prices = np.concatenate([df['Close'].values[-window_size+i:], price_prediction[:i+1]])
                else:
                    # Use only predictions
                    window_prices = price_prediction[i-window_size+1:i+1]
                
                # Calculate Bollinger Bands for this window
                window_mean = np.mean(window_prices)
                window_std = np.std(window_prices)
                
                bb_middle = window_mean
                bb_upper = window_mean + (window_std * 2)
                bb_lower = window_mean - (window_std * 2)
                
                bb_upper_predictions.append(bb_upper)
                bb_middle_predictions.append(bb_middle)
                bb_lower_predictions.append(bb_lower)
            
            predictions['BB_Upper'] = np.array(bb_upper_predictions)
            predictions['BB_Middle'] = np.array(bb_middle_predictions)
            predictions['BB_Lower'] = np.array(bb_lower_predictions)
        
        # Predict moving averages
        sma_predictions = {}
        for period in [20, 50, 200]:
            if f'SMA_{period}' in df.columns:
                last_sma = df[f'SMA_{period}'].iloc[-1]
                sma_predictions[f'SMA_{period}'] = []
                
                for i in range(len(price_prediction)):
                    # Simple moving average prediction
                    if i < period:
                        # Use historical data + predictions
                        window_prices = np.concatenate([df['Close'].values[-period+i+1:], price_prediction[:i+1]])
                    else:
                        # Use only predictions
                        window_prices = price_prediction[i-period+1:i+1]
                    
                    predicted_sma = np.mean(window_prices)
                    sma_predictions[f'SMA_{period}'].append(predicted_sma)
                
                predictions[f'SMA_{period}'] = np.array(sma_predictions[f'SMA_{period}'])
        
        return predictions
        
    except Exception as e:
        print(f"Error predicting technical indicators: {str(e)}")
        # Return empty predictions on error
        return {}

def calculate_technical_uncertainty(df: pd.DataFrame, indicator_predictions: Dict[str, np.ndarray], 
                                  price_prediction: np.ndarray) -> Dict[str, np.ndarray]:
    """
    Calculate uncertainty for technical indicator predictions.
    
    Args:
        df (pd.DataFrame): Historical data
        indicator_predictions (Dict[str, np.ndarray]): Predicted indicators
        price_prediction (np.ndarray): Predicted prices
    
    Returns:
        Dict[str, np.ndarray]: Uncertainty estimates for each indicator
    """
    try:
        uncertainties = {}
        
        # Calculate historical volatility of each indicator
        for indicator_name, predictions in indicator_predictions.items():
            if indicator_name in df.columns:
                # Calculate historical volatility
                historical_values = df[indicator_name].dropna()
                if len(historical_values) > 10:
                    volatility = historical_values.std()
                    
                    # Scale uncertainty by prediction horizon
                    indicator_uncertainty = []
                    for i in range(len(predictions)):
                        # Uncertainty increases with prediction horizon
                        uncertainty = volatility * np.sqrt(i + 1)
                        indicator_uncertainty.append(uncertainty)
                    
                    uncertainties[indicator_name] = np.array(indicator_uncertainty)
                else:
                    # Use a default uncertainty if insufficient data
                    uncertainties[indicator_name] = np.array([0.1 * abs(predictions[0])] * len(predictions))
            else:
                # For new indicators, use a percentage of the prediction value
                uncertainties[indicator_name] = np.array([0.05 * abs(pred) for pred in predictions])
        
        return uncertainties
        
    except Exception as e:
        print(f"Error calculating technical uncertainty: {str(e)}")
        return {}

@spaces.GPU()
def make_prediction_enhanced(symbol: str, timeframe: str = "1d", prediction_days: int = 5, strategy: str = "chronos",
                           use_ensemble: bool = True, use_regime_detection: bool = True, use_stress_testing: bool = True,
                           risk_free_rate: float = 0.02, ensemble_weights: Dict = None, 
                           market_index: str = "^GSPC", use_covariates: bool = True, use_sentiment: bool = True,
                           random_real_points: int = 4, use_smoothing: bool = True, 
                           smoothing_type: str = "exponential", smoothing_window: int = 5, 
                           smoothing_alpha: float = 0.3) -> Tuple[Dict, go.Figure]:
    """
    Enhanced prediction using Chronos with covariate data, advanced uncertainty calculations, and improved algorithms.
    
    Args:
        symbol (str): Stock symbol
        timeframe (str): Data timeframe ('1d', '1h', '15m')
        prediction_days (int): Number of days to predict
        strategy (str): Prediction strategy to use
        use_ensemble (bool): Whether to use ensemble methods
        use_regime_detection (bool): Whether to use regime detection
        use_stress_testing (bool): Whether to perform stress testing
        risk_free_rate (float): Risk-free rate for calculations
        ensemble_weights (Dict): Weights for ensemble models
        market_index (str): Market index for correlation analysis
        use_covariates (bool): Whether to use covariate data
        use_sentiment (bool): Whether to use sentiment analysis
        random_real_points (int): Number of random real points to include in long-horizon context
        use_smoothing (bool): Whether to apply smoothing to predictions
        smoothing_type (str): Type of smoothing to apply ('exponential', 'moving_average', 'kalman', 'savitzky_golay', 'none')
    
    Returns:
        Tuple[Dict, go.Figure]: Trading signals and visualization plot
    """
    try:
        # Get historical data
        df = get_historical_data(symbol, timeframe)
        
        # Initialize variables that might not be set in all strategy paths
        advanced_uncertainties = {}
        volume_pred = None
        volume_uncertainty = None
        technical_predictions = {}
        technical_uncertainties = {}
        
        # Collect enhanced covariate data
        covariate_data = {}
        market_conditions = {}
        if use_covariates:
            print("Collecting enhanced covariate data...")
            covariate_data = get_enhanced_covariate_data(symbol, timeframe, 365)
            
            # Extract market conditions from covariate data
            if 'economic_indicators' in covariate_data:
                vix_data = covariate_data['economic_indicators'].get('volatility', None)
                if vix_data is not None and len(vix_data) > 0:
                    market_conditions['vix'] = vix_data.iloc[-1]
        
        # Calculate market sentiment
        sentiment_data = {}
        if use_sentiment:
            print("Calculating market sentiment...")
            sentiment_data = calculate_market_sentiment(symbol, 30)
        
        # Detect market regime
        regime_info = {}
        if use_regime_detection:
            print("Detecting market regime...")
            returns = df['Close'].pct_change().dropna()
            regime_info = detect_market_regime(returns)
        
        if strategy == "chronos":
            try:
                # Prepare data for Chronos
                prices = df['Close'].values
                chronos_context_size = 64  # Chronos model's context window size (fixed at 64)
                input_context_size = len(prices)  # Available input data can be much larger
                
                # Use a larger range for scaler fitting to get better normalization
                scaler_range = min(input_context_size, chronos_context_size * 2)  # Use up to 128 points for scaler
                
                # Select the most recent chronos_context_size points for the model input
                context_window = prices[-chronos_context_size:]
                
                scaler = MinMaxScaler(feature_range=(-1, 1))
                # Fit scaler on a larger range for better normalization
                scaler.fit(prices[-scaler_range:].reshape(-1, 1))
                normalized_prices = scaler.transform(context_window.reshape(-1, 1)).flatten()
                
                # Ensure we have enough data points for Chronos
                min_data_points = chronos_context_size
                if len(normalized_prices) < min_data_points:
                    padding = np.full(min_data_points - len(normalized_prices), normalized_prices[-1])
                    normalized_prices = np.concatenate([padding, normalized_prices])
                elif len(normalized_prices) > min_data_points:
                    normalized_prices = normalized_prices[-min_data_points:]
                
                # Load pipeline and move to GPU
                pipe = load_pipeline()
                
                # Get the model's device and dtype
                device = torch.device("cuda:0")  # Force CUDA device mapping
                dtype = torch.float16  # Force float16
                print(f"Model device: {device}")
                print(f"Model dtype: {dtype}")
                
                # Convert to tensor and ensure proper shape and device
                context = torch.tensor(normalized_prices, dtype=dtype, device=device)
                
                # Validate context data
                if torch.isnan(context).any() or torch.isinf(context).any():
                    print("Warning: Context contains NaN or Inf values, replacing with zeros")
                    context = torch.nan_to_num(context, nan=0.0, posinf=0.0, neginf=0.0)
                
                # Ensure context is finite and reasonable
                if torch.abs(context).max() > 1000:
                    print("Warning: Context values are very large, normalizing")
                    context = torch.clamp(context, -1000, 1000)
                
                print(f"Context validation - Shape: {context.shape}, Min: {context.min():.4f}, Max: {context.max():.4f}, Mean: {context.mean():.4f}")
                
                # Adjust prediction length based on timeframe
                if timeframe == "1d":
                    max_prediction_length = chronos_context_size  # 64 days
                    actual_prediction_length = min(prediction_days, max_prediction_length)
                    trim_length = prediction_days
                elif timeframe == "1h":
                    max_prediction_length = chronos_context_size  # 64 hours
                    actual_prediction_length = min(prediction_days * 24, max_prediction_length)
                    trim_length = prediction_days * 24
                else:  # 15m
                    max_prediction_length = chronos_context_size  # 64 intervals
                    actual_prediction_length = min(prediction_days * 96, max_prediction_length)
                    trim_length = prediction_days * 96
                
                # Ensure prediction length is valid (must be positive and reasonable)
                actual_prediction_length = max(1, min(actual_prediction_length, 64))
                
                print(f"Prediction length: {actual_prediction_length}")
                print(f"Context length: {len(context)}")
                
                # Use predict_quantiles with proper formatting
                with torch.amp.autocast('cuda'):
                    # Ensure all inputs are on GPU
                    context = context.to(device)
                    
                    # Ensure context is properly shaped and on GPU
                    if len(context.shape) == 1:
                        context = context.unsqueeze(0)
                    context = context.to(device)
                    
                    # Force all model components to GPU
                    pipe.model = pipe.model.to(device)
                    
                    # Move model to evaluation mode
                    pipe.model.eval()
                    
                    # Move all model parameters and buffers to GPU
                    for param in pipe.model.parameters():
                        param.data = param.data.to(device)
                    for buffer in pipe.model.buffers():
                        buffer.data = buffer.data.to(device)
                    
                    # Move all model submodules to GPU
                    for module in pipe.model.modules():
                        if hasattr(module, 'to'):
                            module.to(device)
                    
                    # Move all model attributes to GPU
                    for name, value in pipe.model.__dict__.items():
                        if isinstance(value, torch.Tensor):
                            pipe.model.__dict__[name] = value.to(device)
                    
                    # Move all model config tensors to GPU
                    if hasattr(pipe.model, 'config'):
                        for key, value in pipe.model.config.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                setattr(pipe.model.config, key, value.to(device))
                    
                    # Move all pipeline tensors to GPU
                    for name, value in pipe.__dict__.items():
                        if isinstance(value, torch.Tensor):
                            setattr(pipe, name, value.to(device))
                    
                    # Ensure all model states are on GPU
                    if hasattr(pipe.model, 'state_dict'):
                        state_dict = pipe.model.state_dict()
                        for key in state_dict:
                            if isinstance(state_dict[key], torch.Tensor):
                                state_dict[key] = state_dict[key].to(device)
                        pipe.model.load_state_dict(state_dict)
                    
                    # Move any additional components to GPU
                    if hasattr(pipe, 'tokenizer'):
                        # Move tokenizer to GPU if it supports it
                        if hasattr(pipe.tokenizer, 'to'):
                            pipe.tokenizer = pipe.tokenizer.to(device)
                        
                        # Move all tokenizer tensors to GPU
                        for name, value in pipe.tokenizer.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                setattr(pipe.tokenizer, name, value.to(device))
                        
                        # Handle MeanScaleUniformBins specific attributes
                        if hasattr(pipe.tokenizer, 'bins'):
                            if isinstance(pipe.tokenizer.bins, torch.Tensor):
                                pipe.tokenizer.bins = pipe.tokenizer.bins.to(device)
                        
                        if hasattr(pipe.tokenizer, 'scale'):
                            if isinstance(pipe.tokenizer.scale, torch.Tensor):
                                pipe.tokenizer.scale = pipe.tokenizer.scale.to(device)
                        
                        if hasattr(pipe.tokenizer, 'mean'):
                            if isinstance(pipe.tokenizer.mean, torch.Tensor):
                                pipe.tokenizer.mean = pipe.tokenizer.mean.to(device)
                        
                        # Move any additional tensors in the tokenizer's attributes to GPU
                        for name, value in pipe.tokenizer.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                pipe.tokenizer.__dict__[name] = value.to(device)
                        
                        # Remove the EOS token handling since MeanScaleUniformBins doesn't use it
                        if hasattr(pipe.tokenizer, '_append_eos_token'):
                            # Create a wrapper that just returns the input tensors
                            def wrapped_append_eos(token_ids, attention_mask):
                                return token_ids, attention_mask
                            pipe.tokenizer._append_eos_token = wrapped_append_eos
                    
                    # Force synchronization again to ensure all tensors are on GPU
                    torch.cuda.synchronize()
                    
                    # Ensure all model components are in eval mode
                    pipe.model.eval()
                    
                    # Fix generation configuration to prevent min_length errors
                    if hasattr(pipe.model, 'config'):
                        # Ensure generation config is properly set
                        if hasattr(pipe.model.config, 'generation_config'):
                            # Reset generation config to safe defaults
                            pipe.model.config.generation_config.min_length = 0
                            pipe.model.config.generation_config.max_length = 512
                            pipe.model.config.generation_config.do_sample = False
                            pipe.model.config.generation_config.num_beams = 1
                        else:
                            # Create a safe generation config if it doesn't exist
                            pipe.model.config.generation_config = GenerationConfig(
                                min_length=0,
                                max_length=512,
                                do_sample=False,
                                num_beams=1
                            )
                    
                    # Move any additional tensors in the model's config to GPU
                    if hasattr(pipe.model, 'config'):
                        for key, value in pipe.model.config.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                setattr(pipe.model.config, key, value.to(device))
                    
                    # Move any additional tensors in the model's state dict to GPU
                    if hasattr(pipe.model, 'state_dict'):
                        state_dict = pipe.model.state_dict()
                        for key in state_dict:
                            if isinstance(state_dict[key], torch.Tensor):
                                state_dict[key] = state_dict[key].to(device)
                        pipe.model.load_state_dict(state_dict)
                    
                    # Move any additional tensors in the model's buffers to GPU
                    for name, buffer in pipe.model.named_buffers():
                        if buffer is not None:
                            pipe.model.register_buffer(name, buffer.to(device))
                    
                    # Move any additional tensors in the model's parameters to GPU
                    for name, param in pipe.model.named_parameters():
                        if param is not None:
                            param.data = param.data.to(device)
                    
                    # Move any additional tensors in the model's attributes to GPU
                    for name, value in pipe.model.__dict__.items():
                        if isinstance(value, torch.Tensor):
                            pipe.model.__dict__[name] = value.to(device)
                    
                    # Move any additional tensors in the model's modules to GPU
                    for name, module in pipe.model.named_modules():
                        if hasattr(module, 'to'):
                            module.to(device)
                        # Move any tensors in the module's __dict__
                        for key, value in module.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                setattr(module, key, value.to(device))
                    
                    # Force synchronization again to ensure all tensors are on GPU
                    torch.cuda.synchronize()
                    
                    # Ensure tokenizer is on GPU and all its tensors are on GPU
                    if hasattr(pipe, 'tokenizer'):
                        # Move tokenizer to GPU if it supports it
                        if hasattr(pipe.tokenizer, 'to'):
                            pipe.tokenizer = pipe.tokenizer.to(device)
                        
                        # Move all tokenizer tensors to GPU
                        for name, value in pipe.tokenizer.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                setattr(pipe.tokenizer, name, value.to(device))
                        
                        # Handle MeanScaleUniformBins specific attributes
                        if hasattr(pipe.tokenizer, 'bins'):
                            if isinstance(pipe.tokenizer.bins, torch.Tensor):
                                pipe.tokenizer.bins = pipe.tokenizer.bins.to(device)
                        
                        if hasattr(pipe.tokenizer, 'scale'):
                            if isinstance(pipe.tokenizer.scale, torch.Tensor):
                                pipe.tokenizer.scale = pipe.tokenizer.scale.to(device)
                        
                        if hasattr(pipe.tokenizer, 'mean'):
                            if isinstance(pipe.tokenizer.mean, torch.Tensor):
                                pipe.tokenizer.mean = pipe.tokenizer.mean.to(device)
                        
                        # Move any additional tensors in the tokenizer's attributes to GPU
                        for name, value in pipe.tokenizer.__dict__.items():
                            if isinstance(value, torch.Tensor):
                                pipe.tokenizer.__dict__[name] = value.to(device)
                    
                    # Force synchronization again to ensure all tensors are on GPU
                    torch.cuda.synchronize()
                    
                    # Make prediction with proper parameters
                    # Use the standard quantile levels as per Chronos documentation
                    try:
                        quantiles, mean = pipe.predict_quantiles(
                            context=context,
                            prediction_length=actual_prediction_length,
                            quantile_levels=[0.1, 0.5, 0.9]
                        )
                    except Exception as prediction_error:
                        print(f"Chronos prediction failed: {str(prediction_error)}")
                        print(f"Context shape: {context.shape}")
                        print(f"Context dtype: {context.dtype}")
                        print(f"Context device: {context.device}")
                        print(f"Prediction length: {actual_prediction_length}")
                        print(f"Model device: {next(pipe.model.parameters()).device}")
                        print(f"Model dtype: {next(pipe.model.parameters()).dtype}")
                        
                        # Try with a smaller prediction length as fallback
                        if actual_prediction_length > 1:
                            print(f"Retrying with prediction length 1...")
                            actual_prediction_length = 1
                            quantiles, mean = pipe.predict_quantiles(
                                context=context,
                                prediction_length=actual_prediction_length,
                                quantile_levels=[0.1, 0.5, 0.9]
                            )
                        else:
                            raise prediction_error
                
                if quantiles is None or mean is None or len(quantiles) == 0 or len(mean) == 0:
                    raise ValueError("Chronos returned empty prediction")
                
                print(f"Quantiles shape: {quantiles.shape}, Mean shape: {mean.shape}")
                
                # Convert to numpy arrays
                quantiles = quantiles.detach().cpu().numpy()
                mean = mean.detach().cpu().numpy()
                
                # Denormalize predictions using the same scaler as context
                mean_pred = scaler.inverse_transform(mean.reshape(-1, 1)).flatten()
                lower_bound = scaler.inverse_transform(quantiles[0, :, 0].reshape(-1, 1)).flatten()
                upper_bound = scaler.inverse_transform(quantiles[0, :, 2].reshape(-1, 1)).flatten()
                
                # Calculate uncertainty using advanced methods
                historical_volatility = df['Volatility'].iloc[-1]
                advanced_uncertainties = calculate_advanced_uncertainty(
                    quantiles, historical_volatility, market_conditions
                )
                std_pred = advanced_uncertainties.get('ensemble', 
                    (upper_bound - lower_bound) / (2 * 1.645))
                
                # Apply continuity correction
                last_actual = df['Close'].iloc[-1]
                first_pred = mean_pred[0]
                discontinuity_threshold = max(1e-6, 0.02 * abs(last_actual))  # 2% threshold
                
                if abs(first_pred - last_actual) > discontinuity_threshold:
                    print(f"Warning: Discontinuity detected between last actual ({last_actual:.4f}) and first prediction ({first_pred:.4f})")
                    print(f"Discontinuity magnitude: {abs(first_pred - last_actual):.4f} ({abs(first_pred - last_actual)/last_actual*100:.2f}%)")
                    
                    # Apply improved continuity correction
                    if len(mean_pred) > 1:
                        # Calculate the overall trend from the original predictions
                        original_trend = mean_pred[-1] - first_pred
                        total_steps = len(mean_pred) - 1
                        
                        # Calculate the desired trend per step to reach the final prediction
                        if total_steps > 0:
                            trend_per_step = original_trend / total_steps
                        else:
                            trend_per_step = 0
                        
                        # Apply smooth transition starting from last actual
                        # Use a gradual transition that preserves the overall trend
                        transition_length = min(5, len(mean_pred))  # Longer transition for smoother curve
                        
                        for i in range(transition_length):
                            if i == 0:
                                # First prediction should be very close to last actual
                                mean_pred[i] = last_actual + trend_per_step * 0.1
                            else:
                                # Gradually increase the trend contribution
                                transition_factor = min(1.0, i / transition_length)
                                trend_contribution = trend_per_step * i * transition_factor
                                mean_pred[i] = last_actual + trend_contribution
                        
                        # For remaining predictions, maintain the original relative differences
                        if len(mean_pred) > transition_length:
                            # Calculate the scale factor to maintain relative relationships
                            original_diff = mean_pred[transition_length] - mean_pred[transition_length-1]
                            if original_diff != 0:
                                # Scale the remaining predictions to maintain continuity
                                for i in range(transition_length, len(mean_pred)):
                                    if i == transition_length:
                                        # Ensure smooth transition at the boundary
                                        mean_pred[i] = mean_pred[i-1] + original_diff * 0.5
                                    else:
                                        # Maintain the original relative differences
                                        original_diff_i = mean_pred[i] - mean_pred[i-1]
                                        mean_pred[i] = mean_pred[i-1] + original_diff_i
                        
                        print(f"Applied continuity correction: First prediction adjusted from {first_pred:.4f} to {mean_pred[0]:.4f}")
                        
                        # Apply financial smoothing if enabled
                        if use_smoothing:
                            mean_pred = apply_financial_smoothing(mean_pred, smoothing_type, smoothing_window, smoothing_alpha, 3, use_smoothing)
                    else:
                        # Single prediction case - set to last actual
                        mean_pred[0] = last_actual
                        print(f"Single prediction case: Set to last actual value {last_actual:.4f}")
                
                # If we had to limit the prediction length, extend the prediction recursively
                if actual_prediction_length < trim_length:
                    extended_mean_pred = mean_pred.copy()
                    extended_std_pred = std_pred.copy()
                    
                    # Store the original scaler for consistency
                    original_scaler = scaler
                    
                    # Calculate the number of extension steps needed
                    remaining_steps = trim_length - actual_prediction_length
                    steps_needed = (remaining_steps + actual_prediction_length - 1) // actual_prediction_length
                    
                    for step in range(steps_needed):
                        # Use all available datapoints for context, including predictions
                        # This allows the model to build upon its own predictions for better long-horizon forecasting
                        all_available_data = np.concatenate([prices, extended_mean_pred])
                        
                        # If we have more data than chronos_context_size, use the most recent chronos_context_size points
                        # Otherwise, use all available data (this allows for longer context when available)
                        if len(all_available_data) > chronos_context_size:
                            context_window = all_available_data[-chronos_context_size:]
                        else:
                            context_window = all_available_data
                        
                        # Use the original scaler to maintain consistency - fit on historical data only
                        # but transform the combined context window
                        normalized_context = original_scaler.transform(context_window.reshape(-1, 1)).flatten()
                        context = torch.tensor(normalized_context, dtype=dtype, device=device)
                        if len(context.shape) == 1:
                            context = context.unsqueeze(0)
                        
                        next_length = min(max_prediction_length, remaining_steps)
                        # Ensure next_length is valid (must be positive and reasonable)
                        next_length = max(1, min(next_length, 64))
                        
                        with torch.amp.autocast('cuda'):
                            try:
                                next_quantiles, next_mean = pipe.predict_quantiles(
                                    context=context,
                                    prediction_length=next_length,
                                    quantile_levels=[0.1, 0.5, 0.9]
                                )
                            except Exception as extension_error:
                                print(f"Chronos extension prediction failed: {str(extension_error)}")
                                print(f"Extension context shape: {context.shape}")
                                print(f"Extension prediction length: {next_length}")
                                
                                # Try with a smaller prediction length as fallback
                                if next_length > 1:
                                    print(f"Retrying extension with prediction length 1...")
                                    next_length = 1
                                    next_quantiles, next_mean = pipe.predict_quantiles(
                                        context=context,
                                        prediction_length=next_length,
                                        quantile_levels=[0.1, 0.5, 0.9]
                                    )
                                else:
                                    raise extension_error
                        
                        # Convert predictions to numpy and denormalize using original scaler
                        next_mean = next_mean.detach().cpu().numpy()
                        next_quantiles = next_quantiles.detach().cpu().numpy()
                        
                        # Denormalize predictions using the original scaler
                        next_mean_pred = original_scaler.inverse_transform(next_mean.reshape(-1, 1)).flatten()
                        
                        # Calculate uncertainty for extended predictions
                        next_uncertainties = calculate_advanced_uncertainty(
                            next_quantiles, historical_volatility, market_conditions
                        )
                        next_std_pred = next_uncertainties.get('ensemble', 
                            (next_quantiles[0, :, 2] - next_quantiles[0, :, 0]) / (2 * 1.645))
                        
                        # Check for discontinuity and apply continuity correction
                        if abs(next_mean_pred[0] - extended_mean_pred[-1]) > max(1e-6, 0.02 * abs(extended_mean_pred[-1])):
                            print(f"Warning: Discontinuity detected between last prediction ({extended_mean_pred[-1]:.4f}) and next prediction ({next_mean_pred[0]:.4f})")
                            print(f"Extension discontinuity magnitude: {abs(next_mean_pred[0] - extended_mean_pred[-1]):.4f}")
                            
                            # Apply improved continuity correction for extensions
                            if len(next_mean_pred) > 1:
                                # Calculate the overall trend from the original predictions
                                original_trend = next_mean_pred[-1] - next_mean_pred[0]
                                total_steps = len(next_mean_pred) - 1
                                
                                # Calculate the desired trend per step
                                if total_steps > 0:
                                    trend_per_step = original_trend / total_steps
                                else:
                                    trend_per_step = 0
                                
                                # Apply smooth transition starting from last extended prediction
                                transition_length = min(5, len(next_mean_pred))  # Longer transition for smoother curve
                                
                                for i in range(transition_length):
                                    if i == 0:
                                        # First prediction should be very close to last extended prediction
                                        next_mean_pred[i] = extended_mean_pred[-1] + trend_per_step * 0.1
                                    else:
                                        # Gradually increase the trend contribution
                                        transition_factor = min(1.0, i / transition_length)
                                        trend_contribution = trend_per_step * i * transition_factor
                                        next_mean_pred[i] = extended_mean_pred[-1] + trend_contribution
                                
                                # For remaining predictions, maintain the original relative differences
                                if len(next_mean_pred) > transition_length:
                                    # Calculate the scale factor to maintain relative relationships
                                    original_diff = next_mean_pred[transition_length] - next_mean_pred[transition_length-1]
                                    if original_diff != 0:
                                        # Scale the remaining predictions to maintain continuity
                                        for i in range(transition_length, len(next_mean_pred)):
                                            if i == transition_length:
                                                # Ensure smooth transition at the boundary
                                                next_mean_pred[i] = next_mean_pred[i-1] + original_diff * 0.5
                                            else:
                                                # Maintain the original relative differences
                                                original_diff_i = next_mean_pred[i] - next_mean_pred[i-1]
                                                next_mean_pred[i] = next_mean_pred[i-1] + original_diff_i
                                
                                print(f"Applied extension continuity correction: First extension prediction adjusted from {next_mean_pred[0]:.4f} to {next_mean_pred[0]:.4f}")
                            else:
                                # Single prediction case - set to last extended prediction
                                next_mean_pred[0] = extended_mean_pred[-1]
                                print(f"Single extension prediction case: Set to last extended prediction value {extended_mean_pred[-1]:.4f}")
                        
                        # Apply financial smoothing if enabled
                        if use_smoothing and len(next_mean_pred) > 1:
                            next_mean_pred = apply_financial_smoothing(next_mean_pred, smoothing_type, smoothing_window, smoothing_alpha, 3, use_smoothing)
                        
                        # Append predictions
                        extended_mean_pred = np.concatenate([extended_mean_pred, next_mean_pred])
                        extended_std_pred = np.concatenate([extended_std_pred, next_std_pred])
                        remaining_steps -= len(next_mean_pred)
                        if remaining_steps <= 0:
                            break
                    
                    # Trim to exact prediction length if needed
                    mean_pred = extended_mean_pred[:trim_length]
                    std_pred = extended_std_pred[:trim_length]
                
                # Enhanced volume prediction
                volume_pred, volume_uncertainty = calculate_volume_prediction_enhanced(
                    df, mean_pred, covariate_data
                )
                
                # Ensure volume prediction is properly handled
                if volume_pred is None or len(volume_pred) == 0:
                    print("Warning: Volume prediction failed, using fallback")
                    volume_pred = np.full(len(mean_pred), df['Volume'].iloc[-1])
                    volume_uncertainty = np.full(len(mean_pred), df['Volume'].iloc[-1] * 0.2)
                elif len(volume_pred) != len(mean_pred):
                    print(f"Warning: Volume prediction length mismatch. Expected {len(mean_pred)}, got {len(volume_pred)}")
                    # Pad or truncate to match
                    if len(volume_pred) < len(mean_pred):
                        last_vol = volume_pred[-1] if len(volume_pred) > 0 else df['Volume'].iloc[-1]
                        volume_pred = np.pad(volume_pred, (0, len(mean_pred) - len(volume_pred)), 
                                           mode='constant', constant_values=last_vol)
                        volume_uncertainty = np.pad(volume_uncertainty, (0, len(mean_pred) - len(volume_uncertainty)), 
                                                  mode='constant', constant_values=volume_uncertainty[-1] if len(volume_uncertainty) > 0 else df['Volume'].iloc[-1] * 0.2)
                    else:
                        volume_pred = volume_pred[:len(mean_pred)]
                        volume_uncertainty = volume_uncertainty[:len(mean_pred)]
                
                # Predict technical indicators
                print("Predicting technical indicators...")
                technical_predictions = predict_technical_indicators(df, mean_pred, timeframe)
                technical_uncertainties = calculate_technical_uncertainty(df, technical_predictions, mean_pred)
                
                # Create ensemble prediction if enabled
                ensemble_pred = np.array([])
                ensemble_uncertainty = np.array([])
                if use_ensemble and covariate_data:
                    print("Creating enhanced ensemble model...")
                    ensemble_pred, ensemble_uncertainty = create_enhanced_ensemble_model(
                        df, covariate_data, trim_length
                    )
                
                # Combine Chronos and ensemble predictions
                if len(ensemble_pred) > 0:
                    # Weighted combination
                    chronos_weight = 0.7
                    ensemble_weight = 0.3
                    final_pred = chronos_weight * mean_pred + ensemble_weight * ensemble_pred
                    final_uncertainty = np.sqrt(
                        (chronos_weight * std_pred)**2 + (ensemble_weight * ensemble_uncertainty)**2
                    )
                else:
                    final_pred = mean_pred
                    final_uncertainty = std_pred
                
                # Final continuity validation and correction
                print("Performing final continuity validation...")
                last_actual = df['Close'].iloc[-1]
                first_pred = final_pred[0]
                discontinuity_threshold = max(1e-6, 0.01 * abs(last_actual))  # Stricter 1% threshold for final check
                
                if abs(first_pred - last_actual) > discontinuity_threshold:
                    print(f"Final check: Discontinuity detected between last actual ({last_actual:.4f}) and first prediction ({first_pred:.4f})")
                    print(f"Final discontinuity magnitude: {abs(first_pred - last_actual):.4f} ({abs(first_pred - last_actual)/last_actual*100:.2f}%)")
                    
                    # Apply final continuity correction
                    if len(final_pred) > 1:
                        # Calculate the overall trend
                        overall_trend = final_pred[-1] - first_pred
                        total_steps = len(final_pred) - 1
                        
                        if total_steps > 0:
                            trend_per_step = overall_trend / total_steps
                        else:
                            trend_per_step = 0
                        
                        # Apply very smooth transition
                        transition_length = min(8, len(final_pred))  # Longer transition for final correction
                        
                        for i in range(transition_length):
                            if i == 0:
                                # First prediction should be extremely close to last actual
                                final_pred[i] = last_actual + trend_per_step * 0.05
                            else:
                                # Very gradual transition
                                transition_factor = min(1.0, (i / transition_length) ** 2)  # Quadratic easing
                                trend_contribution = trend_per_step * i * transition_factor
                                final_pred[i] = last_actual + trend_contribution
                        
                        # Maintain relative relationships for remaining predictions
                        if len(final_pred) > transition_length:
                            for i in range(transition_length, len(final_pred)):
                                if i == transition_length:
                                    # Smooth transition at boundary
                                    final_pred[i] = final_pred[i-1] + trend_per_step * 0.8
                                else:
                                    # Maintain original relative differences
                                    original_diff = final_pred[i] - final_pred[i-1]
                                    final_pred[i] = final_pred[i-1] + original_diff * 0.9  # Slightly dampened
                        
                        print(f"Final continuity correction applied: First prediction adjusted from {first_pred:.4f} to {final_pred[0]:.4f}")
                        
                        # Apply additional smoothing for final correction
                        if use_smoothing:
                            final_pred = apply_financial_smoothing(final_pred, smoothing_type, smoothing_window, smoothing_alpha * 0.5, 3, use_smoothing)
                    else:
                        # Single prediction case
                        final_pred[0] = last_actual
                        print(f"Final single prediction correction: Set to last actual value {last_actual:.4f}")
                
                # Verify final continuity
                final_first_pred = final_pred[0]
                final_discontinuity = abs(final_first_pred - last_actual) / last_actual * 100
                print(f"Final continuity check: Discontinuity = {final_discontinuity:.3f}% (threshold: 1.0%)")
                
                if final_discontinuity <= 1.0:
                    print("✓ Continuity validation passed - predictions are smooth")
                else:
                    print(f"⚠ Continuity validation warning - discontinuity of {final_discontinuity:.3f}% remains")
                
            except Exception as e:
                print(f"Chronos prediction error: {str(e)}")
                raise
        
        elif strategy == "technical":
            # Technical analysis fallback strategy
            print("Using technical analysis strategy...")
            try:
                # Use the same MinMaxScaler for consistency
                prices = df['Close'].values
                scaler = MinMaxScaler(feature_range=(-1, 1))
                scaler.fit(prices.reshape(-1, 1))
                
                # Calculate technical indicators for prediction
                last_price = df['Close'].iloc[-1]
                last_rsi = df['RSI'].iloc[-1]
                last_macd = df['MACD'].iloc[-1]
                last_macd_signal = df['MACD_Signal'].iloc[-1]
                last_volatility = df['Volatility'].iloc[-1]
                
                # Get trend direction from technical indicators
                rsi_trend = 1 if last_rsi > 50 else -1
                macd_trend = 1 if last_macd > last_macd_signal else -1
                
                # Calculate momentum and mean reversion factors
                sma_20 = df['SMA_20'].iloc[-1] if 'SMA_20' in df.columns else last_price
                sma_50 = df['SMA_50'].iloc[-1] if 'SMA_50' in df.columns else last_price
                sma_200 = df['SMA_200'].iloc[-1] if 'SMA_200' in df.columns else last_price
                
                # Mean reversion factor (distance from long-term average)
                mean_reversion = (sma_200 - last_price) / last_price
                
                # Momentum factor (short vs long-term trend)
                momentum = (sma_20 - sma_50) / sma_50
                
                # Combine technical signals
                technical_score = (rsi_trend * 0.3 + macd_trend * 0.3 + 
                                 np.sign(momentum) * 0.2 + np.sign(mean_reversion) * 0.2)
                
                # Generate price predictions
                final_pred = []
                final_uncertainty = []
                
                for i in range(1, prediction_days + 1):
                    # Base prediction with trend and mean reversion
                    trend_factor = technical_score * last_volatility * 0.5
                    mean_reversion_factor = mean_reversion * 0.1 * i
                    momentum_factor = momentum * 0.05 * i
                    
                    # Combine factors with decay
                    prediction = last_price * (1 + trend_factor + mean_reversion_factor + momentum_factor)
                    final_pred.append(prediction)
                    
                    # Uncertainty based on volatility and prediction horizon
                    uncertainty = last_volatility * last_price * np.sqrt(i)
                    final_uncertainty.append(uncertainty)
                
                final_pred = np.array(final_pred)
                final_uncertainty = np.array(final_uncertainty)
                
                # Apply smoothing if enabled
                if use_smoothing:
                    final_pred = apply_financial_smoothing(final_pred, smoothing_type, smoothing_window, smoothing_alpha, 3, use_smoothing)
                
                # Enhanced volume prediction
                volume_pred, volume_uncertainty = calculate_volume_prediction_enhanced(
                    df, final_pred, covariate_data
                )
                
                # Ensure volume prediction is properly handled
                if volume_pred is None or len(volume_pred) == 0:
                    print("Warning: Volume prediction failed, using fallback")
                    volume_pred = np.full(len(final_pred), df['Volume'].iloc[-1])
                    volume_uncertainty = np.full(len(final_pred), df['Volume'].iloc[-1] * 0.2)
                elif len(volume_pred) != len(final_pred):
                    print(f"Warning: Volume prediction length mismatch. Expected {len(final_pred)}, got {len(volume_pred)}")
                    # Pad or truncate to match
                    if len(volume_pred) < len(final_pred):
                        last_vol = volume_pred[-1] if len(volume_pred) > 0 else df['Volume'].iloc[-1]
                        volume_pred = np.pad(volume_pred, (0, len(final_pred) - len(volume_pred)), 
                                           mode='constant', constant_values=last_vol)
                        volume_uncertainty = np.pad(volume_uncertainty, (0, len(final_pred) - len(volume_uncertainty)), 
                                                  mode='constant', constant_values=volume_uncertainty[-1] if len(volume_uncertainty) > 0 else df['Volume'].iloc[-1] * 0.2)
                    else:
                        volume_pred = volume_pred[:len(final_pred)]
                        volume_uncertainty = volume_uncertainty[:len(final_pred)]
                
                # Predict technical indicators
                print("Predicting technical indicators for technical strategy...")
                technical_predictions = predict_technical_indicators(df, final_pred, timeframe)
                technical_uncertainties = calculate_technical_uncertainty(df, technical_predictions, final_pred)
                
                # Create ensemble prediction if enabled
                ensemble_pred = np.array([])
                ensemble_uncertainty = np.array([])
                if use_ensemble and covariate_data:
                    print("Creating enhanced ensemble model for technical strategy...")
                    ensemble_pred, ensemble_uncertainty = create_enhanced_ensemble_model(
                        df, covariate_data, prediction_days
                    )
                
                # Combine technical and ensemble predictions
                if len(ensemble_pred) > 0:
                    technical_weight = 0.7
                    ensemble_weight = 0.3
                    final_pred = technical_weight * final_pred + ensemble_weight * ensemble_pred
                    final_uncertainty = np.sqrt(
                        (technical_weight * final_uncertainty)**2 + (ensemble_weight * ensemble_uncertainty)**2
                    )
                
                # Calculate advanced uncertainties for technical strategy
                historical_volatility = df['Volatility'].iloc[-1]
                # Create dummy quantiles for technical strategy (since we don't have quantiles from Chronos)
                dummy_quantiles = np.array([[
                    [final_pred[i] - 2 * final_uncertainty[i], final_pred[i], final_pred[i] + 2 * final_uncertainty[i]]
                    for i in range(len(final_pred))
                ]])
                advanced_uncertainties = calculate_advanced_uncertainty(
                    dummy_quantiles, historical_volatility, market_conditions
                    )
                
                print(f"Technical strategy completed: {len(final_pred)} predictions generated")
                
                # Final continuity validation for technical strategy
                print("Performing final continuity validation for technical strategy...")
                last_actual = df['Close'].iloc[-1]
                first_pred = final_pred[0]
                discontinuity_threshold = max(1e-6, 0.01 * abs(last_actual))  # Stricter 1% threshold for final check
                
                if abs(first_pred - last_actual) > discontinuity_threshold:
                    print(f"Technical strategy final check: Discontinuity detected between last actual ({last_actual:.4f}) and first prediction ({first_pred:.4f})")
                    print(f"Technical strategy final discontinuity magnitude: {abs(first_pred - last_actual):.4f} ({abs(first_pred - last_actual)/last_actual*100:.2f}%)")
                    
                    # Apply final continuity correction for technical strategy
                    if len(final_pred) > 1:
                        # Calculate the overall trend
                        overall_trend = final_pred[-1] - first_pred
                        total_steps = len(final_pred) - 1
                        
                        if total_steps > 0:
                            trend_per_step = overall_trend / total_steps
                        else:
                            trend_per_step = 0
                        
                        # Apply very smooth transition
                        transition_length = min(8, len(final_pred))  # Longer transition for final correction
                        
                        for i in range(transition_length):
                            if i == 0:
                                # First prediction should be extremely close to last actual
                                final_pred[i] = last_actual + trend_per_step * 0.05
                            else:
                                # Very gradual transition
                                transition_factor = min(1.0, (i / transition_length) ** 2)  # Quadratic easing
                                trend_contribution = trend_per_step * i * transition_factor
                                final_pred[i] = last_actual + trend_contribution
                        
                        # Maintain relative relationships for remaining predictions
                        if len(final_pred) > transition_length:
                            for i in range(transition_length, len(final_pred)):
                                if i == transition_length:
                                    # Smooth transition at boundary
                                    final_pred[i] = final_pred[i-1] + trend_per_step * 0.8
                                else:
                                    # Maintain original relative differences
                                    original_diff = final_pred[i] - final_pred[i-1]
                                    final_pred[i] = final_pred[i-1] + original_diff * 0.9  # Slightly dampened
                        
                        print(f"Technical strategy final continuity correction applied: First prediction adjusted from {first_pred:.4f} to {final_pred[0]:.4f}")
                        
                        # Apply additional smoothing for final correction
                        if use_smoothing:
                            final_pred = apply_financial_smoothing(final_pred, smoothing_type, smoothing_window, smoothing_alpha * 0.5, 3, use_smoothing)
                    else:
                        # Single prediction case
                        final_pred[0] = last_actual
                        print(f"Technical strategy final single prediction correction: Set to last actual value {last_actual:.4f}")
                
                # Verify final continuity for technical strategy
                final_first_pred = final_pred[0]
                final_discontinuity = abs(final_first_pred - last_actual) / last_actual * 100
                print(f"Technical strategy final continuity check: Discontinuity = {final_discontinuity:.3f}% (threshold: 1.0%)")
                
                if final_discontinuity <= 1.0:
                    print("✓ Technical strategy continuity validation passed - predictions are smooth")
                else:
                    print(f"⚠ Technical strategy continuity validation warning - discontinuity of {final_discontinuity:.3f}% remains")
                
            except Exception as e:
                print(f"Technical strategy error: {str(e)}")
                # Fallback to simple moving average prediction
                print("Falling back to simple moving average prediction...")
                try:
                    last_price = df['Close'].iloc[-1]
                    volatility = df['Volatility'].iloc[-1]
                    
                    final_pred = np.array([last_price * (1 + 0.001 * i) for i in range(1, prediction_days + 1)])
                    final_uncertainty = np.array([volatility * last_price * np.sqrt(i) for i in range(1, prediction_days + 1)])
                    
                    volume_pred = None
                    volume_uncertainty = None
                    ensemble_pred = np.array([])
                    ensemble_uncertainty = np.array([])
                    
                    # Calculate advanced uncertainties for fallback case
                    dummy_quantiles = np.array([[
                        [final_pred[i] - 2 * final_uncertainty[i], final_pred[i], final_pred[i] + 2 * final_uncertainty[i]]
                        for i in range(len(final_pred))
                    ]])
                    advanced_uncertainties = calculate_advanced_uncertainty(
                        dummy_quantiles, volatility, market_conditions
                    )
                    
                    # Final continuity validation for fallback case
                    print("Performing final continuity validation for fallback prediction...")
                    last_actual = df['Close'].iloc[-1]
                    first_pred = final_pred[0]
                    discontinuity_threshold = max(1e-6, 0.01 * abs(last_actual))  # Stricter 1% threshold for final check
                    
                    if abs(first_pred - last_actual) > discontinuity_threshold:
                        print(f"Fallback final check: Discontinuity detected between last actual ({last_actual:.4f}) and first prediction ({first_pred:.4f})")
                        print(f"Fallback final discontinuity magnitude: {abs(first_pred - last_actual):.4f} ({abs(first_pred - last_actual)/last_actual*100:.2f}%)")
                        
                        # Apply final continuity correction for fallback case
                        if len(final_pred) > 1:
                            # Calculate the overall trend
                            overall_trend = final_pred[-1] - first_pred
                            total_steps = len(final_pred) - 1
                            
                            if total_steps > 0:
                                trend_per_step = overall_trend / total_steps
                            else:
                                trend_per_step = 0
                            
                            # Apply very smooth transition
                            transition_length = min(8, len(final_pred))  # Longer transition for final correction
                            
                            for i in range(transition_length):
                                if i == 0:
                                    # First prediction should be extremely close to last actual
                                    final_pred[i] = last_actual + trend_per_step * 0.05
                                else:
                                    # Very gradual transition
                                    transition_factor = min(1.0, (i / transition_length) ** 2)  # Quadratic easing
                                    trend_contribution = trend_per_step * i * transition_factor
                                    final_pred[i] = last_actual + trend_contribution
                            
                            # Maintain relative relationships for remaining predictions
                            if len(final_pred) > transition_length:
                                for i in range(transition_length, len(final_pred)):
                                    if i == transition_length:
                                        # Smooth transition at boundary
                                        final_pred[i] = final_pred[i-1] + trend_per_step * 0.8
                                    else:
                                        # Maintain original relative differences
                                        original_diff = final_pred[i] - final_pred[i-1]
                                        final_pred[i] = final_pred[i-1] + original_diff * 0.9  # Slightly dampened
                            
                            print(f"Fallback final continuity correction applied: First prediction adjusted from {first_pred:.4f} to {final_pred[0]:.4f}")
                        else:
                            # Single prediction case
                            final_pred[0] = last_actual
                            print(f"Fallback final single prediction correction: Set to last actual value {last_actual:.4f}")
                    
                    # Verify final continuity for fallback case
                    final_first_pred = final_pred[0]
                    final_discontinuity = abs(final_first_pred - last_actual) / last_actual * 100
                    print(f"Fallback final continuity check: Discontinuity = {final_discontinuity:.3f}% (threshold: 1.0%)")
                    
                    if final_discontinuity <= 1.0:
                        print("✓ Fallback continuity validation passed - predictions are smooth")
                    else:
                        print(f"⚠ Fallback continuity validation warning - discontinuity of {final_discontinuity:.3f}% remains")
                    
                except Exception as fallback_error:
                    print(f"Fallback prediction error: {str(fallback_error)}")
                    raise
        
        else:
            raise ValueError(f"Unknown strategy: {strategy}. Supported strategies: 'chronos', 'technical'")
        
        # Create prediction dates
        last_date = df.index[-1]
        if timeframe == "1d":
            pred_dates = pd.date_range(start=last_date + timedelta(days=1), periods=prediction_days)
        elif timeframe == "1h":
            pred_dates = pd.date_range(start=last_date + timedelta(hours=1), periods=prediction_days * 24)
        else:  # 15m
            pred_dates = pd.date_range(start=last_date + timedelta(minutes=15), periods=prediction_days * 96)
        
        # Create enhanced visualization with uncertainties integrated
        fig = make_subplots(rows=3, cols=1, 
                           shared_xaxes=True,
                           vertical_spacing=0.12, 
                           subplot_titles=('Price Prediction with Uncertainty', 'Technical Indicators with Uncertainty', 'Volume with Uncertainty'))
        
        # Add historical price
        fig.add_trace(
            go.Scatter(x=df.index, y=df['Close'], name='Historical Price',
                      line=dict(color='blue', width=2)),
            row=1, col=1
        )
        
        # Add predicted price with integrated uncertainty bands
        fig.add_trace(
            go.Scatter(x=pred_dates, y=final_pred, name='Predicted Price',
                      line=dict(color='red', width=3)),
            row=1, col=1
        )
        
        # Add price uncertainty bands on the same subplot
        if final_uncertainty is not None and len(final_uncertainty) > 0:
            uncertainty_clean = np.array(final_uncertainty)
            uncertainty_clean = np.where(np.isnan(uncertainty_clean), 0, uncertainty_clean)
            
            # Create confidence bands
            confidence_68 = uncertainty_clean  # 1 standard deviation (68% confidence)
            confidence_95 = 2 * uncertainty_clean  # 2 standard deviations (95% confidence)
            
            # Plot 95% confidence bands
            fig.add_trace(
                go.Scatter(x=pred_dates, y=final_pred + confidence_95, name='95% Confidence Upper',
                          line=dict(color='red', width=1, dash='dash'), showlegend=False),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=pred_dates, y=final_pred - confidence_95, name='95% Confidence Lower',
                          line=dict(color='red', width=1, dash='dash'), fill='tonexty',
                          fillcolor='rgba(255,0,0,0.1)', showlegend=False),
                row=1, col=1
            )
            
            # Plot 68% confidence bands
            fig.add_trace(
                go.Scatter(x=pred_dates, y=final_pred + confidence_68, name='68% Confidence Upper',
                          line=dict(color='darkred', width=1, dash='dot'), showlegend=False),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=pred_dates, y=final_pred - confidence_68, name='68% Confidence Lower',
                          line=dict(color='darkred', width=1, dash='dot'), fill='tonexty',
                          fillcolor='rgba(139,0,0,0.1)', showlegend=False),
                row=1, col=1
            )
        
        # Add Bollinger Bands if available (on price subplot)
        if 'BB_Upper' in df.columns and 'BB_Middle' in df.columns and 'BB_Lower' in df.columns:
            fig.add_trace(
                go.Scatter(x=df.index, y=df['BB_Upper'], name='BB Upper (Historical)',
                          line=dict(color='gray', width=1, dash='dash')),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=df.index, y=df['BB_Middle'], name='BB Middle (Historical)',
                          line=dict(color='gray', width=1)),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(x=df.index, y=df['BB_Lower'], name='BB Lower (Historical)',
                          line=dict(color='gray', width=1, dash='dash')),
                row=1, col=1
            )
            
            # Add predicted Bollinger Bands if available
            if 'BB_Upper' in technical_predictions:
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=technical_predictions['BB_Upper'], name='BB Upper (Predicted)',
                              line=dict(color='darkgray', width=2, dash='dash')),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=technical_predictions['BB_Middle'], name='BB Middle (Predicted)',
                              line=dict(color='darkgray', width=2)),
                    row=1, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=technical_predictions['BB_Lower'], name='BB Lower (Predicted)',
                              line=dict(color='darkgray', width=2, dash='dash')),
                    row=1, col=1
                )
        
        # Add technical indicators with their uncertainties on the same subplot
        # RSI with uncertainty
        fig.add_trace(
            go.Scatter(x=df.index, y=df['RSI'], name='RSI (Historical)',
                      line=dict(color='purple', width=1)),
            row=2, col=1
        )
        
        if 'RSI' in technical_predictions:
            fig.add_trace(
                go.Scatter(x=pred_dates, y=technical_predictions['RSI'], name='RSI (Predicted)',
                          line=dict(color='purple', width=2, dash='dash')),
                row=2, col=1
            )
            
            # Add RSI uncertainty bands
            if 'RSI' in technical_uncertainties:
                rsi_upper = technical_predictions['RSI'] + 2 * technical_uncertainties['RSI']
                rsi_lower = technical_predictions['RSI'] - 2 * technical_uncertainties['RSI']
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=rsi_upper, name='RSI Upper Bound',
                              line=dict(color='purple', width=1, dash='dot'), showlegend=False),
                    row=2, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=rsi_lower, name='RSI Lower Bound',
                              line=dict(color='purple', width=1, dash='dot'), fill='tonexty',
                              fillcolor='rgba(128,0,128,0.1)', showlegend=False),
                    row=2, col=1
                )
        
        # MACD with uncertainty
        fig.add_trace(
            go.Scatter(x=df.index, y=df['MACD'], name='MACD (Historical)',
                      line=dict(color='orange', width=1)),
            row=2, col=1
        )
        
        if 'MACD' in technical_predictions:
            fig.add_trace(
                go.Scatter(x=pred_dates, y=technical_predictions['MACD'], name='MACD (Predicted)',
                          line=dict(color='orange', width=2, dash='dash')),
                row=2, col=1
            )
            
            # Add MACD signal line if available
            if 'MACD_Signal' in technical_predictions:
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=technical_predictions['MACD_Signal'], name='MACD Signal (Predicted)',
                              line=dict(color='red', width=1, dash='dash')),
                    row=2, col=1
                )
            
            # Add MACD uncertainty bands
            if 'MACD' in technical_uncertainties:
                macd_upper = technical_predictions['MACD'] + 2 * technical_uncertainties['MACD']
                macd_lower = technical_predictions['MACD'] - 2 * technical_uncertainties['MACD']
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=macd_upper, name='MACD Upper Bound',
                              line=dict(color='orange', width=1, dash='dot'), showlegend=False),
                    row=2, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=macd_lower, name='MACD Lower Bound',
                              line=dict(color='orange', width=1, dash='dot'), fill='tonexty',
                              fillcolor='rgba(255,165,0,0.1)', showlegend=False),
                    row=2, col=1
                )
        
        # Add volume with uncertainty on the same subplot
        if 'Volume' in df.columns and not df['Volume'].isna().all():
            volume_data = pd.to_numeric(df['Volume'], errors='coerce').fillna(0)
            
            fig.add_trace(
                go.Bar(x=df.index, y=volume_data, name='Historical Volume',
                      marker_color='lightblue', opacity=0.7),
                row=3, col=1
            )
        else:
            print("Warning: No valid volume data available for plotting")
        
        # Add predicted volume with better handling
        if volume_pred is not None and len(volume_pred) > 0:
            # Ensure volume prediction is numeric and handle any NaN values
            volume_pred_clean = np.array(volume_pred)
            volume_pred_clean = np.where(np.isnan(volume_pred_clean), 0, volume_pred_clean)
            
            fig.add_trace(
                go.Bar(x=pred_dates, y=volume_pred_clean, name='Predicted Volume',
                      marker_color='red', opacity=0.7),
                row=3, col=1
            )
            
            # Add volume uncertainty bands if available
            if volume_uncertainty is not None and len(volume_uncertainty) > 0:
                volume_uncertainty_clean = np.array(volume_uncertainty)
                volume_uncertainty_clean = np.where(np.isnan(volume_uncertainty_clean), 0, volume_uncertainty_clean)
                
                volume_upper = volume_pred_clean + 2 * volume_uncertainty_clean
                volume_lower = np.maximum(0, volume_pred_clean - 2 * volume_uncertainty_clean)
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=volume_upper, name='Volume Upper Bound',
                              line=dict(color='red', width=1, dash='dot'), showlegend=False),
                    row=3, col=1
                )
                
                fig.add_trace(
                    go.Scatter(x=pred_dates, y=volume_lower, name='Volume Lower Bound',
                              line=dict(color='red', width=1, dash='dot'), fill='tonexty',
                              fillcolor='rgba(255,0,0,0.1)', showlegend=False),
                    row=3, col=1
                )
        
        # Add reference lines for technical indicators
        # RSI overbought/oversold lines
        fig.add_hline(y=70, line_dash="dash", line_color="red", 
                     annotation_text="Overbought (70)", row=2, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", 
                     annotation_text="Oversold (30)", row=2, col=1)
        
        # MACD zero line
        fig.add_hline(y=0, line_dash="dash", line_color="black", 
                     annotation_text="MACD Zero", row=2, col=1)
        
        # Add volume reference line (average volume)
        if 'Volume' in df.columns and not df['Volume'].isna().all():
            avg_volume = df['Volume'].mean()
            fig.add_hline(y=avg_volume, line_dash="dash", line_color="blue", 
                         annotation_text=f"Avg Volume: {avg_volume:,.0f}", row=3, col=1)
        
        
        fig.update_layout(
            title=dict(
                text=f'Enhanced Stock Prediction for {symbol}',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color='black'),
                y=0.95  # Moved down slightly to avoid overlap
            ),
            height=1000, 
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.15,  # Position legend below all subplots
                xanchor="center",
                x=0.5,  # Center the legend horizontally
                bgcolor='rgba(255,255,255,0.9)',  
                bordercolor='black',
                borderwidth=1,
                font=dict(size=10)  # Smaller font for better fit
            ),
            margin=dict(t=120, b=150, l=80, r=80),  # Increased bottom margin for legend  
            autosize=True,  
            hovermode='x unified'  
        )
        
        fig.update_xaxes(
            title_text="Date", 
            row=3, col=1,
            title_font=dict(size=12, color='black'),
            tickfont=dict(size=10)
        )
        fig.update_yaxes(
            title_text="Price ($)", 
            row=1, col=1,
            title_font=dict(size=12, color='black'),
            tickfont=dict(size=10)
        )
        fig.update_yaxes(
            title_text="Technical Indicators", 
            row=2, col=1,
            title_font=dict(size=12, color='black'),
            tickfont=dict(size=10)
        )
        fig.update_yaxes(
            title_text="Volume", 
            row=3, col=1,
            title_font=dict(size=12, color='black'),
            tickfont=dict(size=10)
        )
        
        for i in range(len(fig.layout.annotations)):
            if i < 3: 
                fig.layout.annotations[i].update(
                    font=dict(size=13, color='darkblue', family='Arial, sans-serif'),
                    y=fig.layout.annotations[i].y + 0.01,  # Reduced adjustment to prevent overlap
                    bgcolor='rgba(255,255,255,0.9)', 
                    bordercolor='lightgray',
                    borderwidth=1
                )
    
        
        # Create comprehensive trading signals
        trading_signals = {
            'prediction': {
                'dates': pred_dates.tolist(),
                'prices': final_pred.tolist(),
                'uncertainty': final_uncertainty.tolist(),
                'volume': volume_pred.tolist() if volume_pred is not None else None
            },
            'historical': {
                'dates': df.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
                'prices': df['Close'].tolist(),
                'volume': df['Volume'].tolist() if 'Volume' in df.columns else None
            },
            'technical_indicators': {
                'predictions': {k: v.tolist() for k, v in technical_predictions.items()},
                'uncertainties': {k: v.tolist() for k, v in technical_uncertainties.items()}
            },
            'advanced_uncertainties': advanced_uncertainties,
            'regime_info': regime_info,
            'sentiment_data': sentiment_data,
            'market_conditions': market_conditions,
            'covariate_data_available': len(covariate_data) > 0
        }
        
        # Add stress testing results if enabled
        stress_test_results = {}
        if use_stress_testing:
            try:
                print("Performing stress testing...")
                stress_test_results = stress_test_scenarios(df, final_pred)
                trading_signals['stress_test_results'] = stress_test_results
            except Exception as stress_error:
                print(f"Stress testing failed: {str(stress_error)}")
                trading_signals['stress_test_results'] = {"error": str(stress_error)}
        
        # Add advanced trading signals
        try:
            print("Generating advanced trading signals...")
            advanced_signals = advanced_trading_signals(df, regime_info)
            trading_signals['advanced_signals'] = advanced_signals
        except Exception as advanced_error:
            print(f"Advanced trading signals failed: {str(advanced_error)}")
            trading_signals['advanced_signals'] = {"error": str(advanced_error)}
        
        # Add basic trading signals
        try:
            basic_signals = calculate_trading_signals(df)
            trading_signals.update(basic_signals)
            trading_signals['symbol'] = symbol
            trading_signals['timeframe'] = timeframe
            trading_signals['strategy_used'] = strategy
            trading_signals['ensemble_used'] = use_ensemble
        except Exception as basic_error:
            print(f"Basic trading signals failed: {str(basic_error)}")
            trading_signals['error'] = str(basic_error)
        
        # Debug information for volume and uncertainty
        print(f"Volume data info:")
        print(f"  Historical volume shape: {df['Volume'].shape if 'Volume' in df.columns else 'No volume column'}")
        print(f"  Historical volume NaN count: {df['Volume'].isna().sum() if 'Volume' in df.columns else 'N/A'}")
        print(f"  Predicted volume shape: {volume_pred.shape if volume_pred is not None else 'None'}")
        print(f"  Predicted volume NaN count: {np.isnan(volume_pred).sum() if volume_pred is not None else 'N/A'}")
        
        print(f"Uncertainty data info:")
        print(f"  Final uncertainty shape: {final_uncertainty.shape if final_uncertainty is not None else 'None'}")
        print(f"  Final uncertainty NaN count: {np.isnan(final_uncertainty).sum() if final_uncertainty is not None else 'N/A'}")
        print(f"  Final uncertainty range: [{np.min(final_uncertainty):.4f}, {np.max(final_uncertainty):.4f}]" if final_uncertainty is not None else 'N/A')
        
        return trading_signals, fig
        
    except Exception as e:
        print(f"Enhanced prediction error: {str(e)}")
        raise

def calculate_trading_signals(df: pd.DataFrame) -> Dict:
    """Calculate trading signals based on technical indicators"""
    signals = {
        "RSI": "Oversold" if df['RSI'].iloc[-1] < 30 else "Overbought" if df['RSI'].iloc[-1] > 70 else "Neutral",
        "MACD": "Buy" if df['MACD'].iloc[-1] > df['MACD_Signal'].iloc[-1] else "Sell",
        "Bollinger": "Buy" if df['Close'].iloc[-1] < df['BB_Lower'].iloc[-1] else "Sell" if df['Close'].iloc[-1] > df['BB_Upper'].iloc[-1] else "Hold",
        "SMA": "Buy" if df['SMA_20'].iloc[-1] > df['SMA_50'].iloc[-1] else "Sell"
    }
    
    # Calculate overall signal
    buy_signals = sum(1 for signal in signals.values() if signal == "Buy")
    sell_signals = sum(1 for signal in signals.values() if signal == "Sell")
    
    if buy_signals > sell_signals:
        signals["Overall"] = "Buy"
    elif sell_signals > buy_signals:
        signals["Overall"] = "Sell"
    else:
        signals["Overall"] = "Hold"
    
    return signals

def get_market_data(symbol: str = "^GSPC", lookback_days: int = 365) -> pd.DataFrame:
    """
    Fetch market data (S&P 500 by default) for correlation analysis and regime detection.
    Uses recommended yfinance API methods for better reliability.
    
    Args:
        symbol (str): Market index symbol (default: ^GSPC for S&P 500)
        lookback_days (int): Number of days to look back
    
    Returns:
        pd.DataFrame: Market data with returns
    """
    cache_key = f"{symbol}_{lookback_days}"
    current_time = time.time()
    
    # Check cache
    if cache_key in market_data_cache and current_time < cache_expiry.get(cache_key, 0):
        return market_data_cache[cache_key]
    
    try:
        ticker = yf.Ticker(symbol)
        
        def fetch_market_history():
            return ticker.history(
                period=f"{lookback_days}d",
                interval="1d",
                prepost=False,
                actions=False,
                auto_adjust=True,
                back_adjust=True,
                repair=True
            )
        
        df = retry_yfinance_request(fetch_market_history)
        
        if df is not None and not df.empty:
            df['Returns'] = df['Close'].pct_change()
            df['Volatility'] = df['Returns'].rolling(window=20).std()
            
            # Cache the data
            market_data_cache[cache_key] = df
            cache_expiry[cache_key] = current_time + CACHE_DURATION
            
            print(f"Successfully fetched market data for {symbol}: {len(df)} data points")
        else:
            print(f"Warning: No data returned for {symbol}")
            df = pd.DataFrame()
            
        return df
    except Exception as e:
        print(f"Warning: Could not fetch market data for {symbol}: {str(e)}")
        return pd.DataFrame()

def detect_market_regime(returns: pd.Series, n_regimes: int = 3) -> Dict:
    """
    Detect market regime using Hidden Markov Model or simplified methods.
    
    Args:
        returns (pd.Series): Price returns
        n_regimes (int): Number of regimes to detect
    
    Returns:
        Dict: Regime information including probabilities and characteristics
    """
    def get_regime_name(regime_idx: int, means: List[float], volatilities: List[float]) -> str:
        """
        Convert regime index to descriptive name based on characteristics.
        
        Args:
            regime_idx (int): Regime index (0, 1, 2)
            means (List[float]): List of regime means
            volatilities (List[float]): List of regime volatilities
        
        Returns:
            str: Descriptive regime name
        """
        if len(means) != 3 or len(volatilities) != 3:
            return f"Regime {regime_idx}"
        
        # Sort regimes by volatility (low to high)
        vol_sorted = sorted(range(len(volatilities)), key=lambda i: volatilities[i])
        
        # Sort regimes by mean return (low to high)
        mean_sorted = sorted(range(len(means)), key=lambda i: means[i])
        
        # Determine regime characteristics
        if regime_idx == vol_sorted[0]:  # Lowest volatility
            if means[regime_idx] > 0:
                return "Low Volatility Bull"
            else:
                return "Low Volatility Bear"
        elif regime_idx == vol_sorted[2]:  # Highest volatility
            if means[regime_idx] > 0:
                return "High Volatility Bull"
            else:
                return "High Volatility Bear"
        else:  # Medium volatility
            if means[regime_idx] > 0:
                return "Moderate Bull"
            else:
                return "Moderate Bear"
    
    if len(returns) < 50:
        return {"regime": "Normal Market", "probabilities": [1.0], "volatility": returns.std()}
    
    try:
        if HMM_AVAILABLE:
            # Use HMM for regime detection
            # Convert pandas Series to numpy array for reshape
            returns_array = returns.dropna().values
            
            # Try different HMM configurations if convergence fails
            for attempt in range(3):
                try:
                    if attempt == 0:
                        model = hmm.GaussianHMM(
                            n_components=n_regimes, 
                            random_state=42, 
                            covariance_type="full", 
                            n_iter=500,
                            tol=1e-4,
                            init_params="stmc"
                        )
                    elif attempt == 1:
                        model = hmm.GaussianHMM(
                            n_components=n_regimes, 
                            random_state=42, 
                            covariance_type="diag", 
                            n_iter=1000,
                            tol=1e-3,
                            init_params="stmc"
                        )
                    else:
                        model = hmm.GaussianHMM(
                            n_components=n_regimes, 
                            random_state=42, 
                            covariance_type="spherical", 
                            n_iter=1500,
                            tol=1e-2,
                            init_params="stmc"
                        )
                    
                    # Add data preprocessing to improve convergence
                    returns_clean = returns_array[~np.isnan(returns_array)]
                    returns_clean = returns_clean[~np.isinf(returns_clean)]
                    
                    # Remove outliers that might cause convergence issues
                    q1, q3 = np.percentile(returns_clean, [25, 75])
                    iqr = q3 - q1
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    returns_filtered = returns_clean[(returns_clean >= lower_bound) & (returns_clean <= upper_bound)]
                    
                    # Ensure we have enough data
                    if len(returns_filtered) < 50:
                        returns_filtered = returns_clean
                    
                    # Fit the model with filtered data
                    model.fit(returns_filtered.reshape(-1, 1))
                    
                    # Check if model converged
                    if model.monitor_.converged:
                        print(f"HMM converged successfully with {model.covariance_type} covariance type")
                    else:
                        print(f"HMM did not converge with {model.covariance_type} covariance type, trying next configuration...")
                        if attempt < 2:  # Not the last attempt
                            continue
                        else:
                            print("HMM failed to converge with all configurations, using fallback method")
                            raise Exception("HMM convergence failed")
                    
                    # Get regime probabilities for the last observation
                    regime_probs = model.predict_proba(returns_array.reshape(-1, 1))
                    current_regime = model.predict(returns_array.reshape(-1, 1))[-1]
                    
                    # Calculate regime characteristics
                    regime_means = model.means_.flatten()
                    regime_vols = np.sqrt(model.covars_.diagonal(axis1=1, axis2=2)) if model.covariance_type == "full" else np.sqrt(model.covars_)
                    
                    # Convert regime index to descriptive name
                    regime_name = get_regime_name(int(current_regime), regime_means.tolist(), regime_vols.tolist())
                    
                    return {
                        "regime": regime_name,
                        "regime_index": int(current_regime),
                        "probabilities": regime_probs[-1].tolist(),
                        "means": regime_means.tolist(),
                        "volatilities": regime_vols.tolist(),
                        "method": f"HMM-{model.covariance_type}"
                    }
                except Exception as e:
                    if attempt == 2:  # Last attempt failed
                        print(f"HMM failed after {attempt + 1} attempts: {str(e)}")
                        break
                    continue
        else:
            # Simplified regime detection using volatility clustering
            volatility = returns.rolling(window=20).std().dropna()
            vol_percentile = volatility.iloc[-1] / volatility.quantile(0.8)
            
            if vol_percentile > 1.2:
                regime_name = "High Volatility Market"
                regime = 2  # High volatility regime
            elif vol_percentile < 0.8:
                regime_name = "Low Volatility Market"
                regime = 0  # Low volatility regime
            else:
                regime_name = "Normal Market"
                regime = 1  # Normal regime
            
            return {
                "regime": regime_name,
                "regime_index": regime,
                "probabilities": [0.1, 0.8, 0.1] if regime == 1 else [0.8, 0.1, 0.1] if regime == 0 else [0.1, 0.1, 0.8],
                "volatility": volatility.iloc[-1],
                "method": "Volatility-based"
            }
    except Exception as e:
        print(f"Warning: Regime detection failed: {str(e)}")
        return {"regime": "Normal Market", "regime_index": 1, "probabilities": [1.0], "volatility": returns.std(), "method": "Fallback"}

def calculate_advanced_risk_metrics(df: pd.DataFrame, market_returns: pd.Series = None, 
                                  risk_free_rate: float = 0.02) -> Dict:
    """
    Calculate advanced risk metrics including tail risk and market correlation.
    
    Args:
        df (pd.DataFrame): Stock data
        market_returns (pd.Series): Market returns for correlation analysis
        risk_free_rate (float): Annual risk-free rate
    
    Returns:
        Dict: Advanced risk metrics
    """
    try:
        returns = df['Returns'].dropna()
        
        if len(returns) < 30:
            return {"error": "Insufficient data for risk calculation"}
        
        # Basic metrics
        annual_return = returns.mean() * 252
        annual_vol = returns.std() * np.sqrt(252)
        
        # Market-adjusted metrics
        beta = 1.0
        alpha = 0.0
        correlation = 0.0
        aligned_returns = None
        aligned_market = None
        
        if market_returns is not None and len(market_returns) > 0:
            try:
                # Align dates
                aligned_returns = returns.reindex(market_returns.index).dropna()
                aligned_market = market_returns.reindex(aligned_returns.index).dropna()
                
                # Ensure both arrays have the same length
                if len(aligned_returns) > 10 and len(aligned_market) > 10:
                    # Find the common length
                    min_length = min(len(aligned_returns), len(aligned_market))
                    aligned_returns = aligned_returns.iloc[-min_length:]
                    aligned_market = aligned_market.iloc[-min_length:]
                    
                    # Ensure they have the same length
                    if len(aligned_returns) == len(aligned_market) and len(aligned_returns) > 10:
                        try:
                            beta = np.cov(aligned_returns, aligned_market)[0,1] / np.var(aligned_market)
                            alpha = aligned_returns.mean() - beta * aligned_market.mean()
                            correlation = np.corrcoef(aligned_returns, aligned_market)[0,1]
                        except Exception as e:
                            print(f"Market correlation calculation error: {str(e)}")
                            beta = 1.0
                            alpha = 0.0
                            correlation = 0.0
                    else:
                        beta = 1.0
                        alpha = 0.0
                        correlation = 0.0
                else:
                    beta = 1.0
                    alpha = 0.0
                    correlation = 0.0
            except Exception as e:
                print(f"Market data alignment error: {str(e)}")
                beta = 1.0
                alpha = 0.0
                correlation = 0.0
                aligned_returns = None
                aligned_market = None
        
        # Tail risk metrics
        var_95 = np.percentile(returns, 5)
        var_99 = np.percentile(returns, 1)
        cvar_95 = returns[returns <= var_95].mean()
        cvar_99 = returns[returns <= var_99].mean()
        
        # Maximum drawdown
        cumulative_returns = (1 + returns).cumprod()
        rolling_max = cumulative_returns.expanding().max()
        drawdown = (cumulative_returns - rolling_max) / rolling_max
        max_drawdown = drawdown.min()
        
        # Skewness and kurtosis
        skewness = stats.skew(returns)
        kurtosis = stats.kurtosis(returns)
        
        # Risk-adjusted returns
        sharpe_ratio = (annual_return - risk_free_rate) / annual_vol if annual_vol > 0 else 0
        sortino_ratio = (annual_return - risk_free_rate) / (returns[returns < 0].std() * np.sqrt(252)) if returns[returns < 0].std() > 0 else 0
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0
        
        # Information ratio (if market data available)
        information_ratio = 0
        if aligned_returns is not None and aligned_market is not None:
            try:
                if len(aligned_returns) > 10 and len(aligned_market) > 10:
                    min_length = min(len(aligned_returns), len(aligned_market))
                    aligned_returns_for_ir = aligned_returns.iloc[-min_length:]
                    aligned_market_for_ir = aligned_market.iloc[-min_length:]
                    
                    if len(aligned_returns_for_ir) == len(aligned_market_for_ir):
                        excess_returns = aligned_returns_for_ir - aligned_market_for_ir
                        information_ratio = excess_returns.mean() / excess_returns.std() if excess_returns.std() > 0 else 0
                    else:
                        information_ratio = 0
                else:
                    information_ratio = 0
            except Exception as e:
                print(f"Information ratio calculation error: {str(e)}")
                information_ratio = 0
        
        return {
            "Annual_Return": annual_return,
            "Annual_Volatility": annual_vol,
            "Sharpe_Ratio": sharpe_ratio,
            "Sortino_Ratio": sortino_ratio,
            "Calmar_Ratio": calmar_ratio,
            "Information_Ratio": information_ratio,
            "Beta": beta,
            "Alpha": alpha * 252,
            "Correlation_with_Market": correlation,
            "VaR_95": var_95,
            "VaR_99": var_99,
            "CVaR_95": cvar_95,
            "CVaR_99": cvar_99,
            "Max_Drawdown": max_drawdown,
            "Skewness": skewness,
            "Kurtosis": kurtosis,
            "Risk_Free_Rate": risk_free_rate
        }
    except Exception as e:
        print(f"Advanced risk metrics calculation error: {str(e)}")
        return {"error": f"Risk calculation failed: {str(e)}"}

def create_ensemble_prediction(df: pd.DataFrame, prediction_days: int, 
                             ensemble_weights: Dict = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create ensemble prediction combining multiple models.
    
    Args:
        df (pd.DataFrame): Historical data
        prediction_days (int): Number of days to predict
        ensemble_weights (Dict): Weights for different models
    
    Returns:
        Tuple[np.ndarray, np.ndarray]: Mean and uncertainty predictions
    """
    if ensemble_weights is None:
        ensemble_weights = {"chronos": 0.6, "technical": 0.2, "statistical": 0.2}
    
    predictions = {}
    uncertainties = {}
    
    # Chronos prediction (placeholder - will be filled by main prediction function)
    predictions["chronos"] = np.array([])
    uncertainties["chronos"] = np.array([])
    
    # Technical prediction
    if ensemble_weights.get("technical", 0) > 0:
        try:
            last_price = df['Close'].iloc[-1]
            rsi = df['RSI'].iloc[-1]
            macd = df['MACD'].iloc[-1]
            macd_signal = df['MACD_Signal'].iloc[-1]
            volatility = df['Volatility'].iloc[-1]
            
            # Enhanced technical prediction
            trend = 1 if (rsi > 50 and macd > macd_signal) else -1
            mean_reversion = (df['SMA_200'].iloc[-1] - last_price) / last_price if 'SMA_200' in df.columns else 0
            
            tech_pred = []
            for i in range(1, prediction_days + 1):
                # Combine trend and mean reversion
                prediction = last_price * (1 + trend * volatility * 0.3 + mean_reversion * 0.1 * i)
                tech_pred.append(prediction)
            
            predictions["technical"] = np.array(tech_pred)
            uncertainties["technical"] = np.array([volatility * last_price * i for i in range(1, prediction_days + 1)])
        except Exception as e:
            print(f"Technical prediction error: {str(e)}")
            predictions["technical"] = np.array([])
            uncertainties["technical"] = np.array([])
    
    # Statistical prediction (ARIMA-like)
    if ensemble_weights.get("statistical", 0) > 0:
        try:
            returns = df['Returns'].dropna()
            if len(returns) > 10:
                # Simple moving average with momentum
                ma_short = df['Close'].rolling(window=10).mean().iloc[-1]
                ma_long = df['Close'].rolling(window=30).mean().iloc[-1]
                momentum = (ma_short - ma_long) / ma_long
                
                last_price = df['Close'].iloc[-1]
                stat_pred = []
                for i in range(1, prediction_days + 1):
                    # Mean reversion with momentum
                    prediction = last_price * (1 + momentum * 0.5 - 0.001 * i)  # Decay factor
                    stat_pred.append(prediction)
                
                predictions["statistical"] = np.array(stat_pred)
                uncertainties["statistical"] = np.array([returns.std() * last_price * np.sqrt(i) for i in range(1, prediction_days + 1)])
            else:
                predictions["statistical"] = np.array([])
                uncertainties["statistical"] = np.array([])
        except Exception as e:
            print(f"Statistical prediction error: {str(e)}")
            predictions["statistical"] = np.array([])
            uncertainties["statistical"] = np.array([])
    
    # Combine predictions
    valid_predictions = {k: v for k, v in predictions.items() if len(v) > 0}
    valid_uncertainties = {k: v for k, v in uncertainties.items() if len(v) > 0}
    
    if not valid_predictions:
        return np.array([]), np.array([])
    
    # Weighted ensemble
    total_weight = sum(ensemble_weights.get(k, 0) for k in valid_predictions.keys())
    if total_weight == 0:
        return np.array([]), np.array([])
    
    # Normalize weights
    normalized_weights = {k: ensemble_weights.get(k, 0) / total_weight for k in valid_predictions.keys()}
    
    # Calculate weighted mean and uncertainty
    max_length = max(len(v) for v in valid_predictions.values())
    ensemble_mean = np.zeros(max_length)
    ensemble_uncertainty = np.zeros(max_length)
    
    for model, pred in valid_predictions.items():
        weight = normalized_weights[model]
        if len(pred) < max_length:
            # Extend prediction using last value
            extended_pred = np.concatenate([pred, np.full(max_length - len(pred), pred[-1])])
            extended_unc = np.concatenate([valid_uncertainties[model], np.full(max_length - len(pred), valid_uncertainties[model][-1])])
        else:
            extended_pred = pred[:max_length]
            extended_unc = valid_uncertainties[model][:max_length]
        
        ensemble_mean += weight * extended_pred
        ensemble_uncertainty += weight * extended_unc
    
    return ensemble_mean, ensemble_uncertainty

def stress_test_scenarios(df: pd.DataFrame, prediction: np.ndarray, 
                         scenarios: Dict = None) -> Dict:
    """
    Perform stress testing under various market scenarios.
    
    Args:
        df (pd.DataFrame): Historical data
        prediction (np.ndarray): Base prediction
        scenarios (Dict): Stress test scenarios
    
    Returns:
        Dict: Stress test results
    """
    if scenarios is None:
        scenarios = {
            "market_crash": {"volatility_multiplier": 3.0, "return_shock": -0.15},
            "high_volatility": {"volatility_multiplier": 2.0, "return_shock": -0.05},
            "low_volatility": {"volatility_multiplier": 0.5, "return_shock": 0.02},
            "bull_market": {"volatility_multiplier": 1.2, "return_shock": 0.10},
            "interest_rate_shock": {"volatility_multiplier": 1.5, "return_shock": -0.08}
        }
    
    base_volatility = df['Volatility'].iloc[-1]
    base_return = df['Returns'].mean()
    last_price = df['Close'].iloc[-1]
    
    stress_results = {}
    
    for scenario_name, params in scenarios.items():
        try:
            # Calculate stressed parameters
            stressed_vol = base_volatility * params["volatility_multiplier"]
            stressed_return = base_return + params["return_shock"]
            
            # Generate stressed prediction
            stressed_pred = []
            for i, pred in enumerate(prediction):
                # Apply stress factors
                stress_factor = 1 + stressed_return * (i + 1) / 252
                volatility_impact = np.random.normal(0, stressed_vol * np.sqrt((i + 1) / 252))
                stressed_price = pred * stress_factor * (1 + volatility_impact)
                stressed_pred.append(stressed_price)
            
            # Calculate stress metrics
            stress_results[scenario_name] = {
                "prediction": np.array(stressed_pred),
                "max_loss": min(stressed_pred) / last_price - 1,
                "volatility": stressed_vol,
                "expected_return": stressed_return,
                "var_95": np.percentile([p / last_price - 1 for p in stressed_pred], 5)
            }
        except Exception as e:
            print(f"Stress test error for {scenario_name}: {str(e)}")
            stress_results[scenario_name] = {"error": str(e)}
    
    return stress_results

def calculate_skewed_uncertainty(quantiles: np.ndarray, confidence_level: float = 0.9) -> np.ndarray:
    """
    Calculate uncertainty accounting for skewness in return distributions.
    
    Args:
        quantiles (np.ndarray): Quantile predictions from Chronos
        confidence_level (float): Confidence level for uncertainty calculation
    
    Returns:
        np.ndarray: Uncertainty estimates
    """
    try:
        lower = quantiles[0, :, 0]
        median = quantiles[0, :, 1]
        upper = quantiles[0, :, 2]
        
        # Calculate skewness for each prediction point
        uncertainties = []
        for i in range(len(lower)):
            # Calculate skewness
            if upper[i] != median[i] and median[i] != lower[i]:
                skewness = (median[i] - lower[i]) / (upper[i] - median[i])
            else:
                skewness = 1.0
            
            # Adjust z-score based on skewness
            if skewness > 1.2:  # Right-skewed
                z_score = stats.norm.ppf(confidence_level) * (1 + 0.1 * skewness)
            elif skewness < 0.8:  # Left-skewed
                z_score = stats.norm.ppf(confidence_level) * (1 - 0.1 * abs(skewness))
            else:
                z_score = stats.norm.ppf(confidence_level)
            
            # Calculate uncertainty
            uncertainty = (upper[i] - lower[i]) / (2 * z_score)
            uncertainties.append(uncertainty)
        
        return np.array(uncertainties)
    except Exception as e:
        print(f"Skewed uncertainty calculation error: {str(e)}")
        # Fallback to simple calculation
        return (quantiles[0, :, 2] - quantiles[0, :, 0]) / (2 * 1.645)

def adaptive_smoothing(new_pred: np.ndarray, historical_pred: np.ndarray, 
                      prediction_uncertainty: np.ndarray) -> np.ndarray:
    """
    Apply adaptive smoothing based on prediction uncertainty.
    
    Args:
        new_pred (np.ndarray): New predictions
        historical_pred (np.ndarray): Historical predictions
        prediction_uncertainty (np.ndarray): Prediction uncertainty
    
    Returns:
        np.ndarray: Smoothed predictions
    """
    try:
        if len(historical_pred) == 0:
            return new_pred
        
        # Calculate adaptive alpha based on uncertainty
        uncertainty_ratio = prediction_uncertainty / np.mean(np.abs(historical_pred))
        
        if uncertainty_ratio > 0.1:  # High uncertainty
            alpha = 0.1  # More smoothing
        elif uncertainty_ratio < 0.05:  # Low uncertainty
            alpha = 0.5  # Less smoothing
        else:
            alpha = 0.3  # Default
        
        # Apply weighted smoothing
        smoothed = alpha * new_pred + (1 - alpha) * historical_pred[-len(new_pred):]
        return smoothed
    except Exception as e:
        print(f"Adaptive smoothing error: {str(e)}")
        return new_pred

def advanced_trading_signals(df: pd.DataFrame, regime_info: Dict = None) -> Dict:
    """
    Generate advanced trading signals with confidence levels and regime awareness.
    
    Args:
        df (pd.DataFrame): Stock data
        regime_info (Dict): Market regime information
    
    Returns:
        Dict: Advanced trading signals
    """
    try:
        # Calculate signal strength and confidence
        rsi = df['RSI'].iloc[-1]
        macd = df['MACD'].iloc[-1]
        macd_signal = df['MACD_Signal'].iloc[-1]
        
        rsi_strength = abs(rsi - 50) / 50  # 0-1 scale
        macd_strength = abs(macd - macd_signal) / df['Close'].iloc[-1]
        
        # Regime-adjusted thresholds
        if regime_info and "volatilities" in regime_info:
            volatility_regime = df['Volatility'].iloc[-1] / np.mean(regime_info["volatilities"])
        else:
            volatility_regime = 1.0
        
        # Adjust RSI thresholds based on volatility
        rsi_oversold = 30 + (volatility_regime - 1) * 10
        rsi_overbought = 70 - (volatility_regime - 1) * 10
        
        # Calculate signals with confidence
        signals = {}
        
        # RSI signal
        if rsi < rsi_oversold:
            rsi_signal = "Oversold"
            rsi_confidence = min(0.9, 0.5 + rsi_strength * 0.4)
        elif rsi > rsi_overbought:
            rsi_signal = "Overbought"
            rsi_confidence = min(0.9, 0.5 + rsi_strength * 0.4)
        else:
            rsi_signal = "Neutral"
            rsi_confidence = 0.3
        
        signals["RSI"] = {
            "signal": rsi_signal,
            "strength": rsi_strength,
            "confidence": rsi_confidence,
            "value": rsi
        }
        
        # MACD signal
        if macd > macd_signal:
            macd_signal = "Buy"
            macd_confidence = min(0.8, 0.4 + macd_strength * 40)
        else:
            macd_signal = "Sell"
            macd_confidence = min(0.8, 0.4 + macd_strength * 40)
        
        signals["MACD"] = {
            "signal": macd_signal,
            "strength": macd_strength,
            "confidence": macd_confidence,
            "value": macd
        }
        
        # Bollinger Bands signal
        if 'BB_Upper' in df.columns and 'BB_Lower' in df.columns:
            current_price = df['Close'].iloc[-1]
            bb_upper = df['BB_Upper'].iloc[-1]
            bb_lower = df['BB_Lower'].iloc[-1]
            
            # Calculate position within Bollinger Bands (0-1 scale)
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
            bb_strength = abs(bb_position - 0.5) * 2  # 0-1 scale, strongest at edges
            
            if current_price < bb_lower:
                bb_signal = "Buy"
                bb_confidence = 0.7
            elif current_price > bb_upper:
                bb_signal = "Sell"
                bb_confidence = 0.7
            else:
                bb_signal = "Hold"
                bb_confidence = 0.5
            
            signals["Bollinger"] = {
                "signal": bb_signal,
                "strength": bb_strength,
                "confidence": bb_confidence,
                "position": bb_position
            }
        
        # SMA signal
        if 'SMA_20' in df.columns and 'SMA_50' in df.columns:
            sma_20 = df['SMA_20'].iloc[-1]
            sma_50 = df['SMA_50'].iloc[-1]
            
            # Calculate SMA strength based on ratio
            sma_ratio = sma_20 / sma_50 if sma_50 != 0 else 1.0
            sma_strength = abs(sma_ratio - 1.0)  # 0-1 scale, strongest when ratio differs most from 1
            
            if sma_20 > sma_50:
                sma_signal = "Buy"
                sma_confidence = 0.6
            else:
                sma_signal = "Sell"
                sma_confidence = 0.6
            
            signals["SMA"] = {
                "signal": sma_signal,
                "strength": sma_strength,
                "confidence": sma_confidence,
                "ratio": sma_ratio
            }
        
        # Calculate weighted overall signal
        buy_signals = []
        sell_signals = []
        
        for signal_name, signal_data in signals.items():
            # Get strength with default value if not present
            strength = signal_data.get("strength", 0.5)  # Default strength of 0.5
            confidence = signal_data.get("confidence", 0.5)  # Default confidence of 0.5
            
            if signal_data["signal"] == "Buy":
                buy_signals.append(strength * confidence)
            elif signal_data["signal"] == "Sell":
                sell_signals.append(strength * confidence)
        
        weighted_buy = sum(buy_signals) if buy_signals else 0
        weighted_sell = sum(sell_signals) if sell_signals else 0
        
        if weighted_buy > weighted_sell:
            overall_signal = "Buy"
            overall_confidence = weighted_buy / (weighted_buy + weighted_sell) if (weighted_buy + weighted_sell) > 0 else 0
        elif weighted_sell > weighted_buy:
            overall_signal = "Sell"
            overall_confidence = weighted_sell / (weighted_buy + weighted_sell) if (weighted_buy + weighted_sell) > 0 else 0
        else:
            overall_signal = "Hold"
            overall_confidence = 0.5
        
        return {
            "signals": signals,
            "overall_signal": overall_signal,
            "confidence": overall_confidence,
            "regime_adjusted": regime_info is not None
        }
    
    except Exception as e:
        print(f"Advanced trading signals error: {str(e)}")
        return {"error": str(e)}

def apply_financial_smoothing(data: np.ndarray, smoothing_type: str = "exponential", 
                            window_size: int = 5, alpha: float = 0.3, 
                            poly_order: int = 3, use_smoothing: bool = True) -> np.ndarray:
    """
    Apply financial smoothing algorithms to time series data.
    
    Args:
        data (np.ndarray): Input time series data
        smoothing_type (str): Type of smoothing to apply
            - 'exponential': Exponential moving average (good for trend following)
            - 'moving_average': Simple moving average (good for noise reduction)
            - 'kalman': Kalman filter (good for adaptive smoothing)
            - 'savitzky_golay': Savitzky-Golay filter (good for preserving peaks/valleys)
            - 'double_exponential': Double exponential smoothing (good for trend + seasonality)
            - 'triple_exponential': Triple exponential smoothing (Holt-Winters, good for complex patterns)
            - 'adaptive': Adaptive smoothing based on volatility
            - 'none': No smoothing applied
        window_size (int): Window size for moving average and Savitzky-Golay
        alpha (float): Smoothing factor for exponential methods (0-1)
        poly_order (int): Polynomial order for Savitzky-Golay filter
        use_smoothing (bool): Whether to apply smoothing
    
    Returns:
        np.ndarray: Smoothed data
    """
    if not use_smoothing or smoothing_type == "none" or len(data) < 3:
        return data
    
    try:
        if smoothing_type == "exponential":
            # Exponential Moving Average - good for trend following
            smoothed = np.zeros_like(data)
            smoothed[0] = data[0]
            for i in range(1, len(data)):
                smoothed[i] = alpha * data[i] + (1 - alpha) * smoothed[i-1]
            return smoothed
        
        elif smoothing_type == "moving_average":
            # Simple Moving Average - good for noise reduction
            if len(data) < window_size:
                return data
            
            smoothed = np.zeros_like(data)
            # Handle the beginning of the series
            for i in range(min(window_size - 1, len(data))):
                smoothed[i] = np.mean(data[:i+1])
            
            # Apply moving average for the rest
            for i in range(window_size - 1, len(data)):
                smoothed[i] = np.mean(data[i-window_size+1:i+1])
            return smoothed
        
        elif smoothing_type == "kalman":
            # Kalman Filter - adaptive smoothing
            if len(data) < 2:
                return data
            
            # Initialize Kalman filter parameters
            Q = 0.01  # Process noise
            R = 0.1   # Measurement noise
            P = 1.0   # Initial estimate error
            x = data[0]  # Initial state estimate
            
            smoothed = np.zeros_like(data)
            smoothed[0] = x
            
            for i in range(1, len(data)):
                # Prediction step
                x_pred = x
                P_pred = P + Q
                
                # Update step
                K = P_pred / (P_pred + R)  # Kalman gain
                x = x_pred + K * (data[i] - x_pred)
                P = (1 - K) * P_pred
                
                smoothed[i] = x
            
            return smoothed
        
        elif smoothing_type == "savitzky_golay":
            # Savitzky-Golay filter - preserves peaks and valleys
            if len(data) < window_size:
                return data
            
            # Ensure window_size is odd
            if window_size % 2 == 0:
                window_size += 1
            
            # Ensure polynomial order is less than window_size
            if poly_order >= window_size:
                poly_order = window_size - 1
            
            try:
                from scipy.signal import savgol_filter
                return savgol_filter(data, window_size, poly_order)
            except ImportError:
                # Fallback to simple moving average if scipy not available
                return apply_financial_smoothing(data, "moving_average", window_size)
        
        elif smoothing_type == "double_exponential":
            # Double Exponential Smoothing (Holt's method) - trend + level
            if len(data) < 3:
                return data
            
            smoothed = np.zeros_like(data)
            trend = np.zeros_like(data)
            
            # Initialize
            smoothed[0] = data[0]
            trend[0] = data[1] - data[0] if len(data) > 1 else 0
            
            # Apply double exponential smoothing
            for i in range(1, len(data)):
                prev_smoothed = smoothed[i-1]
                prev_trend = trend[i-1]
                
                smoothed[i] = alpha * data[i] + (1 - alpha) * (prev_smoothed + prev_trend)
                trend[i] = alpha * (smoothed[i] - prev_smoothed) + (1 - alpha) * prev_trend
            
            return smoothed
        
        elif smoothing_type == "triple_exponential":
            # Triple Exponential Smoothing (Holt-Winters) - trend + level + seasonality
            if len(data) < 6:
                return apply_financial_smoothing(data, "double_exponential", window_size, alpha)
            
            # For simplicity, we'll use a seasonal period of 5 (common for financial data)
            season_period = min(5, len(data) // 2)
            
            smoothed = np.zeros_like(data)
            trend = np.zeros_like(data)
            season = np.zeros_like(data)
            
            # Initialize
            smoothed[0] = data[0]
            trend[0] = (data[season_period] - data[0]) / season_period if len(data) > season_period else 0
            
            # Initialize seasonal components
            for i in range(season_period):
                season[i] = data[i] - smoothed[0]
            
            # Apply triple exponential smoothing
            for i in range(1, len(data)):
                prev_smoothed = smoothed[i-1]
                prev_trend = trend[i-1]
                prev_season = season[(i-1) % season_period]
                
                smoothed[i] = alpha * (data[i] - prev_season) + (1 - alpha) * (prev_smoothed + prev_trend)
                trend[i] = alpha * (smoothed[i] - prev_smoothed) + (1 - alpha) * prev_trend
                season[i % season_period] = alpha * (data[i] - smoothed[i]) + (1 - alpha) * prev_season
            
            return smoothed
        
        elif smoothing_type == "adaptive":
            # Adaptive smoothing based on volatility
            if len(data) < 5:
                return data
            
            # Calculate rolling volatility
            returns = np.diff(data) / data[:-1]
            volatility = np.zeros_like(data)
            volatility[0] = np.std(returns) if len(returns) > 0 else 0.01
            
            for i in range(1, len(data)):
                if i < 5:
                    volatility[i] = np.std(returns[:i]) if i > 0 else 0.01
                else:
                    volatility[i] = np.std(returns[i-5:i])
            
            # Normalize volatility to smoothing factor
            vol_factor = np.clip(volatility / np.mean(volatility), 0.1, 0.9)
            adaptive_alpha = 1 - vol_factor  # Higher volatility = less smoothing
            
            # Apply adaptive exponential smoothing
            smoothed = np.zeros_like(data)
            smoothed[0] = data[0]
            
            for i in range(1, len(data)):
                current_alpha = adaptive_alpha[i]
                smoothed[i] = current_alpha * data[i] + (1 - current_alpha) * smoothed[i-1]
            
            return smoothed
        
        else:
            # Default to exponential smoothing
            return apply_financial_smoothing(data, "exponential", window_size, alpha)
    
    except Exception as e:
        print(f"Smoothing error: {str(e)}")
        return data

# def create_interface():
#     """Create the Gradio interface with separate tabs for different timeframes"""
    
#     # Enhanced title and descriptions
#     title = """# 🙋🏻‍♂️Welcome to 🌟Tonic's  🚀 Stock Prediction with 📦Amazon ⌚Chronos
# ---
# """
    
#     description = """
# The **Advanced Stock Prediction System** is a cutting-edge AI-powered platform with **580M+ parameters**, designed to analyze and predict stock prices across multiple timeframes. Equipped with **Amazon's Chronos foundation model** and **advanced ensemble methods**, it excels in both short-term trading and long-term investment analysis. The system supports **multi-timeframe analysis**, **real-time market monitoring**, and **comprehensive risk assessment**, enhancing its versatility for all types of traders and investors.

# ### Key Features
# - **Multi-Timeframe Analysis**: Daily (up to 365 days), Hourly (up to 7 days), and 15-minute (up to 3 days) predictions
# - **Real-Time Market Status**: Check if markets are open with one-click monitoring
# - **Advanced Ensemble Methods**: Combines Chronos, Technical Analysis, and Statistical Models
# - **Enhanced Uncertainty Quantification**: Multiple uncertainty calculation methods for robust predictions
# - **Market Regime Detection**: Identifies bull, bear, and sideways market conditions
# - **Stress Testing**: Scenario analysis under various market conditions
# - **Sentiment Analysis**: News sentiment integration for enhanced predictions

# ## Supported Markets
# - **US Stock Market** (NYSE, NASDAQ, AMEX): 9:30 AM - 4:00 PM ET
# - **European Markets** (London, Frankfurt, Paris): 8:00 AM - 4:30 PM GMT  
# - **Asian Markets** (Tokyo, Hong Kong, Shanghai): 9:00 AM - 3:30 PM JST
# - **Forex Market** (24/7 Global Currency Exchange)
# - **Cryptocurrency Market** (24/7 Bitcoin, Ethereum, Altcoins)
# - **US Futures Market** (24/7 CME, ICE, CBOT)
# - **Commodities Market** (24/7 Gold, Silver, Oil, Natural Gas)
# """
    
#     model_info = """
# ## How to Use
# 1. **Market Status Check**: Use the dropdown to check if markets are open
# 2. **Select Analysis Type**: Choose from Daily, Hourly, or 15-minute analysis
# 3. **Enter Stock Symbol**: Input any valid stock symbol (e.g., AAPL, TSLA, GOOGL)
# 4. **Configure Parameters**: Adjust prediction days, lookback period, and advanced settings
# 5. **Click Analyze**: View comprehensive predictions with uncertainty estimates

# ## Model Information
# - **Core Model**: Amazon Chronos T5 Foundation Model
# - **Ensemble Methods**: Random Forest, Gradient Boosting, SVR, Neural Networks
# - **Technical Indicators**: RSI, MACD, Bollinger Bands, Moving Averages
# - **Risk Metrics**: Sharpe Ratio, VaR, Maximum Drawdown, Beta
# - **Data Sources**: Yahoo Finance, Market Indices, Economic Indicators
# - **Environment**: PyTorch 2.1.2 + CUDA Support + Advanced ML Libraries
# """
    
#     join_us = """
# ## Join the Community
# 🌟 **Advanced Stock Prediction** is continuously evolving! Join our active builder's community 👻 

# [![Join us on Discord](https://img.shields.io/discord/1109943800132010065?label=Discord&logo=discord&style=flat-square)](https://discord.gg/qdfnvSPcqP) 
# [![Hugging Face](https://img.shields.io/badge/Hugging%20Face-Open%20Source-blue?logo=huggingface&style=flat-square)](https://huggingface.co/TeamTonic) 
# [![GitHub](https://img.shields.io/badge/GitHub-Contribute-green?logo=github&style=flat-square)](https://github.com/Tonic-AI)

# 🤗Big thanks to Yuvi Sharma and all the folks at huggingface for the community grant 🤗
# """

#     with gr.Blocks(title="Advanced Stock Prediction Analysis", theme=gr.themes.Base()) as demo:
#         with gr.Row():
#             gr.Markdown(title)
        
#         with gr.Row():
#             with gr.Column(scale=1):
#                 with gr.Group():
#                     gr.Markdown(description)
#             with gr.Column(scale=1):
#                 with gr.Group():
#                     gr.Markdown(model_info)
#                     gr.Markdown(join_us)
        
#         gr.Markdown("---")  # Add a separator
        
#         # Add comprehensive market information section with nested accordions
#         with gr.Accordion("🌎 Global Market Information", open=False): 
#             # Quick Market Status Check Section
#             with gr.Accordion("📊 Quick Market Status Check", open=False):
#                 with gr.Column(scale=1):
#                     gr.Markdown("### 📊 Quick Market Status Check")
#                     # Create user-friendly market choices
#                     market_choices = [(config['name'], key) for key, config in MARKET_CONFIGS.items()]
#                     market_dropdown = gr.Dropdown(
#                         choices=market_choices,
#                         label="Select Market",
#                         value="US_STOCKS",
#                         info="Choose a market to check its current status"
#                     )
#                     check_market_btn = gr.Button("🔍 Check Market Status", variant="primary")
                
#                 with gr.Column(scale=2):
#                     market_status_result = gr.Markdown(
#                         value="Select a market and click 'Check Market Status' to see current trading status.",
#                         label="Market Status Result"
#                     )
#             # Enhanced Market Information Section
#             with gr.Accordion("🌍 Enhanced Market Information", open=False):
#                 with gr.Row():
#                     with gr.Column():
#                         gr.Markdown("### Market Summary")
#                         market_summary_display = gr.JSON(label="Market Summary", value={})
#                         def update_market_summary():
#                             """Update market summary with enhanced yfinance data"""
#                             return get_enhanced_market_summary()
#                         update_market_summary_btn = gr.Button("🔄 Update Market Summary")
#                         update_market_summary_btn.click(
#                             fn=update_market_summary,
#                             outputs=[market_summary_display]
#                         )
#                     with gr.Column():
#                         gr.Markdown("### Market Types Supported")
#                         gr.Markdown("""
#                         **📈 Stock Markets:**
#                         - **US Stocks** (NYSE, NASDAQ, AMEX): 9:30 AM - 4:00 PM ET
#                         - **European Markets** (London, Frankfurt, Paris): 8:00 AM - 4:30 PM GMT
#                         - **Asian Markets** (Tokyo, Hong Kong, Shanghai): 9:00 AM - 3:30 PM JST
                        
#                         **📊 24/7 Markets:**
#                         - **Forex** (Global Currency Exchange): 24/7 trading
#                         - **Cryptocurrency** (Bitcoin, Ethereum, Altcoins): 24/7 trading
#                         - **US Futures** (CME, ICE, CBOT): 24/7 trading
#                         - **Commodities** (Gold, Silver, Oil, Natural Gas): 24/7 trading
                        
#                         **💡 Features:**
#                         - Real-time market status updates every 10 minutes
#                         - Timezone-aware calculations
#                         - Market-specific trading hours
#                         - Enhanced data from yfinance API
#                         """)
        
#         # Connect the button to the function
#         check_market_btn.click(
#             fn=check_market_status_simple,
#             inputs=[market_dropdown],
#             outputs=[market_status_result]
#         )
        
#         # Advanced Settings Accordion
#         with gr.Accordion("Advanced Settings", open=False):
#             with gr.Row():
#                 with gr.Column():
#                     use_ensemble = gr.Checkbox(label="Use Ensemble Methods", value=True)
#                     use_regime_detection = gr.Checkbox(label="Use Regime Detection", value=True)
#                     use_stress_testing = gr.Checkbox(label="Use Stress Testing", value=True)
#                     use_covariates = gr.Checkbox(label="Use Enhanced Covariate Data", value=True, 
#                                                info="Include market indices, sectors, and economic indicators")
#                     use_sentiment = gr.Checkbox(label="Use Sentiment Analysis", value=True,
#                                               info="Include news sentiment analysis")
#                     use_smoothing = gr.Checkbox(label="Use Smoothing", value=True)
#                     smoothing_type = gr.Dropdown(
#                         choices=["exponential", "moving_average", "kalman", "savitzky_golay", 
#                                 "double_exponential", "triple_exponential", "adaptive", "none"],
#                         label="Smoothing Type",
#                         value="exponential",
#                         info="""Smoothing algorithms:
#                         • Exponential: Trend following (default)
#                         • Moving Average: Noise reduction
#                         • Kalman: Adaptive smoothing
#                         • Savitzky-Golay: Preserves peaks/valleys
#                         • Double Exponential: Trend + level
#                         • Triple Exponential: Complex patterns
#                         • Adaptive: Volatility-based
#                         • None: No smoothing"""
#                     )
#                     smoothing_window = gr.Slider(
#                         minimum=3,
#                         maximum=21,
#                         value=5,
#                         step=1,
#                         label="Smoothing Window Size",
#                         info="Window size for moving average and Savitzky-Golay filters"
#                     )
#                     smoothing_alpha = gr.Slider(
#                         minimum=0.1,
#                         maximum=0.9,
#                         value=0.3,
#                         step=0.05,
#                         label="Smoothing Alpha",
#                         info="Smoothing factor for exponential methods (0.1-0.9)"
#                     )
#                     risk_free_rate = gr.Slider(
#                         minimum=0.0,
#                         maximum=0.1,
#                         value=0.02,
#                         step=0.001,
#                         label="Risk-Free Rate (Annual)"
#                     )
#                     market_index = gr.Dropdown(
#                         choices=["^GSPC", "^DJI", "^IXIC", "^RUT"],
#                         label="Market Index for Correlation",
#                         value="^GSPC"
#                     )
#                     random_real_points = gr.Slider(
#                         minimum=0,
#                         maximum=16,
#                         value=4,
#                         step=1,
#                         label="Random Real Points in Long-Horizon Context"
#                     )
                
#                 with gr.Column():
#                     gr.Markdown("### Ensemble Weights")
#                     chronos_weight = gr.Slider(
#                         minimum=0.0,
#                         maximum=1.0,
#                         value=0.6,
#                         step=0.1,
#                         label="Chronos Weight"
#                     )
#                     technical_weight = gr.Slider(
#                         minimum=0.0,
#                         maximum=1.0,
#                         value=0.2,
#                         step=0.1,
#                         label="Technical Weight"
#                     )
#                     statistical_weight = gr.Slider(
#                         minimum=0.0,
#                         maximum=1.0,
#                         value=0.2,
#                         step=0.1,
#                         label="Statistical Weight"
#                     )
                    
#                     gr.Markdown("### Enhanced Features")
#                     gr.Markdown("""
#                     **New Enhanced Features:**
#                     - **Covariate Data**: Market indices, sector ETFs, commodities, currencies
#                     - **Sentiment Analysis**: News sentiment scoring and confidence
#                     - **Advanced Uncertainty**: Multiple uncertainty calculation methods
#                     - **Enhanced Volume Prediction**: Price-volume relationship modeling
#                     - **Regime-Aware Uncertainty**: Market condition adjustments
#                     - **Multi-Algorithm Ensemble**: Random Forest, Gradient Boosting, SVR, Neural Networks
#                     - **Real-Time Market Status**: Updates every 10 minutes with detailed timing information
#                     """)
        
#         with gr.Tabs() as tabs:
#             # Daily Analysis Tab
#             with gr.TabItem("Daily Analysis"):
#                 with gr.Row():
#                     with gr.Column():
#                         daily_symbol = gr.Textbox(label="Stock Symbol (e.g., AAPL)", value="AAPL")
#                         daily_prediction_days = gr.Slider(
#                             minimum=1,
#                             maximum=365,
#                             value=30,
#                             step=1,
#                             label="Days to Predict"
#                         )
#                         daily_lookback_days = gr.Slider(
#                             minimum=1,
#                             maximum=3650,
#                             value=365,
#                             step=1,
#                             label="Historical Lookback (Days)"
#                         )
#                         daily_strategy = gr.Dropdown(
#                             choices=["chronos", "technical"],
#                             label="Prediction Strategy",
#                             value="chronos"
#                         )
#                         daily_predict_btn = gr.Button("Analyze Stock")
#                         gr.Markdown("""
#                         **Daily Analysis Features:**
#                         - **Extended Data Range**: Up to 10 years of historical data (3650 days)
#                         - **24/7 Availability**: Available regardless of market hours
#                         - **Auto-Adjusted Data**: Automatically adjusted for splits and dividends
#                         - **Comprehensive Financial Ratios**: P/E, PEG, Price-to-Book, Price-to-Sales, and more
#                         - **Advanced Risk Metrics**: Sharpe ratio, VaR, drawdown analysis, market correlation
#                         - **Market Regime Detection**: Identifies bull/bear/sideways market conditions
#                         - **Stress Testing**: Scenario analysis under various market conditions
#                         - **Ensemble Methods**: Combines multiple prediction models for improved accuracy
#                         - **Maximum prediction period**: 365 days
#                         - **Ideal for**: Medium to long-term investment analysis, portfolio management, and strategic planning
#                         - **Technical Indicators**: RSI, MACD, Bollinger Bands, moving averages optimized for daily data
#                         - **Volume Analysis**: Average daily volume, volume volatility, and liquidity metrics
#                         - **Sector Analysis**: Industry classification, market cap ranking, and sector-specific metrics
#                         """)
                    
#                     with gr.Column():
#                         daily_plot = gr.Plot(label="Analysis and Prediction")
#                         daily_historical_json = gr.JSON(label="Historical Data")
#                         daily_predicted_json = gr.JSON(label="Predicted Data")
                
#                 with gr.Row():
#                     with gr.Column():
#                         gr.Markdown("### Structured Product Metrics")
#                         daily_metrics = gr.JSON(label="Product Metrics")
                        
#                         gr.Markdown("### Advanced Risk Analysis")
#                         daily_risk_metrics = gr.JSON(label="Risk Metrics")
                        
#                         gr.Markdown("### Market Regime Analysis")
#                         daily_regime_metrics = gr.JSON(label="Regime Metrics")
                        
#                         gr.Markdown("### Trading Signals")
#                         daily_signals = gr.JSON(label="Trading Signals")
                        
#                         gr.Markdown("### Advanced Trading Signals")
#                         daily_signals_advanced = gr.JSON(label="Advanced Trading Signals")
                    
#                     with gr.Column():
#                         gr.Markdown("### Sector & Financial Analysis")
#                         daily_sector_metrics = gr.JSON(label="Sector Metrics")
                        
#                         gr.Markdown("### Stress Test Results")
#                         daily_stress_results = gr.JSON(label="Stress Test Results")
                        
#                         gr.Markdown("### Ensemble Analysis")
#                         daily_ensemble_metrics = gr.JSON(label="Ensemble Metrics")
            
#             # Hourly Analysis Tab
#             with gr.TabItem("Hourly Analysis"):
#                 with gr.Row():
#                     with gr.Column():
#                         hourly_symbol = gr.Textbox(label="Stock Symbol (e.g., AAPL)", value="AAPL")
#                         hourly_prediction_days = gr.Slider(
#                             minimum=1,
#                             maximum=7,  # Limited to 7 days for hourly predictions
#                             value=3,
#                             step=1,
#                             label="Days to Predict"
#                         )
#                         hourly_lookback_days = gr.Slider(
#                             minimum=1,
#                             maximum=60,  # Enhanced to 60 days for hourly data
#                             value=14,
#                             step=1,
#                             label="Historical Lookback (Days)"
#                         )
#                         hourly_strategy = gr.Dropdown(
#                             choices=["chronos", "technical"],
#                             label="Prediction Strategy",
#                             value="chronos"
#                         )
#                         hourly_predict_btn = gr.Button("Analyze Stock")
#                         gr.Markdown("""
#                         **Hourly Analysis Features:**
#                         - **Extended Data Range**: Up to 60 days of historical data
#                         - **Pre/Post Market Data**: Includes extended hours trading data
#                         - **Auto-Adjusted Data**: Automatically adjusted for splits and dividends
#                         - **Metrics**: Intraday volatility, volume analysis, and momentum indicators
#                         - **Comprehensive Financial Ratios**: P/E, PEG, Price-to-Book, and more
#                         - **Maximum prediction period**: 7 days
#                         - **Data available during market hours only**
#                         """)
                    
#                     with gr.Column():
#                         hourly_plot = gr.Plot(label="Analysis and Prediction")
#                         hourly_signals = gr.JSON(label="Trading Signals")
#                         hourly_historical_json = gr.JSON(label="Historical Data")
#                         hourly_predicted_json = gr.JSON(label="Predicted Data")
                
#                 with gr.Row():
#                     with gr.Column():
#                         gr.Markdown("### Structured Product Metrics")
#                         hourly_metrics = gr.JSON(label="Product Metrics")
                        
#                         gr.Markdown("### Advanced Risk Analysis")
#                         hourly_risk_metrics = gr.JSON(label="Risk Metrics")
                        
#                         gr.Markdown("### Market Regime Analysis")
#                         hourly_regime_metrics = gr.JSON(label="Regime Metrics")
                        
#                         gr.Markdown("### Trading Signals")
#                         hourly_signals_advanced = gr.JSON(label="Advanced Trading Signals")
                    
#                     with gr.Column():
#                         gr.Markdown("### Sector & Financial Analysis")
#                         hourly_sector_metrics = gr.JSON(label="Sector Metrics")
                        
#                         gr.Markdown("### Stress Test Results")
#                         hourly_stress_results = gr.JSON(label="Stress Test Results")
                        
#                         gr.Markdown("### Ensemble Analysis")
#                         hourly_ensemble_metrics = gr.JSON(label="Ensemble Metrics")
            
#             # 15-Minute Analysis Tab
#             with gr.TabItem("15-Minute Analysis"):
#                 with gr.Row():
#                     with gr.Column():
#                         min15_symbol = gr.Textbox(label="Stock Symbol (e.g., AAPL)", value="AAPL")
#                         min15_prediction_days = gr.Slider(
#                             minimum=1,
#                             maximum=2,  # Limited to 2 days for 15-minute predictions
#                             value=1,
#                             step=1,
#                             label="Days to Predict"
#                         )
#                         min15_lookback_days = gr.Slider(
#                             minimum=1,
#                             maximum=7,  # 7 days for 15-minute data
#                             value=3,
#                             step=1,
#                             label="Historical Lookback (Days)"
#                         )
#                         min15_strategy = gr.Dropdown(
#                             choices=["chronos", "technical"],
#                             label="Prediction Strategy",
#                             value="chronos"
#                         )
#                         min15_predict_btn = gr.Button("Analyze Stock")
#                         gr.Markdown("""
#                         **15-Minute Analysis Features:**
#                         - **Data Range**: Up to 7 days of historical data (vs 5 days previously)
#                         - **High-Frequency Metrics**: Intraday volatility, volume-price trends, momentum analysis
#                         - **Pre/Post Market Data**: Includes extended hours trading data
#                         - **Auto-Adjusted Data**: Automatically adjusted for splits and dividends
#                         - **Enhanced Technical Indicators**: Optimized for short-term trading
#                         - **Maximum prediction period**: 2 days
#                         - **Requires at least 64 data points for Chronos predictions**
#                         - **Data available during market hours only**
#                         """)
                    
#                     with gr.Column():
#                         min15_plot = gr.Plot(label="Analysis and Prediction")
#                         min15_signals = gr.JSON(label="Trading Signals")
#                         min15_historical_json = gr.JSON(label="Historical Data")
#                         min15_predicted_json = gr.JSON(label="Predicted Data")
                
#                 with gr.Row():
#                     with gr.Column():
#                         gr.Markdown("### Structured Product Metrics")
#                         min15_metrics = gr.JSON(label="Product Metrics")
                        
#                         gr.Markdown("### Advanced Risk Analysis")
#                         min15_risk_metrics = gr.JSON(label="Risk Metrics")
                        
#                         gr.Markdown("### Market Regime Analysis")
#                         min15_regime_metrics = gr.JSON(label="Regime Metrics")
                        
#                         gr.Markdown("### Trading Signals")
#                         min15_signals_advanced = gr.JSON(label="Advanced Trading Signals")
                    
#                     with gr.Column():
#                         gr.Markdown("### Sector & Financial Analysis")
#                         min15_sector_metrics = gr.JSON(label="Sector Metrics")
                        
#                         gr.Markdown("### Stress Test Results")
#                         min15_stress_results = gr.JSON(label="Stress Test Results")
                        
#                         gr.Markdown("### Ensemble Analysis")
#                         min15_ensemble_metrics = gr.JSON(label="Ensemble Metrics")
        
#         def analyze_stock(symbol, timeframe, prediction_days, lookback_days, strategy,
#                          use_ensemble, use_regime_detection, use_stress_testing,
#                          risk_free_rate, market_index, chronos_weight, technical_weight, statistical_weight,
#                          random_real_points, use_smoothing, smoothing_type, smoothing_window, smoothing_alpha,
#                          use_covariates=True, use_sentiment=True):
#             try:
#                 # Create ensemble weights
#                 ensemble_weights = {
#                     "chronos": chronos_weight,
#                     "technical": technical_weight,
#                     "statistical": statistical_weight
#                 }
                
#                 # Get market data for correlation analysis
#                 market_df = get_market_data(market_index, lookback_days)
#                 market_returns = market_df['Returns'] if not market_df.empty else None
                
#                 # Make prediction with enhanced features
#                 signals, fig = make_prediction_enhanced(
#                     symbol=symbol,
#                     timeframe=timeframe,
#                     prediction_days=prediction_days,
#                     strategy=strategy,
#                     use_ensemble=use_ensemble,
#                     use_regime_detection=use_regime_detection,
#                     use_stress_testing=use_stress_testing,
#                     risk_free_rate=risk_free_rate,
#                     ensemble_weights=ensemble_weights,
#                     market_index=market_index,
#                     use_covariates=use_covariates,
#                     use_sentiment=use_sentiment,
#                     random_real_points=random_real_points,
#                     use_smoothing=use_smoothing,
#                     smoothing_type=smoothing_type,
#                     smoothing_window=smoothing_window,
#                     smoothing_alpha=smoothing_alpha
#                 )
                
#                 # Get historical data for additional metrics
#                 df = get_historical_data(symbol, timeframe, lookback_days)
                
#                 # Fetch fundamental data from yfinance info property
#                 fundamentals = get_fundamental_data(symbol)
                
#                 # Calculate structured product metrics using fundamentals and price data
#                 product_metrics = {
#                     "Market_Cap": fundamentals.get("marketCap"),
#                     "Sector": fundamentals.get("sector"),
#                     "Industry": fundamentals.get("industry"),
#                     "Dividend_Yield": fundamentals.get("dividendYield"),
#                     "Avg_Daily_Volume": fundamentals.get("averageDailyVolume"),
#                     "Volume_Volatility": df['Volume'].rolling(window=20, min_periods=1).std().iloc[-1] if 'Volume' in df.columns else None,
#                     "Enterprise_Value": fundamentals.get("enterpriseValue"),
#                     "P/E_Ratio": fundamentals.get("trailingPE"),
#                     "Forward_P/E": fundamentals.get("forwardPE"),
#                     "PEG_Ratio": fundamentals.get("pegRatio"),
#                     "Price_to_Book": fundamentals.get("priceToBook"),
#                     "Price_to_Sales": fundamentals.get("priceToSalesTrailing12Months"),
#                 }
                
#                 # Calculate advanced risk metrics
#                 risk_metrics = calculate_advanced_risk_metrics(df, market_returns, risk_free_rate)
                
#                 # Calculate sector metrics using fundamentals
#                 sector_metrics = {
#                     "Sector": fundamentals.get("sector"),
#                     "Industry": fundamentals.get("industry"),
#                     "Market_Cap_Rank": "Large" if fundamentals.get("marketCap", 0) > 1e10 else "Mid" if fundamentals.get("marketCap", 0) > 1e9 else "Small",
#                     "Liquidity_Score": "High" if fundamentals.get("averageDailyVolume", 0) > 1e6 else "Medium" if fundamentals.get("averageDailyVolume", 0) > 1e5 else "Low",
#                     "Gross_Margin": fundamentals.get("grossMargins"),
#                     "Operating_Margin": fundamentals.get("operatingMargins"),
#                     "Net_Margin": fundamentals.get("netMargins"),
#                 }
                
#                 # Add enhanced features information
#                 enhanced_metrics = {
#                     "covariate_data_used": signals.get("covariate_data_available", False),
#                     "sentiment_analysis_used": use_sentiment,
#                     "advanced_uncertainty_methods": list(signals.get("advanced_uncertainties", {}).keys()),
#                     "regime_aware_uncertainty": use_regime_detection,
#                     "enhanced_volume_prediction": signals.get("prediction", {}).get("volume") is not None
#                 }
                
#                 Add intraday-specific metrics for shorter timeframes
#                 if timeframe in ["1h", "15m"]:
#                     intraday_metrics = {
#                         "Intraday_Volatility": df['Intraday_Volatility'].iloc[-1] if 'Intraday_Volatility' in df.columns else 0,
#                         "Volume_Ratio": df['Volume_Ratio'].iloc[-1] if 'Volume_Ratio' in df.columns else 0,
#                         "Price_Momentum": df['Price_Momentum'].iloc[-1] if 'Price_Momentum' in df.columns else 0,
#                         "Volume_Momentum": df['Volume_Momentum'].iloc[-1] if 'Volume_Momentum' in df.columns else 0,
#                         "Volume_Price_Trend": df['Volume_Price_Trend'].iloc[-1] if 'Volume_Price_Trend' in df.columns else 0
#                     }
#                     product_metrics.update(intraday_metrics)
                
#                 # Extract regime and stress test information
#                 regime_metrics = signals.get("regime_info", {})
#                 stress_results = signals.get("stress_test_results", {})
#                 ensemble_metrics = {
#                     "ensemble_used": signals.get("ensemble_used", False),
#                     "ensemble_weights": ensemble_weights,
#                     "enhanced_features": enhanced_metrics
#                 }
                
#                 # Separate basic and advanced signals
#                 basic_signals = {
#                     "RSI": signals.get("RSI", "Neutral"),
#                     "MACD": signals.get("MACD", "Hold"),
#                     "Bollinger": signals.get("Bollinger", "Hold"),
#                     "SMA": signals.get("SMA", "Hold"),
#                     "Overall": signals.get("Overall", "Hold"),
#                     "symbol": signals.get("symbol", symbol),
#                     "timeframe": signals.get("timeframe", timeframe),
#                     "strategy_used": signals.get("strategy_used", strategy)
#                 }
                
#                 advanced_signals = signals.get("advanced_signals", {})
                
#                 # In analyze_stock, extract historical and predicted values for UI
#                 historical = signals.get('historical', {})
#                 predicted = signals.get('prediction', {})
                
#                 return basic_signals, fig, product_metrics, risk_metrics, sector_metrics, regime_metrics, stress_results, ensemble_metrics, advanced_signals, historical, predicted
#             except Exception as e:
#                 error_message = str(e)
#                 if "Market is currently closed" in error_message:
#                     error_message = f"{error_message}. Please try again during market hours or use daily timeframe."
#                 elif "Insufficient data points" in error_message:
#                     error_message = f"Not enough data available for {symbol} in {timeframe} timeframe. Please try a different timeframe or symbol."
#                 elif "no price data found" in error_message:
#                     error_message = f"No data available for {symbol} in {timeframe} timeframe. Please try a different timeframe or symbol."
#                 raise gr.Error(error_message)
        
#         # Daily analysis button click
#         def daily_analysis(s: str, pd: int, ld: int, st: str, ue: bool, urd: bool, ust: bool,
#                           rfr: float, mi: str, cw: float, tw: float, sw: float,
#                           rrp: int, usm: bool, smt: str, sww: float, sa: float,
#                           uc: bool, us: bool) -> Tuple[Dict, go.Figure, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict]:
#             """
#             Process daily timeframe stock analysis with enhanced features.

#             This function performs comprehensive stock analysis using daily data with support for
#             multiple prediction strategies, ensemble methods, regime detection, stress testing,
#             covariate data, and sentiment analysis. It's designed for medium to long-term investment 
#             analysis with up to 365 days of prediction.

#             Args:
#                 s (str): Stock Symbol (e.g., AAPL) - The input value from the "Stock Symbol" Textbox component
#                 pd (int): Days to Predict - The input value from the "Days to Predict" Slider component (1-365)
#                 ld (int): Historical Lookback (Days) - The input value from the "Historical Lookback (Days)" Slider component (1-3650)
#                 st (str): Prediction Strategy - The input value from the "Prediction Strategy" Dropdown component
#                     Options: "chronos" (uses Amazon's Chronos T5 model) or "technical" (traditional technical analysis)
#                 ue (bool): Use Ensemble Methods - The input value from the "Use Ensemble Methods" Checkbox component
#                     When True, combines multiple prediction models for improved accuracy
#                 urd (bool): Use Regime Detection - The input value from the "Use Regime Detection" Checkbox component
#                     When True, detects market regimes (bull/bear/sideways) to adjust predictions
#                 ust (bool): Use Stress Testing - The input value from the "Use Stress Testing" Checkbox component
#                     When True, performs scenario analysis under various market conditions
#                 rfr (float): Risk-Free Rate (Annual) - The input value from the "Risk-Free Rate (Annual)" Slider component (0.0-0.1)
#                     Annual risk-free rate used for risk-adjusted return calculations
#                 mi (str): Market Index for Correlation - The input value from the "Market Index for Correlation" Dropdown component
#                     Options: "^GSPC" (S&P 500), "^DJI" (Dow Jones), "^IXIC" (NASDAQ), "^RUT" (Russell 2000)
#                 cw (float): Chronos Weight - The input value from the "Chronos Weight" Slider component (0.0-1.0)
#                     Weight given to Chronos model predictions in ensemble methods
#                 tw (float): Technical Weight - The input value from the "Technical Weight" Slider component (0.0-1.0)
#                     Weight given to technical analysis predictions in ensemble methods
#                 sw (float): Statistical Weight - The input value from the "Statistical Weight" Slider component (0.0-1.0)
#                     Weight given to statistical model predictions in ensemble methods
#                 rrp (int): Random Real Points in Long-Horizon Context - The input value from the "Random Real Points in Long-Horizon Context" Slider component
#                     Number of random real points to include in long-horizon context for improved predictions
#                 usm (bool): Use Smoothing - The input value from the "Use Smoothing" Checkbox component
#                     When True, applies smoothing to predictions to reduce noise and improve continuity
#                 smt (str): Smoothing Type - The input value from the "Smoothing Type" Dropdown component
#                     Options: "exponential", "moving_average", "kalman", "savitzky_golay", "double_exponential", "triple_exponential", "adaptive", "none"
#                 sww (float): Smoothing Window Size - The input value from the "Smoothing Window Size" Slider component
#                     Window size for moving average and Savitzky-Golay smoothing methods
#                 sa (float): Smoothing Alpha - The input value from the "Smoothing Alpha" Slider component (0.1-0.9)
#                     Alpha parameter for exponential smoothing methods
#                 uc (bool): Use Enhanced Covariate Data - The input value from the "Use Enhanced Covariate Data" Checkbox component
#                     When True, includes market indices, sectors, and economic indicators in analysis
#                 us (bool): Use Sentiment Analysis - The input value from the "Use Sentiment Analysis" Checkbox component
#                     When True, includes news sentiment analysis in the prediction model

#             Returns:
#                 Tuple[Dict, go.Figure, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict]: Analysis results containing:
#                     [0] Dict: Trading Signals - Output value for the "Trading Signals" Json component
#                         Contains RSI, MACD, Bollinger Bands, SMA, and overall trading signals
#                     [1] go.Figure: Analysis and Prediction - Output value for the "Analysis and Prediction" Plot component
#                         Interactive plot with historical data, predictions, and confidence intervals
#                     [2] Dict: Product Metrics - Output value for the "Product Metrics" Json component
#                         Structured product metrics including Market Cap, P/E ratios, and financial ratios
#                     [3] Dict: Risk Metrics - Output value for the "Risk Metrics" Json component
#                         Advanced risk metrics including Sharpe ratio, VaR, drawdown, and correlation analysis
#                     [4] Dict: Sector Metrics - Output value for the "Sector Metrics" Json component
#                         Sector and industry analysis metrics
#                     [5] Dict: Regime Metrics - Output value for the "Regime Metrics" Json component
#                         Market regime detection results and analysis
#                     [6] Dict: Stress Test Results - Output value for the "Stress Test Results" Json component
#                         Stress testing scenario results under various market conditions
#                     [7] Dict: Ensemble Metrics - Output value for the "Ensemble Metrics" Json component
#                         Ensemble method configuration and performance results
#                     [8] Dict: Advanced Trading Signals - Output value for the "Advanced Trading Signals" Json component
#                         Advanced trading signals with confidence levels and sophisticated indicators
#                     [9] Dict: Historical Data - Output value for the "Historical Data" Json component
#                         Historical data for the selected stock
#                     [10] Dict: Predicted Data - Output value for the "Predicted Data" Json component
#                         Predicted data for the selected stock

#             Raises:
#                 gr.Error: If data cannot be fetched, insufficient data points, or other analysis errors
#                     Common errors include invalid symbols, market closure, or insufficient historical data

#             Example:
#                 >>> signals, plot, metrics, risk, sector, regime, stress, ensemble, advanced, historical, predicted = daily_analysis(
#                 ...     "AAPL", 30, 365, "chronos", True, True, True, 0.02, "^GSPC", 0.6, 0.2, 0.2, 4, True, "exponential", 5, 0.3, True, True
#                 ... )

#             Notes:
#                 - Daily analysis is available 24/7 regardless of market hours
#                 - Maximum prediction period is 365 days
#                 - Historical data can go back up to 10 years (3650 days)
#                 - Ensemble weights (cw + tw + sw) should sum to 1.0 for optimal results
#                 - Risk-free rate is typically between 0.02-0.05 (2-5% annually)
#                 - Smoothing helps reduce prediction noise but may reduce responsiveness to sudden changes
#                 - Enhanced covariate data includes market indices, sector ETFs, commodities, and currencies
#                 - Sentiment analysis provides news sentiment scoring and confidence levels
#             """
#             return analyze_stock(s, "1d", pd, ld, st, ue, urd, ust, rfr, mi, cw, tw, sw, rrp, usm, smt, sww, sa, uc, us)

#         daily_predict_btn.click(
#             fn=daily_analysis,
#             inputs=[daily_symbol, daily_prediction_days, daily_lookback_days, daily_strategy,
#                    use_ensemble, use_regime_detection, use_stress_testing, risk_free_rate, market_index,
#                    chronos_weight, technical_weight, statistical_weight,
#                    random_real_points, use_smoothing, smoothing_type, smoothing_window, smoothing_alpha,
#                    use_covariates, use_sentiment],
#             outputs=[daily_signals, daily_plot, daily_metrics, daily_risk_metrics, daily_sector_metrics,
#                     daily_regime_metrics, daily_stress_results, daily_ensemble_metrics, daily_signals_advanced, daily_historical_json, daily_predicted_json]
#         )
        
#         # Hourly analysis button click
#         def hourly_analysis(s: str, pd: int, ld: int, st: str, ue: bool, urd: bool, ust: bool,
#                            rfr: float, mi: str, cw: float, tw: float, sw: float,
#                            rrp: int, usm: bool, smt: str, sww: float, sa: float,
#                            uc: bool, us: bool) -> Tuple[Dict, go.Figure, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict]:
#             """
#             Process hourly timeframe stock analysis with enhanced features.

#             This function performs high-frequency stock analysis using hourly data, ideal for
#             short to medium-term trading strategies. It includes intraday volatility analysis,
#             volume-price trends, momentum indicators, covariate data, and sentiment analysis
#             optimized for hourly timeframes.

#             Args:
#                 s (str): Stock Symbol (e.g., AAPL) - The input value from the "Stock Symbol" Textbox component
#                 pd (int): Days to Predict - The input value from the "Days to Predict" Slider component (1-7)
#                     Limited to 7 days due to Yahoo Finance hourly data constraints
#                 ld (int): Historical Lookback (Days) - The input value from the "Historical Lookback (Days)" Slider component (1-60)
#                     Enhanced to 60 days for hourly data (vs standard 30 days)
#                 st (str): Prediction Strategy - The input value from the "Prediction Strategy" Dropdown component
#                     Options: "chronos" (uses Amazon's Chronos T5 model optimized for hourly data) or "technical" (technical indicators adjusted for hourly timeframes)
#                 ue (bool): Use Ensemble Methods - The input value from the "Use Ensemble Methods" Checkbox component
#                     Combines multiple models for improved short-term prediction accuracy
#                 urd (bool): Use Regime Detection - The input value from the "Use Regime Detection" Checkbox component
#                     Detects intraday market regimes and volatility patterns
#                 ust (bool): Use Stress Testing - The input value from the "Use Stress Testing" Checkbox component
#                     Performs scenario analysis for short-term market shocks
#                 rfr (float): Risk-Free Rate (Annual) - The input value from the "Risk-Free Rate (Annual)" Slider component (0.0-0.1)
#                     Annual risk-free rate for risk-adjusted calculations
#                 mi (str): Market Index for Correlation - The input value from the "Market Index for Correlation" Dropdown component
#                     Options: "^GSPC" (S&P 500), "^DJI" (Dow Jones), "^IXIC" (NASDAQ), "^RUT" (Russell 2000)
#                 cw (float): Chronos Weight - The input value from the "Chronos Weight" Slider component (0.0-1.0)
#                     Weight for Chronos model in ensemble predictions
#                 tw (float): Technical Weight - The input value from the "Technical Weight" Slider component (0.0-1.0)
#                     Weight for technical analysis in ensemble predictions
#                 sw (float): Statistical Weight - The input value from the "Statistical Weight" Slider component (0.0-1.0)
#                     Weight for statistical models in ensemble predictions
#                 rrp (int): Random Real Points in Long-Horizon Context - The input value from the "Random Real Points in Long-Horizon Context" Slider component
#                     Number of random real points to include in long-horizon context for improved predictions
#                 usm (bool): Use Smoothing - The input value from the "Use Smoothing" Checkbox component
#                     When True, applies smoothing to predictions to reduce noise and improve continuity
#                 smt (str): Smoothing Type - The input value from the "Smoothing Type" Dropdown component
#                     Options: "exponential", "moving_average", "kalman", "savitzky_golay", "double_exponential", "triple_exponential", "adaptive", "none"
#                 sww (float): Smoothing Window Size - The input value from the "Smoothing Window Size" Slider component
#                     Window size for moving average and Savitzky-Golay smoothing methods
#                 sa (float): Smoothing Alpha - The input value from the "Smoothing Alpha" Slider component (0.1-0.9)
#                     Alpha parameter for exponential smoothing methods
#                 uc (bool): Use Enhanced Covariate Data - The input value from the "Use Enhanced Covariate Data" Checkbox component
#                     When True, includes market indices, sectors, and economic indicators in analysis
#                 us (bool): Use Sentiment Analysis - The input value from the "Use Sentiment Analysis" Checkbox component
#                     When True, includes news sentiment analysis in the prediction model

#             Returns:
#                 Tuple[Dict, go.Figure, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict]: Analysis results containing:
#                     [0] Dict: Trading Signals - Output value for the "Trading Signals" Json component
#                         Basic trading signals optimized for hourly timeframes
#                     [1] go.Figure: Analysis and Prediction - Output value for the "Analysis and Prediction" Plot component
#                         Interactive plot with hourly data, predictions, and intraday patterns
#                     [2] Dict: Product Metrics - Output value for the "Product Metrics" Json component
#                         Product metrics including intraday volatility and volume analysis
#                     [3] Dict: Risk Metrics - Output value for the "Risk Metrics" Json component
#                         Risk metrics adjusted for hourly data frequency
#                     [4] Dict: Sector Metrics - Output value for the "Sector Metrics" Json component
#                         Sector analysis with intraday-specific metrics
#                     [5] Dict: Regime Metrics - Output value for the "Regime Metrics" Json component
#                         Market regime detection for hourly patterns
#                     [6] Dict: Stress Test Results - Output value for the "Stress Test Results" Json component
#                         Stress testing results for short-term scenarios
#                     [7] Dict: Ensemble Metrics - Output value for the "Ensemble Metrics" Json component
#                         Ensemble analysis configuration and results
#                     [8] Dict: Advanced Trading Signals - Output value for the "Advanced Trading Signals" Json component
#                         Advanced signals with intraday-specific indicators
#                     [9] Dict: Historical Data - Output value for the "Historical Data" Json component
#                         Historical data for the selected stock
#                     [10] Dict: Predicted Data - Output value for the "Predicted Data" Json component
#                         Predicted data for the selected stock

#             Raises:
#                 gr.Error: If market is closed, insufficient data, or analysis errors
#                     Hourly data is only available during market hours (9:30 AM - 4:00 PM ET)

#             Example:
#                 >>> signals, plot, metrics, risk, sector, regime, stress, ensemble, advanced, historical, predicted = hourly_analysis(
#                 ...     "AAPL", 3, 14, "chronos", True, True, True, 0.02, "^GSPC", 0.6, 0.2, 0.2, 4, True, "exponential", 5, 0.3, True, True
#                 ... )

#             Notes:
#                 - Only available during market hours (9:30 AM - 4:00 PM ET, weekdays)
#                 - Maximum prediction period is 7 days (168 hours)
#                 - Historical data limited to 60 days due to Yahoo Finance constraints
#                 - Includes pre/post market data for extended hours analysis
#                 - Optimized for day trading and swing trading strategies
#                 - Requires high-liquidity stocks for reliable hourly analysis
#                 - Smoothing helps reduce prediction noise but may reduce responsiveness to sudden changes
#                 - Enhanced covariate data includes market indices, sector ETFs, commodities, and currencies
#                 - Sentiment analysis provides news sentiment scoring and confidence levels
#             """
#             return analyze_stock(s, "1h", pd, ld, st, ue, urd, ust, rfr, mi, cw, tw, sw, rrp, usm, smt, sww, sa, uc, us)

#         hourly_predict_btn.click(
#             fn=hourly_analysis,
#             inputs=[hourly_symbol, hourly_prediction_days, hourly_lookback_days, hourly_strategy,
#                    use_ensemble, use_regime_detection, use_stress_testing, risk_free_rate, market_index,
#                    chronos_weight, technical_weight, statistical_weight,
#                    random_real_points, use_smoothing, smoothing_type, smoothing_window, smoothing_alpha,
#                    use_covariates, use_sentiment],
#             outputs=[hourly_signals, hourly_plot, hourly_metrics, hourly_risk_metrics, hourly_sector_metrics,
#                     hourly_regime_metrics, hourly_stress_results, hourly_ensemble_metrics, hourly_signals_advanced, hourly_historical_json, hourly_predicted_json]
#         )
        
#         # 15-minute analysis button click
#         def min15_analysis(s: str, pd: int, ld: int, st: str, ue: bool, urd: bool, ust: bool,
#                           rfr: float, mi: str, cw: float, tw: float, sw: float,
#                           rrp: int, usm: bool, smt: str, sww: float, sa: float,
#                           uc: bool, us: bool) -> Tuple[Dict, go.Figure, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict]:
#             """
#             Process 15-minute timeframe stock analysis with enhanced features.

#             This function performs ultra-high-frequency stock analysis using 15-minute data, ideal for
#             scalping and very short-term trading strategies. It includes micro-volatility analysis,
#             volume-price relationships, momentum indicators, covariate data, and sentiment analysis
#             optimized for 15-minute timeframes.

#             Args:
#                 s (str): Stock Symbol (e.g., AAPL) - The input value from the "Stock Symbol" Textbox component
#                 pd (int): Days to Predict - The input value from the "Days to Predict" Slider component (1-3)
#                     Limited to 3 days due to Yahoo Finance 15-minute data constraints
#                 ld (int): Historical Lookback (Days) - The input value from the "Historical Lookback (Days)" Slider component (1-7)
#                     Limited to 7 days for 15-minute data
#                 st (str): Prediction Strategy - The input value from the "Prediction Strategy" Dropdown component
#                     Options: "chronos" (uses Amazon's Chronos T5 model optimized for 15-minute data) or "technical" (technical indicators adjusted for 15-minute timeframes)
#                 ue (bool): Use Ensemble Methods - The input value from the "Use Ensemble Methods" Checkbox component
#                     Combines multiple models for improved ultra-short-term prediction accuracy
#                 urd (bool): Use Regime Detection - The input value from the "Use Regime Detection" Checkbox component
#                     Detects micro-market regimes and volatility patterns
#                 ust (bool): Use Stress Testing - The input value from the "Use Stress Testing" Checkbox component
#                     Performs scenario analysis for micro-market shocks
#                     Performs scenario analysis for intraday market shocks and volatility spikes
#                 rfr (float): Risk-Free Rate (Annual) - The input value from the "Risk-Free Rate (Annual)" Slider component (0.0-0.1)
#                     Annual risk-free rate for risk-adjusted calculations (less relevant for 15m analysis)
#                 mi (str): Market Index for Correlation - The input value from the "Market Index for Correlation" Dropdown component
#                     Options: "^GSPC" (S&P 500), "^DJI" (Dow Jones), "^IXIC" (NASDAQ), "^RUT" (Russell 2000)
#                 cw (float): Chronos Weight - The input value from the "Chronos Weight" Slider component (0.0-1.0)
#                     Weight for Chronos model in ensemble predictions
#                 tw (float): Technical Weight - The input value from the "Technical Weight" Slider component (0.0-1.0)
#                     Weight for technical analysis in ensemble predictions
#                 sw (float): Statistical Weight - The input value from the "Statistical Weight" Slider component (0.0-1.0)
#                     Weight for statistical models in ensemble predictions
#                 rrp (int): Random Real Points in Long-Horizon Context - The input value from the "Random Real Points in Long-Horizon Context" Slider component
#                     Number of random real points to include in long-horizon context for improved predictions
#                 usm (bool): Use Smoothing - The input value from the "Use Smoothing" Checkbox component
#                     When True, applies smoothing to predictions to reduce noise and improve continuity
#                 smt (str): Smoothing Type - The input value from the "Smoothing Type" Dropdown component
#                     Options: "exponential", "moving_average", "kalman", "savitzky_golay", "double_exponential", "triple_exponential", "adaptive", "none"
#                 sww (float): Smoothing Window Size - The input value from the "Smoothing Window Size" Slider component
#                     Window size for moving average and Savitzky-Golay smoothing methods
#                 sa (float): Smoothing Alpha - The input value from the "Smoothing Alpha" Slider component (0.1-0.9)
#                     Alpha parameter for exponential smoothing methods

#             Returns:
#                 Tuple[Dict, go.Figure, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict, Dict]: Analysis results containing:
#                     [0] Dict: Trading Signals - Output value for the "Trading Signals" Json component
#                         Basic trading signals optimized for 15-minute timeframes
#                     [1] go.Figure: Analysis and Prediction - Output value for the "Analysis and Prediction" Plot component
#                         Interactive plot with 15-minute data, predictions, and micro-patterns
#                     [2] Dict: Product Metrics - Output value for the "Product Metrics" Json component
#                         Product metrics including high-frequency volatility and volume analysis
#                     [3] Dict: Risk Metrics - Output value for the "Risk Metrics" Json component
#                         Risk metrics adjusted for 15-minute data frequency
#                     [4] Dict: Sector Metrics - Output value for the "Sector Metrics" Json component
#                         Sector analysis with ultra-short-term metrics
#                     [5] Dict: Regime Metrics - Output value for the "Regime Metrics" Json component
#                         Market regime detection for 15-minute patterns
#                     [6] Dict: Stress Test Results - Output value for the "Stress Test Results" Json component
#                         Stress testing results for intraday scenarios
#                     [7] Dict: Ensemble Metrics - Output value for the "Ensemble Metrics" Json component
#                         Ensemble analysis configuration and results
#                     [8] Dict: Advanced Trading Signals - Output value for the "Advanced Trading Signals" Json component
#                         Advanced signals with 15-minute-specific indicators
#                     [9] Dict: Historical Data - Output value for the "Historical Data" Json component
#                         Historical data for the selected stock
#                     [10] Dict: Predicted Data - Output value for the "Predicted Data" Json component
#                         Predicted data for the selected stock

#             Raises:
#                 gr.Error: If market is closed, insufficient data points, or analysis errors
#                     15-minute data requires at least 64 data points and is only available during market hours

#             Example:
#                 >>> signals, plot, metrics, risk, sector, regime, stress, ensemble, advanced, historical, predicted = min15_analysis(
#                 ...     "AAPL", 1, 3, "chronos", True, True, True, 0.02, "^GSPC", 0.6, 0.2, 0.2, 4, True, "exponential", 5, 0.3
#                 ... )

#             Notes:
#                 - Only available during market hours (9:30 AM - 4:00 PM ET, weekdays)
#                 - Maximum prediction period is 2 days (192 15-minute intervals)
#                 - Historical data limited to 7 days due to Yahoo Finance constraints
#                 - Requires minimum 64 data points for reliable Chronos predictions
#                 - Optimized for scalping and very short-term trading strategies
#                 - Includes specialized indicators for intraday momentum and volume analysis
#                 - Higher transaction costs and slippage considerations for 15-minute strategies
#                 - Best suited for highly liquid large-cap stocks with tight bid-ask spreads
#                 - Smoothing helps reduce prediction noise but may reduce responsiveness to sudden changes
#             """
#             return analyze_stock(s, "15m", pd, ld, st, ue, urd, ust, rfr, mi, cw, tw, sw, rrp, usm, smt, sww, sa)

#         min15_predict_btn.click(
#             fn=min15_analysis,
#             inputs=[min15_symbol, min15_prediction_days, min15_lookback_days, min15_strategy,
#                    use_ensemble, use_regime_detection, use_stress_testing, risk_free_rate, market_index,
#                    chronos_weight, technical_weight, statistical_weight,
#                    random_real_points, use_smoothing, smoothing_type, smoothing_window, smoothing_alpha],
#             outputs=[min15_signals, min15_plot, min15_metrics, min15_risk_metrics, min15_sector_metrics,
#                     min15_regime_metrics, min15_stress_results, min15_ensemble_metrics, min15_signals_advanced, min15_historical_json, min15_predicted_json]
#         )
    
#     return demo

def get_enhanced_covariate_data(symbol: str, timeframe: str = "1d", lookback_days: int = 365) -> Dict[str, pd.DataFrame]:
    """
    Collect enhanced covariate data including market indices, sectors, commodities, and economic indicators.
    
    Args:
        symbol (str): Stock symbol
        timeframe (str): Data timeframe
        lookback_days (int): Number of days to look back
    
    Returns:
        Dict[str, pd.DataFrame]: Dictionary of covariate dataframes
    """
    try:
        covariate_data = {}
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days)
        
        # Collect market indices data
        print("Collecting market indices data...")
        market_data = {}
        for index in COVARIATE_SOURCES['market_indices']:
            try:
                ticker = yf.Ticker(index)
                data = retry_yfinance_request(lambda: ticker.history(
                    start=start_date, end=end_date, interval=timeframe
                ))
                if not data.empty:
                    market_data[index] = data['Close']
                    print(f"  Successfully collected {index}: {len(data)} data points")
                else:
                    print(f"  No data for {index}")
            except Exception as e:
                print(f"  Error fetching {index}: {str(e)}")
                # Continue with other indices even if one fails
        
        if market_data:
            covariate_data['market_indices'] = pd.DataFrame(market_data)
            print(f"Market indices data shape: {covariate_data['market_indices'].shape}")
        else:
            print("No market indices data collected")
        
        # Collect sector data
        print("Collecting sector data...")
        sector_data = {}
        for sector in COVARIATE_SOURCES['sectors']:
            try:
                ticker = yf.Ticker(sector)
                data = retry_yfinance_request(lambda: ticker.history(
                    start=start_date, end=end_date, interval=timeframe
                ))
                if not data.empty:
                    sector_data[sector] = data['Close']
                    print(f"  Successfully collected {sector}: {len(data)} data points")
                else:
                    print(f"  No data for {sector}")
            except Exception as e:
                print(f"  Error fetching {sector}: {str(e)}")
                # Continue with other sectors even if one fails
        
        if sector_data:
            covariate_data['sectors'] = pd.DataFrame(sector_data)
            print(f"Sector data shape: {covariate_data['sectors'].shape}")
        else:
            print("No sector data collected")
        
        # Collect economic indicators
        print("Collecting economic indicators...")
        economic_data = {}
        for indicator, ticker_symbol in ECONOMIC_INDICATORS.items():
            try:
                ticker = yf.Ticker(ticker_symbol)
                data = retry_yfinance_request(lambda: ticker.history(
                    start=start_date, end=end_date, interval=timeframe
                ))
                if not data.empty:
                    economic_data[indicator] = data['Close']
                    print(f"  Successfully collected {indicator} ({ticker_symbol}): {len(data)} data points")
                else:
                    print(f"  No data for {indicator} ({ticker_symbol})")
            except Exception as e:
                print(f"  Error fetching {indicator} ({ticker_symbol}): {str(e)}")
                # Continue with other indicators even if one fails
        
        if economic_data:
            covariate_data['economic_indicators'] = pd.DataFrame(economic_data)
            print(f"Economic indicators data shape: {covariate_data['economic_indicators'].shape}")
        else:
            print("No economic indicators data collected")
        
        # Return whatever data we were able to collect
        if not covariate_data:
            print("Warning: No covariate data collected, returning empty dict")
        
        return covariate_data
    
    except Exception as e:
        print(f"Error collecting covariate data: {str(e)}")
        # Return empty dict instead of failing completely
        return {}

def calculate_market_sentiment(symbol: str, lookback_days: int = 30) -> Dict[str, float]:
    """
    Calculate market sentiment using news sentiment analysis and social media data.
    
    Args:
        symbol (str): Stock symbol
        lookback_days (int): Number of days to look back
    
    Returns:
        Dict[str, float]: Sentiment metrics
    """
    if not SENTIMENT_AVAILABLE:
        return {'sentiment_score': 0.0, 'sentiment_confidence': 0.0}
    
    try:
        sentiment_scores = []
        
        # Get news sentiment (simplified approach using yfinance news)
        try:
            ticker = yf.Ticker(symbol)
            news = retry_yfinance_request(lambda: ticker.news)
            
            if news:
                for article in news[:10]:  # Analyze last 10 news articles
                    title = article.get('title', '')
                    summary = article.get('summary', '')
                    text = f"{title} {summary}"
                    
                    # Calculate sentiment using TextBlob
                    blob = TextBlob(text)
                    sentiment_scores.append(blob.sentiment.polarity)
        except Exception as e:
            print(f"Error fetching news sentiment: {str(e)}")
            # Don't fail completely, just log the error
        
        # Calculate average sentiment
        if sentiment_scores:
            avg_sentiment = np.mean(sentiment_scores)
            sentiment_confidence = min(0.9, len(sentiment_scores) / 10.0)
        else:
            avg_sentiment = 0.0
            sentiment_confidence = 0.0
        
        return {
            'sentiment_score': avg_sentiment,
            'sentiment_confidence': sentiment_confidence,
            'sentiment_samples': len(sentiment_scores)
        }
    
    except Exception as e:
        print(f"Error calculating sentiment: {str(e)}")
        # Return neutral sentiment on error
        return {
            'sentiment_score': 0.0, 
            'sentiment_confidence': 0.0,
            'sentiment_samples': 0,
            'error': str(e)
        }

def calculate_advanced_uncertainty(quantiles: np.ndarray, historical_volatility: float, 
                                 market_conditions: Dict = None, confidence_level: float = 0.9) -> Dict[str, np.ndarray]:
    """
    Calculate advanced uncertainty estimates using multiple methods.
    
    Args:
        quantiles (np.ndarray): Quantile predictions from Chronos
        historical_volatility (float): Historical volatility
        market_conditions (Dict): Market condition indicators
        confidence_level (float): Confidence level for uncertainty calculation
    
    Returns:
        Dict[str, np.ndarray]: Multiple uncertainty estimates
    """
    try:
        lower = quantiles[0, :, 0]
        median = quantiles[0, :, 1]
        upper = quantiles[0, :, 2]
        
        uncertainties = {}
        
        # 1. Basic quantile-based uncertainty
        basic_uncertainty = (upper - lower) / (2 * stats.norm.ppf(confidence_level))
        uncertainties['basic'] = basic_uncertainty
        
        # 2. Skewness-adjusted uncertainty
        skewed_uncertainty = calculate_skewed_uncertainty(quantiles, confidence_level)
        uncertainties['skewed'] = skewed_uncertainty
        
        # 3. Volatility-scaled uncertainty
        volatility_scaled = basic_uncertainty * (1 + historical_volatility)
        uncertainties['volatility_scaled'] = volatility_scaled
        
        # 4. Market condition adjusted uncertainty
        if market_conditions:
            vix_level = market_conditions.get('vix', 20.0)
            vix_factor = vix_level / 20.0  # Normalize to typical VIX level
            market_adjusted = basic_uncertainty * vix_factor
            uncertainties['market_adjusted'] = market_adjusted
        else:
            uncertainties['market_adjusted'] = basic_uncertainty
        
        # 5. Time-decay uncertainty (uncertainty increases with prediction horizon)
        time_decay = np.array([basic_uncertainty[i] * (1 + 0.1 * i) for i in range(len(basic_uncertainty))])
        uncertainties['time_decay'] = time_decay
        
        # 6. Ensemble uncertainty (combine all methods)
        ensemble_uncertainty = np.mean([
            uncertainties['basic'],
            uncertainties['skewed'],
            uncertainties['volatility_scaled'],
            uncertainties['market_adjusted'],
            uncertainties['time_decay']
        ], axis=0)
        uncertainties['ensemble'] = ensemble_uncertainty
        
        return uncertainties
    
    except Exception as e:
        print(f"Advanced uncertainty calculation error: {str(e)}")
        # Fallback to basic calculation
        return {'basic': (quantiles[0, :, 2] - quantiles[0, :, 0]) / (2 * 1.645)}

def create_enhanced_ensemble_model(df: pd.DataFrame, covariate_data: Dict, 
                                 prediction_days: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create an enhanced ensemble model using multiple algorithms and covariate data.
    
    Args:
        df (pd.DataFrame): Stock data
        covariate_data (Dict): Covariate data
        prediction_days (int): Number of days to predict
    
    Returns:
        Tuple[np.ndarray, np.ndarray]: Ensemble predictions and uncertainties
    """
    if not ENSEMBLE_AVAILABLE:
        return np.array([]), np.array([])
    
    try:
        # Prepare features
        features = []
        target = df['Close'].values
        
        # Technical indicators as features
        features.append(df['RSI'].fillna(50).values)  # Fill NaN with neutral RSI value
        features.append(df['MACD'].fillna(0).values)  # Fill NaN with zero
        features.append(df['Volatility'].fillna(df['Volatility'].mean()).values)  # Fill with mean volatility
        
        if 'BB_Upper' in df.columns:
            bb_position = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
            bb_position = bb_position.fillna(0.5)  # Fill NaN with neutral position
            features.append(bb_position.values)
        
        # Add lagged price features to capture temporal patterns
        for lag in [1, 2, 3, 5, 10]:
            if len(target) > lag:
                lagged_prices = np.pad(target[:-lag], (lag, 0), mode='edge')
                features.append(lagged_prices)
        
        # Add rolling statistics to capture trends
        for window in [5, 10, 20]:
            if len(target) >= window:
                rolling_mean = pd.Series(target).rolling(window=window, min_periods=1).mean().values
                rolling_std = pd.Series(target).rolling(window=window, min_periods=1).std().fillna(0).values
                features.append(rolling_mean)
                features.append(rolling_std)
        
        # Add price momentum features
        if len(target) > 1:
            price_momentum_1d = np.pad(np.diff(target), (1, 0), mode='constant', constant_values=0)
            price_momentum_5d = np.pad(np.diff(target, n=5), (5, 0), mode='constant', constant_values=0)
            features.append(price_momentum_1d)
            features.append(price_momentum_5d)
        
        # Add covariate data
        if 'market_indices' in covariate_data:
            for col in covariate_data['market_indices'].columns:
                covariate_series = covariate_data['market_indices'][col]
                # Align covariate data to target length
                if len(covariate_series) == len(target):
                    # Fill NaN values with forward fill, then backward fill
                    filled_series = covariate_series.fillna(method='ffill').fillna(method='bfill')
                    features.append(filled_series.values)
                elif len(covariate_series) > len(target):
                    # Truncate to target length
                    truncated_series = covariate_series.tail(len(target))
                    filled_series = truncated_series.fillna(method='ffill').fillna(method='bfill')
                    features.append(filled_series.values)
                else:
                    # Pad with last value
                    padded_values = np.pad(covariate_series.values, 
                                         (len(target) - len(covariate_series), 0), 
                                         mode='edge')
                    # Fill any remaining NaN values
                    filled_values = pd.Series(padded_values).fillna(method='ffill').fillna(method='bfill').values
                    features.append(filled_values)
        
        if 'economic_indicators' in covariate_data:
            for col in covariate_data['economic_indicators'].columns:
                covariate_series = covariate_data['economic_indicators'][col]
                # Align covariate data to target length
                if len(covariate_series) == len(target):
                    # Fill NaN values with forward fill, then backward fill
                    filled_series = covariate_series.fillna(method='ffill').fillna(method='bfill')
                    features.append(filled_series.values)
                elif len(covariate_series) > len(target):
                    # Truncate to target length
                    truncated_series = covariate_series.tail(len(target))
                    filled_series = truncated_series.fillna(method='ffill').fillna(method='bfill')
                    features.append(filled_series.values)
                else:
                    # Pad with last value
                    padded_values = np.pad(covariate_series.values, 
                                         (len(target) - len(covariate_series), 0), 
                                         mode='edge')
                    # Fill any remaining NaN values
                    filled_values = pd.Series(padded_values).fillna(method='ffill').fillna(method='bfill').values
                    features.append(filled_values)
        
        # Create feature matrix
        X = np.column_stack(features)
        y = target
        
        # Validate feature matrix
        print(f"Feature matrix shape: {X.shape}, Target shape: {y.shape}")
        
        # Ensure all features have the same length
        feature_lengths = [len(feature) for feature in features]
        if len(set(feature_lengths)) > 1:
            print(f"Warning: Feature lengths are inconsistent: {feature_lengths}")
            # Find the minimum length and truncate all features
            min_length = min(feature_lengths)
            X = X[:min_length]
            y = y[:min_length]
            print(f"Truncated to minimum length: {min_length}")
        
        # Remove any NaN values
        print(f"Checking for NaN values in feature matrix...")
        nan_rows = np.isnan(X).any(axis=1)
        nan_count = nan_rows.sum()
        print(f"Found {nan_count} rows with NaN values out of {len(X)} total rows")
        
        if nan_count > 0:
            # Check which features have NaN values
            for i, feature_name in enumerate(['RSI', 'MACD', 'Volatility', 'BB_Position'] + 
                                           [f'Market_{j}' for j in range(len(features)-4)]):
                if i < X.shape[1]:
                    nan_count_feature = np.isnan(X[:, i]).sum()
                    if nan_count_feature > 0:
                        print(f"  Feature {feature_name}: {nan_count_feature} NaN values")
        
        # Only remove rows if there are still NaN values after filling
        if nan_count > 0:
            mask = ~np.isnan(X).any(axis=1) & ~np.isnan(y)
            X = X[mask]
            y = y[mask]
            print(f"Removed {nan_count} rows with NaN values")
        else:
            print("No NaN values found in feature matrix")
        
        print(f"After NaN removal - X shape: {X.shape}, y shape: {y.shape}")
        
        if len(X) < 50:  # Need sufficient data
            print(f"Insufficient data after preprocessing: {len(X)} samples")
            print("This might be due to:")
            print("1. Too many NaN values in covariate data")
            print("2. Insufficient historical data")
            print("3. Data alignment issues")
            print("Trying fallback with technical indicators only...")
            
            # Fallback: Use only technical indicators
            try:
                fallback_features = []
                fallback_features.append(df['RSI'].fillna(50).values)
                fallback_features.append(df['MACD'].fillna(0).values)
                fallback_features.append(df['Volatility'].fillna(df['Volatility'].mean()).values)
                
                if 'BB_Upper' in df.columns:
                    bb_position = (df['Close'] - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower'])
                    bb_position = bb_position.fillna(0.5)
                    fallback_features.append(bb_position.values)
                
                X_fallback = np.column_stack(fallback_features)
                y_fallback = df['Close'].values
                
                # Remove any remaining NaN values
                mask = ~np.isnan(X_fallback).any(axis=1) & ~np.isnan(y_fallback)
                X_fallback = X_fallback[mask]
                y_fallback = y_fallback[mask]
                
                print(f"Fallback feature matrix shape: {X_fallback.shape}")
                
                if len(X_fallback) >= 50:
                    print("Using fallback ensemble with technical indicators only")
                    # Use the fallback data for the rest of the function
                    X = X_fallback
                    y = y_fallback
                else:
                    print("Fallback also failed, returning empty arrays")
                    return np.array([]), np.array([])
                    
            except Exception as fallback_error:
                print(f"Fallback failed: {str(fallback_error)}")
                return np.array([]), np.array([])
        
        # Initialize models
        models = {
            'random_forest': RandomForestRegressor(n_estimators=100, random_state=42),
            'gradient_boosting': GradientBoostingRegressor(n_estimators=100, random_state=42),
            'ridge': Ridge(alpha=1.0),
            'lasso': Lasso(alpha=0.1),
            'svr': SVR(kernel='rbf', C=1.0, gamma='scale'),
            'mlp': MLPRegressor(hidden_layer_sizes=(100, 50), max_iter=500, random_state=42)
        }
        
        # Train models using time series cross-validation
        predictions = {}
        uncertainties = {}
        
        for name, model in models.items():
            try:
                # Use ALL available data for training (no train/test split)
                # This maximizes the use of historical information
                print(f"Training {name} on all {len(X)} data points...")
                
                # Train model on all available data
                model.fit(X, y)
                
                # Generate predictions for the full prediction period
                # Use the most recent data points to generate future predictions
                if len(X) >= prediction_days:
                    # Use the last prediction_days data points for prediction
                    # This ensures we're using the most recent patterns and trends
                    X_pred = X[-prediction_days:]
                    pred = model.predict(X_pred)
                    print(f"  {name}: Generated {len(pred)} predictions using last {prediction_days} data points")
                else:
                    # If we don't have enough data, use all available data and extrapolate
                    pred = model.predict(X)
                    print(f"  {name}: Generated {len(pred)} predictions using all {len(X)} data points")
                    
                    if len(pred) < prediction_days:
                        # Extend with trend-based predictions
                        if len(pred) > 0:
                            # Calculate trend from last few predictions
                            trend_window = min(5, len(pred))
                            if trend_window > 1:
                                trend = np.mean(np.diff(pred[-trend_window:]))
                            else:
                                trend = 0
                            
                            # Extend predictions using the trend
                            last_pred = pred[-1] if len(pred) > 0 else y[-1]
                            for i in range(len(pred), prediction_days):
                                next_pred = last_pred + trend
                                pred = np.append(pred, next_pred)
                                last_pred = next_pred
                            
                            print(f"  {name}: Extended to {len(pred)} predictions using trend extrapolation")
                        else:
                            # No predictions available, use simple extrapolation
                            last_price = y[-1]
                            pred = np.array([last_price * (1 + 0.001 * i) for i in range(prediction_days)])
                            print(f"  {name}: Generated {len(pred)} predictions using simple extrapolation")
                
                # Calculate uncertainty using cross-validation on all data
                # This gives us a better estimate of model performance
                try:
                    cv_scores = cross_val_score(model, X, y, cv=min(5, len(X)//10), scoring='neg_mean_squared_error')
                    mse = -np.mean(cv_scores)
                    uncertainty = np.sqrt(mse) * np.ones(prediction_days)
                    print(f"  {name} CV MSE: {mse:.6f}")
                except Exception as cv_error:
                    print(f"  {name} CV failed, using fallback uncertainty: {str(cv_error)}")
                    # Fallback uncertainty based on historical volatility
                    uncertainty = np.std(y) * np.ones(prediction_days)
                
                # Ensure prediction is the right length
                if len(pred) != prediction_days:
                    print(f"Warning: {name} produced {len(pred)} predictions, expected {prediction_days}")
                    if len(pred) > prediction_days:
                        pred = pred[:prediction_days]
                        uncertainty = uncertainty[:prediction_days]
                    else:
                        # Extend with trend-based predictions
                        if len(pred) > 0:
                            # Calculate trend from last few predictions
                            trend_window = min(5, len(pred))
                            if trend_window > 1:
                                trend = np.mean(np.diff(pred[-trend_window:]))
                            else:
                                trend = 0
                            
                            # Extend predictions using the trend
                            last_pred = pred[-1] if len(pred) > 0 else y[-1]
                            for i in range(len(pred), prediction_days):
                                next_pred = last_pred + trend
                                pred = np.append(pred, next_pred)
                                last_pred = next_pred
                        else:
                            # No predictions available, use simple extrapolation
                            last_price = y[-1]
                            pred = np.array([last_price * (1 + 0.001 * i) for i in range(prediction_days)])
                
                # Validate prediction
                if len(pred) == prediction_days and len(uncertainty) == prediction_days:
                    predictions[name] = pred
                    uncertainties[name] = uncertainty
                else:
                    print(f"Warning: {name} prediction validation failed. Skipping.")
                    continue
                
            except Exception as e:
                print(f"Error training {name}: {str(e)}")
                continue
        
        if not predictions:
            return np.array([]), np.array([])
        
        # Debug: Print prediction lengths
        print(f"Ensemble model debugging - Expected prediction_days: {prediction_days}")
        for name, pred in predictions.items():
            print(f"  {name}: prediction length = {len(pred)}, uncertainty length = {len(uncertainties.get(name, []))}")
        
        # Combine predictions using weighted average
        weights = {}
        model_performances = {}
        
        for name in predictions.keys():
            if name in uncertainties:
                # Calculate model performance on training data
                try:
                    # Use cross-validation score as performance metric
                    cv_scores = cross_val_score(models[name], X, y, cv=min(5, len(X)//10), scoring='r2')
                    performance = np.mean(cv_scores)
                    model_performances[name] = performance
                    
                    # Weight based on both performance and uncertainty
                    # Higher performance and lower uncertainty = higher weight
                    uncertainty_factor = 1.0 / np.mean(uncertainties[name])
                    performance_factor = max(0, performance)  # Ensure non-negative
                    
                    # Combine factors (you can adjust the balance)
                    weights[name] = (0.7 * performance_factor + 0.3 * uncertainty_factor)
                    
                    print(f"  {name}: Performance={performance:.4f}, Uncertainty={np.mean(uncertainties[name]):.4f}, Weight={weights[name]:.4f}")
                    
                except Exception as e:
                    print(f"  {name}: Performance calculation failed, using uncertainty only: {str(e)}")
                    # Fallback to uncertainty-based weighting
                    weights[name] = 1.0 / np.mean(uncertainties[name])
                    model_performances[name] = 0.0
            else:
                # Equal weight if no uncertainty available
                weights[name] = 1.0
                model_performances[name] = 0.0
        
        # Normalize weights
        total_weight = sum(weights.values())
        if total_weight > 0:
            weights = {k: v / total_weight for k, v in weights.items()}
        else:
            # Equal weights if all uncertainties are zero
            weights = {k: 1.0 / len(weights) for k in weights.keys()}
        
        # Calculate ensemble prediction
        ensemble_pred = np.zeros(prediction_days)
        ensemble_uncertainty = np.zeros(prediction_days)
        
        for name, pred in predictions.items():
            if name in weights:
                # Ensure prediction is the right length
                pred_array = np.array(pred)
                uncertainty_array = np.array(uncertainties[name])
                
                # Handle different prediction lengths
                if len(pred_array) >= prediction_days:
                    # Truncate to prediction_days
                    pred_array = pred_array[:prediction_days]
                    uncertainty_array = uncertainty_array[:prediction_days]
                elif len(pred_array) < prediction_days:
                    # Extend with the last value
                    last_pred = pred_array[-1] if len(pred_array) > 0 else 0
                    last_uncertainty = uncertainty_array[-1] if len(uncertainty_array) > 0 else 1.0
                    
                    # Pad with last values
                    pred_array = np.pad(pred_array, (0, prediction_days - len(pred_array)), 
                                      mode='constant', constant_values=last_pred)
                    uncertainty_array = np.pad(uncertainty_array, (0, prediction_days - len(uncertainty_array)), 
                                             mode='constant', constant_values=last_uncertainty)
                
                # Ensure arrays are the correct shape
                if len(pred_array) != prediction_days:
                    print(f"Warning: {name} prediction length mismatch. Expected {prediction_days}, got {len(pred_array)}")
                    continue
                
                if len(uncertainty_array) != prediction_days:
                    print(f"Warning: {name} uncertainty length mismatch. Expected {prediction_days}, got {len(uncertainty_array)}")
                    continue
                
                # Add weighted contribution
                ensemble_pred += weights[name] * pred_array
                ensemble_uncertainty += weights[name] * uncertainty_array
        
        return ensemble_pred, ensemble_uncertainty
    
    except Exception as e:
        print(f"Enhanced ensemble model error: {str(e)}")
        print("Falling back to simple ensemble prediction...")
        
        # Fallback: Simple ensemble using basic models
        try:
            # Use simple linear regression as fallback
            X = np.arange(len(df)).reshape(-1, 1)
            y = df['Close'].values
            
            # Simple linear trend
            slope = np.polyfit(X.flatten(), y, 1)[0]
            last_price = y[-1]
            
            # Generate simple predictions
            ensemble_pred = np.array([last_price + slope * i for i in range(1, prediction_days + 1)])
            ensemble_uncertainty = np.std(y) * np.ones(prediction_days)
            
            return ensemble_pred, ensemble_uncertainty
            
        except Exception as fallback_error:
            print(f"Fallback ensemble also failed: {str(fallback_error)}")
            return np.array([]), np.array([])

def calculate_volume_prediction_enhanced(df: pd.DataFrame, price_prediction: np.ndarray, 
                                       covariate_data: Dict = None) -> Tuple[np.ndarray, np.ndarray]:
    """
    Enhanced volume prediction using multiple factors and relationships.
    
    Args:
        df (pd.DataFrame): Stock data
        price_prediction (np.ndarray): Price predictions
        covariate_data (Dict): Covariate data
    
    Returns:
        Tuple[np.ndarray, np.ndarray]: Volume predictions and uncertainties
    """
    try:
        # Get historical volume and price data
        volume_data = df['Volume'].values
        price_data = df['Close'].values
        
        # Calculate volume-price relationship
        volume_price_ratio = volume_data / price_data
        volume_volatility = np.std(volume_data)
        
        # Calculate volume momentum
        volume_momentum = np.diff(volume_data)
        avg_volume_momentum = np.mean(volume_momentum[-10:])  # Last 10 periods
        
        # Predict volume based on price movement
        price_changes = np.diff(price_prediction)
        predicted_volume = []
        
        for i, price_change in enumerate(price_changes):
            if i == 0:
                # First prediction based on last actual volume
                base_volume = volume_data[-1]
            else:
                # Subsequent predictions based on price movement and momentum
                base_volume = predicted_volume[-1]
            
            # Adjust volume based on price movement
            if abs(price_change) > 0.01:  # Significant price movement
                volume_multiplier = 1.5 if abs(price_change) > 0.02 else 1.2
            else:
                volume_multiplier = 0.8
            
            # Add momentum effect
            momentum_effect = 1.0 + (avg_volume_momentum / base_volume) * 0.1
            
            # Calculate predicted volume
            pred_vol = base_volume * volume_multiplier * momentum_effect
            
            # Add some randomness based on historical volatility
            noise = np.random.normal(0, volume_volatility * 0.1)
            pred_vol = max(0, pred_vol + noise)
            
            predicted_volume.append(pred_vol)
        
        # Add first prediction
        predicted_volume.insert(0, volume_data[-1])
        
        # Calculate uncertainty
        volume_uncertainty = volume_volatility * np.ones(len(predicted_volume))
        
        # Adjust uncertainty based on prediction horizon
        for i in range(len(volume_uncertainty)):
            volume_uncertainty[i] *= (1 + 0.1 * i)
        
        return np.array(predicted_volume), np.array(volume_uncertainty)
    
    except Exception as e:
        print(f"Enhanced volume prediction error: {str(e)}")
        # Fallback to simple prediction
        last_volume = df['Volume'].iloc[-1]
        return np.full(len(price_prediction), last_volume), np.full(len(price_prediction), last_volume * 0.2)

def calculate_regime_aware_uncertainty(quantiles: np.ndarray, regime_info: Dict, 
                                     market_conditions: Dict = None) -> np.ndarray:
    """
    Calculate uncertainty that accounts for market regime changes.
    
    Args:
        quantiles (np.ndarray): Quantile predictions
        regime_info (Dict): Market regime information
        market_conditions (Dict): Current market conditions
    
    Returns:
        np.ndarray: Regime-aware uncertainty estimates
    """
    try:
        # Get basic uncertainty
        basic_uncertainty = calculate_skewed_uncertainty(quantiles)
        
        # Get regime information
        if regime_info and 'volatilities' in regime_info:
            current_volatility = regime_info.get('current_volatility', np.mean(regime_info['volatilities']))
            avg_volatility = np.mean(regime_info['volatilities'])
            volatility_ratio = current_volatility / avg_volatility
        else:
            volatility_ratio = 1.0
        
        # Adjust uncertainty based on regime
        regime_adjusted = basic_uncertainty * volatility_ratio
        
        # Add market condition adjustments
        if market_conditions:
            vix_level = market_conditions.get('vix', 20.0)
            vix_factor = vix_level / 20.0
            regime_adjusted *= vix_factor
        
        return regime_adjusted
    
    except Exception as e:
        print(f"Regime-aware uncertainty calculation error: {str(e)}")
        return calculate_skewed_uncertainty(quantiles)

def get_market_info_from_yfinance(symbol: str) -> Dict:
    """
    Get market information from yfinance using the recommended API methods.
    
    Args:
        symbol (str): Market symbol (e.g., '^GSPC', 'EURUSD=X', 'BTC-USD')
    
    Returns:
        Dict: Market information including current price, volume, and other metrics
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Get basic info with retry - use get_info() method as recommended
        info = retry_yfinance_request(lambda: ticker.info)
        
        # Get current market data with retry
        try:
            hist = retry_yfinance_request(lambda: ticker.history(period="1d"))
        except Exception as e:
            print(f"Error fetching history for {symbol}: {str(e)}")
            hist = None
        
        # Get additional market data
        market_data = {}
        
        if hist is not None and not hist.empty:
            market_data.update({
                'current_price': hist['Close'].iloc[-1],
                'open_price': hist['Open'].iloc[-1],
                'high_price': hist['High'].iloc[-1],
                'low_price': hist['Low'].iloc[-1],
                'volume': hist['Volume'].iloc[-1],
                'change': hist['Close'].iloc[-1] - hist['Open'].iloc[-1],
                'change_percent': ((hist['Close'].iloc[-1] - hist['Open'].iloc[-1]) / hist['Open'].iloc[-1]) * 100
            })
        
        # Get news if available with retry
        try:
            news = retry_yfinance_request(lambda: ticker.news)
            market_data['news_count'] = len(news) if news else 0
        except Exception as e:
            print(f"Error fetching news for {symbol}: {str(e)}")
            market_data['news_count'] = 0
        
        # Skip earnings and recommendations for symbols that typically don't have them
        symbols_without_earnings = ['^', '=', 'F', 'X', 'USD', 'EUR', 'GBP', 'JPY', 'BTC', 'ETH', 'GC', 'SI', 'CL', 'NG']
        skip_earnings = any(symbol in symbol.upper() for symbol in symbols_without_earnings)
        
        additional_data = {}

        if skip_earnings:
            market_data['earnings'] = []
            market_data['recommendations'] = []
        else:
            # Get recommendations if available with retry
            try:
                recommendations = retry_yfinance_request(lambda: ticker.recommendations)
                if recommendations is not None and hasattr(recommendations, 'empty') and not recommendations.empty:
                    market_data['recommendations'] = recommendations.tail(5).to_dict('records')
                else:
                    market_data['recommendations'] = []
            except Exception as e:
                print(f"Error fetching recommendations for {symbol}: {str(e)}")
                market_data['recommendations'] = []

            # Get earnings info if available with retry
            try:
                earnings = retry_yfinance_request(lambda: ticker.earnings)
                # Check if earnings is None or empty before accessing .empty
                if earnings is not None and hasattr(earnings, 'empty') and not earnings.empty:
                    market_data['earnings'] = earnings.tail(4).to_dict('records')
                else:
                    market_data['earnings'] = []
            except Exception as e:
                print(f"Error fetching earnings for {symbol}: {str(e)}")
                market_data['earnings'] = []

            # For stocks, try to get dividends and splits
            try:
                dividends = retry_yfinance_request(lambda: ticker.dividends)
                if dividends is not None and hasattr(dividends, 'empty') and not dividends.empty:
                    additional_data['dividends'] = dividends.tail(4).to_dict('records')
                else:
                    additional_data['dividends'] = []
            except Exception as e:
                print(f"Error fetching dividends for {symbol}: {str(e)}")
                additional_data['dividends'] = []
            
            try:
                splits = retry_yfinance_request(lambda: ticker.splits)
                if splits is not None and hasattr(splits, 'empty') and not splits.empty:
                    additional_data['splits'] = splits.tail(4).to_dict('records')
                else:
                    additional_data['splits'] = []
            except Exception as e:
                print(f"Error fetching splits for {symbol}: {str(e)}")
                additional_data['splits'] = []
        
        # Combine all data
        result = {
            'symbol': symbol,
            'info': info,
            'market_data': market_data,
            'additional_data': additional_data,
            'timestamp': datetime.now().isoformat()
        }
        
        return result
        
    except Exception as e:
        print(f"Error fetching market info for {symbol}: {str(e)}")
        return {
            'symbol': symbol,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }

def get_enhanced_market_summary() -> Dict:
    """
    Get enhanced market summary for all configured markets using yfinance.
    
    Returns:
        Dict: Summary of all markets with current data
    """
    market_summary = {}
    
    for market_key, config in MARKET_CONFIGS.items():
        try:
            symbol = config['symbol']
            market_info = get_market_info_from_yfinance(symbol)
            market_status = market_status_manager.get_status(market_key)
            
            market_summary[market_key] = {
                'config': config,
                'status': {
                    'is_open': market_status.is_open,
                    'status_text': market_status.status_text,
                    'current_time': market_status.current_time_et,
                    'next_trading_day': market_status.next_trading_day
                },
                'market_data': market_info.get('market_data', {}),
                'info': market_info.get('info', {}),
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            market_summary[market_key] = {
                'config': config,
                'error': str(e),
                'last_updated': datetime.now().isoformat()
            }
    
    return market_summary

def check_market_status_simple(market_key: str) -> str:
    """
    Simple function to check market status for a specific market.
    
    Args:
        market_key (str): Market key from MARKET_CONFIGS
        
    Returns:
        str: Formatted market status information
    """
    try:
        # Get market status
        status = market_status_manager.get_status(market_key)
        
        # Create a user-friendly display
        status_emoji = "🟢" if status.is_open else "🔴"
        status_text = "OPEN" if status.is_open else "CLOSED"
        
        result = f"""
## {status_emoji} {status.market_name} Status: {status_text}

**Current Status:** {status.status_text}

**Market Details:**
- **Type:** {status.market_type.title()}
- **Symbol:** {status.market_symbol}
- **Current Time:** {status.current_time_et}
- **Last Updated:** {status.last_updated}

**Trading Information:**
- **Next Trading Day:** {status.next_trading_day}
- **Time Until Open:** {status.time_until_open}
- **Time Until Close:** {status.time_until_close}

**Market Description:** {MARKET_CONFIGS[market_key]['description']}
"""
        
        return result
        
    except Exception as e:
        return f"❌ Error checking market status: {str(e)}"

def calculate_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate technical indicators for a given DataFrame.
    
    Args:
        df (pd.DataFrame): DataFrame with OHLCV data
    
    Returns:
        pd.DataFrame: DataFrame with technical indicators added
    """
    try:
        # Calculate moving averages
        df['SMA_20'] = df['Close'].rolling(window=20, min_periods=1).mean()
        df['SMA_50'] = df['Close'].rolling(window=50, min_periods=1).mean()
        df['SMA_200'] = df['Close'].rolling(window=200, min_periods=1).mean()
        
        # Calculate RSI
        df['RSI'] = calculate_rsi(df['Close'])
        
        # Calculate MACD
        df['MACD'], df['MACD_Signal'] = calculate_macd(df['Close'])
        
        # Calculate Bollinger Bands
        df['BB_Upper'], df['BB_Middle'], df['BB_Lower'] = calculate_bollinger_bands(df['Close'])
        
        # Calculate additional volatility metrics
        df['Annualized_Vol'] = df['Volatility'] * np.sqrt(252)
        
        # Calculate drawdown metrics
        df['Rolling_Max'] = df['Close'].rolling(window=len(df), min_periods=1).max()
        df['Drawdown'] = (df['Close'] - df['Rolling_Max']) / df['Rolling_Max']
        df['Max_Drawdown'] = df['Drawdown'].rolling(window=len(df), min_periods=1).min()
        
        # Calculate liquidity metrics
        df['Avg_Daily_Volume'] = df['Volume'].rolling(window=20, min_periods=1).mean()
        df['Volume_Volatility'] = df['Volume'].rolling(window=20, min_periods=1).std()
        
        # Fill any remaining NaN values
        df = df.fillna(method='ffill').fillna(method='bfill')
        
        return df
        
    except Exception as e:
        print(f"Error calculating technical indicators: {str(e)}")
        return df

def get_fundamental_data(symbol: str) -> dict:
    """
    Fetch fundamental data for a given symbol using yfinance's info property.
    Returns a dictionary of fundamental data, or an empty dict if unavailable.
    """
    try:
        ticker = yf.Ticker(symbol)
        info = retry_yfinance_request(lambda: ticker.info)
        if info is not None and isinstance(info, dict):
            return info
        else:
            print(f"No fundamental info available for {symbol}")
            return {}
    except Exception as e:
        print(f"Error fetching fundamental data for {symbol}: {str(e)}")
        return {}  # Fallback to empty dict

if __name__ == "__main__":
    import signal
    import atexit
    
    # Register cleanup function
    atexit.register(cleanup_on_exit)
    
    # Handle SIGINT and SIGTERM for graceful shutdown
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        cleanup_on_exit()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        demo = create_interface()
        print("Starting Advanced Stock Prediction Analysis with real-time market status updates...")
        print("Market status will update every 15 minutes automatically.")
        demo.launch(ssr_mode=False, mcp_server=True)
    except KeyboardInterrupt:
        print("\nApplication interrupted by user. Shutting down...")
        cleanup_on_exit()
    except Exception as e:
        print(f"Error starting application: {str(e)}")
        cleanup_on_exit()
        raise
