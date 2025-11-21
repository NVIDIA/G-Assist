"""
Weather Plugin - template-aligned implementation.

Provides weather summaries via the Open-Meteo APIs (keyless) and follows the
standard G-Assist plugin structure: ProgramData paths, heartbeat, optional setup
wizard, and streaming-friendly responses.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from ctypes import byref, windll, wintypes, GetLastError, create_string_buffer
from typing import Any, Dict, Optional

import requests

PLUGIN_NAME = "weather"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", ".")
PLUGIN_DIR = os.path.join(PROGRAM_DATA, "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_base_url": "https://api.open-meteo.com/v1/forecast",
    "geocode_api_url": "https://geocoding-api.open-meteo.com/v1/search",
    "default_timeout": 10,
    "features": {
        "enable_passthrough": False,
        "stream_chunk_size": 240,
        "use_setup_wizard": False,
    },
}

STATE: Dict[str, Any] = {
    "config": DEFAULT_CONFIG.copy(),
    "awaiting_input": False,
    "heartbeat_active": False,
    "heartbeat_thread": None,
    "wizard_active": False,
}


def ensure_directories() -> None:
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def apply_config_defaults(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = DEFAULT_CONFIG.copy()
    merged.update({k: v for k, v in raw.items() if k != "features"})

    merged_features = DEFAULT_CONFIG["features"].copy()
    merged_features.update(raw.get("features", {}))
    merged["features"] = merged_features

    if "geocode_api_url" not in merged or not merged["geocode_api_url"]:
        merged["geocode_api_url"] = DEFAULT_CONFIG["geocode_api_url"]
    if "api_base_url" not in merged or not merged["api_base_url"]:
        merged["api_base_url"] = DEFAULT_CONFIG["api_base_url"]
    if "default_timeout" not in merged or not isinstance(merged["default_timeout"], int):
        merged["default_timeout"] = DEFAULT_CONFIG["default_timeout"]

    return merged


def load_config() -> Dict[str, Any]:
    ensure_directories()
    if not os.path.isfile(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    merged = apply_config_defaults(data)
    STATE["config"] = merged
    if merged != data:
        save_config(merged)
    return merged


def save_config(data: Dict[str, Any]) -> None:
    ensure_directories()
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    STATE["config"] = data


def validate_config(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    timeout = data.get("default_timeout")
    if not isinstance(timeout, int) or timeout <= 0:
        return False, "default_timeout must be a positive integer."
    base_url = data.get("api_base_url", "")
    geocode_url = data.get("geocode_api_url", "")
    if not base_url.startswith("http"):
        return False, "api_base_url must be a valid URL (https://...)."
    if not geocode_url.startswith("http"):
        return False, "geocode_api_url must be a valid URL (https://...)."
    return True, None


WEATHER_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def describe_weather_code(code: Optional[int]) -> str:
    if code is None:
        return "Unknown conditions"
    return WEATHER_CODE_MAP.get(code, f"Weather code {code}")


def build_setup_instructions(error: Optional[str] = None) -> str:
    header = f"[{PLUGIN_NAME.upper()} SETUP]\n========================\n"
    error_section = f"⚠️ {error}\n\n" if error else ""
    body = (
        f"1. Open config file:\n   {CONFIG_FILE}\n"
        "2. Update the API base URL or timeout if needed.\n"
        "3. Save the file and type 'done'.\n"
        "4. If you want to skip setup, set features.use_setup_wizard to false.\n"
    )
    return header + error_section + body


def config_needs_setup(config: Dict[str, Any], valid: bool) -> bool:
    return config["features"].get("use_setup_wizard", False) and not valid


def start_setup_wizard(error: Optional[str]) -> Dict[str, Any]:
    STATE["wizard_active"] = True
    STATE["awaiting_input"] = True
    instructions = build_setup_instructions(error)
    return generate_success_response(instructions, awaiting_input=True)


def read_command() -> Optional[Dict[str, Any]]:
    STD_INPUT_HANDLE = -10
    pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)

    buffer = []
    while True:
        chunk = create_string_buffer(4096)
        bytes_read = wintypes.DWORD()
        success = windll.kernel32.ReadFile(pipe, chunk, len(chunk), byref(bytes_read), None)

        if not success:
            logging.error("Pipe read failed (error=%s)", GetLastError())
            return None

        if bytes_read.value == 0:
            time.sleep(0.01)
            continue

        buffer.append(chunk.value[: bytes_read.value].decode("utf-8"))
        if bytes_read.value < len(chunk):
            break

    payload = "".join(buffer)
    if payload.endswith("<<END>>"):
        payload = payload[: -len("<<END>>")]

    try:
        clean = payload.encode("utf-8").decode("raw_unicode_escape")
        return json.loads(clean)
    except json.JSONDecodeError:
        logging.error("Malformed JSON: %s", payload[:200])
        return None


def write_response(response: Dict[str, Any]) -> None:
    STD_OUTPUT_HANDLE = -11
    pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
    payload = (json.dumps(response) + "<<END>>").encode("utf-8")
    bytes_written = wintypes.DWORD()
    success = windll.kernel32.WriteFile(pipe, payload, len(payload), byref(bytes_written), None)
    if success:
        logging.info("[PIPE] Sent %s (%d bytes)", response.get("type", "response"), bytes_written.value)
    else:
        logging.error("[PIPE] Write failed (error=%s)", GetLastError())


def start_heartbeat(interval: int = 10) -> None:
    stop_heartbeat()
    STATE["heartbeat_active"] = True

    def loop() -> None:
        while STATE["heartbeat_active"]:
            heartbeat_msg = {"type": "heartbeat", "timestamp": time.time()}
            write_response(heartbeat_msg)
            time.sleep(interval)

    thread = threading.Thread(target=loop, daemon=True)
    STATE["heartbeat_thread"] = thread
    thread.start()
    logging.info("Heartbeat started (interval=%ss)", interval)


def stop_heartbeat() -> None:
    STATE["heartbeat_active"] = False
    thread = STATE.get("heartbeat_thread")
    if thread and thread.is_alive():
        thread.join(timeout=1)
    STATE["heartbeat_thread"] = None


def generate_success_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {"success": True, "message": message, "awaiting_input": awaiting_input}


def generate_failure_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {"success": False, "message": message, "awaiting_input": awaiting_input}


def stream_text(message: str) -> None:
    chunk_size = STATE["config"]["features"].get("stream_chunk_size", 240)
    for idx in range(0, len(message), chunk_size):
        write_response({"message": message[idx : idx + chunk_size]})


def send_status(message: str) -> None:
    write_response({"message": message})


def build_weather_summary(city: str, config: Dict[str, Any]) -> tuple[bool, str]:
    timeout = config["default_timeout"]
    geocode_url = config.get("geocode_api_url", DEFAULT_CONFIG["geocode_api_url"])
    forecast_url = config.get("api_base_url", DEFAULT_CONFIG["api_base_url"])

    params = {
        "name": city,
        "count": 1,
        "language": "en",
        "format": "json",
    }
    try:
        geo_resp = requests.get(geocode_url, params=params, timeout=timeout)
        geo_resp.raise_for_status()
    except requests.Timeout:
        return False, "Request timed out. Please try again."
    except requests.RequestException as exc:
        return False, f"Network error while looking up city: {exc}"

    try:
        geo_payload = geo_resp.json()
    except json.JSONDecodeError:
        return False, "Failed to parse location lookup response."

    results = geo_payload.get("results") or []
    if not results:
        return False, f"Could not find coordinates for '{city}'."

    top_hit = results[0]
    latitude = top_hit.get("latitude")
    longitude = top_hit.get("longitude")
    resolved_name = top_hit.get("name") or city
    country = top_hit.get("country_code", "")

    if latitude is None or longitude is None:
        return False, "Location lookup returned invalid coordinates."

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
    except requests.Timeout:
        return False, "Request timed out while fetching weather."
    except requests.RequestException as exc:
        return False, f"Network error while retrieving weather data: {exc}"

    try:
        payload = weather_resp.json()
    except json.JSONDecodeError:
        return False, "Failed to parse weather data."

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
    temp_str = f"{temperature:.1f}°C" if isinstance(temperature, (int, float)) else "N/A"
    wind_str = f"{windspeed:.0f} km/h wind" if isinstance(windspeed, (int, float)) else "wind data unavailable"
    humidity_str = f"Humidity {humidity}%" if isinstance(humidity, (int, float)) else "Humidity N/A"
    location_label = f"{resolved_name}, {country}" if country else resolved_name

    summary = f"{location_label}: {condition}, {temp_str}, {wind_str}, {humidity_str}"
    return True, summary


def handle_initialize(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    valid, error = validate_config(config)
    if config_needs_setup(config, valid):
        return start_setup_wizard(error)
    if not valid:
        STATE["awaiting_input"] = False
        STATE["wizard_active"] = False
        return generate_failure_response(error or "Invalid configuration.")

    STATE["awaiting_input"] = config["features"].get("enable_passthrough", False)
    heartbeat_interval = 5 if STATE["awaiting_input"] else 15
    start_heartbeat(interval=heartbeat_interval)

    message = (
        f"[{PLUGIN_NAME}] Ready to handle weather requests.\n"
        f"- API base: {config['api_base_url']}\n"
        f"- Timeout: {config['default_timeout']} seconds\n"
        "Call get_weather_info to fetch current conditions."
    )
    return generate_success_response(message, awaiting_input=STATE["awaiting_input"])


def handle_weather_info(params: Dict[str, Any]) -> Dict[str, Any]:
    city = (params or {}).get("city", "").strip()
    if not city:
        return generate_failure_response("City parameter is required.", awaiting_input=False)

    config = STATE["config"]
    send_status(f"Checking weather for {city}...")
    success, summary = build_weather_summary(city, config)
    if not success:
        return generate_failure_response(summary, awaiting_input=False)

    stream_text(summary)
    return generate_success_response("", awaiting_input=False)


def handle_user_input(message: Dict[str, Any]) -> Dict[str, Any]:
    content = message.get("content", "").strip()
    if STATE["wizard_active"]:
        load_config()
        valid, error = validate_config(STATE["config"])
        if valid:
            STATE["wizard_active"] = False
            STATE["awaiting_input"] = STATE["config"]["features"].get("enable_passthrough", False)
            success_msg = (
                "Configuration detected successfully!\n"
                "You can now use get_weather_info.\n"
                "Type 'exit' to leave passthrough mode when applicable."
            )
            return generate_success_response(success_msg, awaiting_input=STATE["awaiting_input"])
        retry_msg = build_setup_instructions(error)
        return generate_success_response(retry_msg, awaiting_input=True)

    return generate_failure_response("No passthrough session is active.", awaiting_input=False)


def handle_tool_call(command: Dict[str, Any]) -> Dict[str, Any]:
    tool_call = command["tool_calls"][0]
    function_name = tool_call.get("func")
    params = tool_call.get("params", {}) or {}

    if function_name == "initialize":
        return handle_initialize(tool_call)
    if function_name == "get_weather_info":
        return handle_weather_info(params)

    return generate_failure_response(f"Unknown function: {function_name}", awaiting_input=False)


def main() -> int:
    ensure_directories()
    logging.info("Launching weather plugin")

    try:
        while True:
            command = read_command()
            if command is None:
                logging.info("Pipe closed or invalid command received. Exiting weather plugin loop.")
                break

            try:
                if "tool_calls" in command:
                    response = handle_tool_call(command)
                elif command.get("msg_type") == "user_input":
                    response = handle_user_input(command)
                else:
                    response = generate_failure_response("Unsupported command payload.", awaiting_input=False)

                if response is not None:
                    write_response(response)
            except Exception as exc:
                logging.exception("Unhandled error while processing command")
                write_response(generate_failure_response(f"Plugin error: {exc}", awaiting_input=False))

    except KeyboardInterrupt:
        logging.info("Weather plugin interrupted, shutting down.")
    finally:
        stop_heartbeat()

    logging.info("Weather plugin exiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
