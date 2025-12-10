"""
Weather Plugin for G-Assist - V2 SDK Version

Provides weather summaries via the Open-Meteo APIs (keyless).
"""

import os
import sys

# ============================================================================
# PATH SETUP - Must be FIRST before any third-party imports!
# ============================================================================
# Add libs folder to path (contains SDK and all dependencies like requests)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

# Now we can import third-party libraries from libs/
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
PLUGIN_NAME = "weather"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default API endpoints (no API key required!)
DEFAULT_CONFIG = {
    "api_base_url": "https://api.open-meteo.com/v1/forecast",
    "geocode_api_url": "https://geocoding-api.open-meteo.com/v1/search",
    "default_timeout": 10,
}

# Weather code descriptions
WEATHER_CODE_MAP = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

def load_config() -> Dict[str, Any]:
    """Load configuration from file."""
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
            # Merge with defaults
            config = DEFAULT_CONFIG.copy()
            config.update(data)
            return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    return DEFAULT_CONFIG.copy()


def describe_weather_code(code: Optional[int]) -> str:
    """Get human-readable description for weather code."""
    if code is None:
        return "Unknown conditions"
    return WEATHER_CODE_MAP.get(code, f"Weather code {code}")


# ============================================================================
# PLUGIN SETUP
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="2.0.0",
    description="Weather information via Open-Meteo (no API key required)"
)


# ============================================================================
# COMMANDS
# ============================================================================
@plugin.command("get_weather_info")
def get_weather_info(city: str = ""):
    """
    Get current weather for a city.
    
    Args:
        city: Name of the city to get weather for
    """
    if not city:
        return "City parameter is required."
    
    config = load_config()
    timeout = config.get("default_timeout", 10)
    geocode_url = config.get("geocode_api_url", DEFAULT_CONFIG["geocode_api_url"])
    forecast_url = config.get("api_base_url", DEFAULT_CONFIG["api_base_url"])
    
    plugin.stream(f"Checking weather for {city}...")
    
    # Step 1: Geocode the city
    # Open-Meteo works better with just city names, not "City, State" format
    # Try to extract city name and add US filter if state abbreviation detected
    city_name = city.strip()
    country_filter = None
    
    # Check for "City, State" or "City, ST" format (US addresses)
    if ", " in city_name:
        parts = city_name.split(", ")
        city_name = parts[0].strip()
        state_part = parts[-1].strip().upper() if len(parts) > 1 else ""
        # Common US state abbreviations (2 letters) or full state names
        if len(state_part) == 2 or state_part in ["CALIFORNIA", "TEXAS", "NEW YORK", "FLORIDA"]:
            country_filter = "US"
    
    params = {"name": city_name, "count": 5, "language": "en", "format": "json"}
    if country_filter:
        params["country"] = country_filter
    
    try:
        geo_resp = requests.get(geocode_url, params=params, timeout=timeout)
        geo_resp.raise_for_status()
        geo_payload = geo_resp.json()
    except requests.Timeout:
        return "Request timed out. Please try again."
    except requests.RequestException as exc:
        return f"Network error while looking up city: {exc}"
    except json.JSONDecodeError:
        return "Failed to parse location lookup response."
    
    results = geo_payload.get("results") or []
    if not results:
        # Try again without country filter
        if country_filter:
            params.pop("country", None)
            try:
                geo_resp = requests.get(geocode_url, params=params, timeout=timeout)
                geo_payload = geo_resp.json()
                results = geo_payload.get("results") or []
            except:
                pass
    
    if not results:
        return f"Could not find coordinates for '{city}'. Try using just the city name (e.g., 'Danville' instead of 'Danville, CA')."
    
    top_hit = results[0]
    latitude = top_hit.get("latitude")
    longitude = top_hit.get("longitude")
    resolved_name = top_hit.get("name") or city
    country = top_hit.get("country_code", "")
    
    if latitude is None or longitude is None:
        return "Location lookup returned invalid coordinates."
    
    # Step 2: Get weather data
    forecast_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": True,
        "hourly": "relativehumidity_2m",
        "timezone": "auto",
    }
    
    try:
        weather_resp = requests.get(forecast_url, params=forecast_params, timeout=timeout)
        weather_resp.raise_for_status()
        payload = weather_resp.json()
    except requests.Timeout:
        return "Request timed out while fetching weather."
    except requests.RequestException as exc:
        return f"Network error while retrieving weather data: {exc}"
    except json.JSONDecodeError:
        return "Failed to parse weather data."
    
    current = payload.get("current_weather") or {}
    temperature = current.get("temperature")
    windspeed = current.get("windspeed")
    weather_code = current.get("weathercode")
    humidity = "N/A"
    
    hourly_times = payload.get("hourly", {}).get("time", [])
    humidities = payload.get("hourly", {}).get("relativehumidity_2m", [])
    if hourly_times and humidities:
        humidity = humidities[-1]
    
    condition = describe_weather_code(weather_code)
    temp_str = f"{temperature:.1f}C" if isinstance(temperature, (int, float)) else "N/A"
    wind_str = f"{windspeed:.0f} km/h wind" if isinstance(windspeed, (int, float)) else "wind data unavailable"
    humidity_str = f"Humidity {humidity}%" if isinstance(humidity, (int, float)) else "Humidity N/A"
    location_label = f"{resolved_name}, {country}" if country else resolved_name
    
    summary = f"{location_label}: {condition}, {temp_str}, {wind_str}, {humidity_str}"
    logger.info(f"Weather result: {summary}")
    return summary


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    logger.info("Starting Weather plugin (SDK version)...")
    plugin.run()
