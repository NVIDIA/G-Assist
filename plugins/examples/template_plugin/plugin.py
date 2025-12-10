"""
Template G-Assist plugin.

This file provides a fully wired reference implementation that new plugins can
copy and adapt.  It demonstrates:
  * Directory/layout conventions (ProgramData deployment, config + logs)
  * Request/response framing over the RISE plugin pipe (<<END>> delimiter)
  * Heartbeat background thread for health monitoring
  * Tool call handling with streaming chunks
  * Passthrough (`awaiting_input`) mode and user-input routing
  * Simple configuration validation + setup wizard hook

To build a real plugin:
  1. Duplicate this directory and rename it to your plugin name.
  2. Update PLUGIN_NAME, DEFAULT_CONFIG, manifest.json, and `handle_tool_call`.
  3. Replace the stubbed API helpers with real logic.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from ctypes import byref, windll, wintypes, create_string_buffer, GetLastError
from typing import Any, Dict, Optional

# -----------------------------------------------------------------------------
# Feature toggles (tune these at the top when customizing the template)
# -----------------------------------------------------------------------------
ENABLE_SETUP_WIZARD = True
ENABLE_PASSTHROUGH_DEMO = True
DEFAULT_STREAM_CHARS = 240
HEARTBEAT_INTERVAL_SECONDS = 5

# -----------------------------------------------------------------------------
# Paths & persistent state
# -----------------------------------------------------------------------------

PLUGIN_NAME = "template_plugin"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", ".")
PLUGIN_DIR = os.path.join(
    PROGRAM_DATA, "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

DEFAULT_CONFIG: Dict[str, Any] = {
    "api_base_url": "https://api.example.com/v1",
    "api_key": "<replace-with-secure-key>",
    "default_timeout": 15,
    "features": {
        "enable_passthrough": ENABLE_PASSTHROUGH_DEMO,
        "stream_chunk_size": DEFAULT_STREAM_CHARS,
        "use_setup_wizard": ENABLE_SETUP_WIZARD,
    },
}

STATE: Dict[str, Any] = {
    "config": DEFAULT_CONFIG.copy(),
    "awaiting_input": False,
    "pending_note": None,
    "heartbeat_active": False,
    "heartbeat_thread": None,
    "wizard_active": False,
}

# -----------------------------------------------------------------------------
# Logging / IO helpers
# -----------------------------------------------------------------------------


def ensure_directories() -> None:
    os.makedirs(PLUGIN_DIR, exist_ok=True)
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def load_config() -> Dict[str, Any]:
    ensure_directories()
    if not os.path.isfile(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    STATE["config"] = data
    return data


def save_config(data: Dict[str, Any]) -> None:
    ensure_directories()
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    STATE["config"] = data


def validate_config(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    if not data.get("api_key") or data["api_key"].startswith("<replace"):
        return False, "API key missing. Please update config.json before use."
    if not isinstance(data.get("default_timeout", 0), int):
        return False, "default_timeout must be an integer number of seconds."
    return True, None


def build_setup_instructions(error: Optional[str] = None) -> str:
    header = f"[{PLUGIN_NAME.upper()} SETUP]\n========================\n"
    error_section = f"⚠️ {error}\n\n" if error else ""
    body = (
        f"1. Open config file:\n   {CONFIG_FILE}\n"
        "2. Update the API key and any required fields.\n"
        "3. Save the file.\n"
        "4. Return here and type 'done' (or paste the key if your workflow requires it).\n\n"
        "Tips:\n"
        " - Keep keys on a single line (no quotes).\n"
        " - Restart the plugin if you move the config location.\n"
    )
    return header + error_section + body


def config_needs_setup(config: Dict[str, Any], valid: bool) -> bool:
    return (
        ENABLE_SETUP_WIZARD
        and config["features"].get("use_setup_wizard", False)
        and not valid
    )


def start_setup_wizard(error: Optional[str]) -> Dict[str, Any]:
    STATE["wizard_active"] = True
    STATE["awaiting_input"] = True
    instructions = build_setup_instructions(error)
    return generate_success_response(instructions, awaiting_input=True)


def read_command() -> Optional[Dict[str, Any]]:
    """Blocking read from stdin pipe until <<END>> delimiter is received."""
    STD_INPUT_HANDLE = -10
    pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)

    buffer = []
    while True:
        chunk = create_string_buffer(4096)
        bytes_read = wintypes.DWORD()
        success = windll.kernel32.ReadFile(
            pipe,
            chunk,
            len(chunk),
            byref(bytes_read),
            None,
        )

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
    success = windll.kernel32.WriteFile(
        pipe,
        payload,
        len(payload),
        byref(bytes_written),
        None,
    )
    if success:
        logging.info("[PIPE] Sent %s (%d bytes)", response.get("type", "response"), bytes_written.value)
    else:
        logging.error("[PIPE] Write failed (error=%s)", GetLastError())


# -----------------------------------------------------------------------------
# Heartbeat support
# -----------------------------------------------------------------------------


def start_heartbeat(interval: int = 5) -> None:
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


# -----------------------------------------------------------------------------
# Response helpers
# -----------------------------------------------------------------------------


def generate_success_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {"success": True, "message": message, "awaiting_input": awaiting_input}


def generate_failure_response(message: str, awaiting_input: bool = False) -> Dict[str, Any]:
    return {"success": False, "message": message, "awaiting_input": awaiting_input}


def stream_text(message: str, chunk_size: int = DEFAULT_STREAM_CHARS) -> None:
    chunk_size = STATE["config"]["features"].get("stream_chunk_size", chunk_size)
    for idx in range(0, len(message), chunk_size):
        write_response({"message": message[idx : idx + chunk_size]})


# -----------------------------------------------------------------------------
# Business logic stubs (replace with real functionality)
# -----------------------------------------------------------------------------


def handle_initialize(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    config = load_config()
    valid, error = validate_config(config)
    if config_needs_setup(config, valid):
        return start_setup_wizard(error)
    if not valid:
        STATE["awaiting_input"] = False
        STATE["wizard_active"] = False
        return generate_failure_response(error or "Invalid configuration.")

    STATE["awaiting_input"] = False
    STATE["wizard_active"] = False
    start_heartbeat(interval=HEARTBEAT_INTERVAL_SECONDS)

    message = (
        f"[{PLUGIN_NAME}] Ready to handle requests.\n"
        f"- API base: {config['api_base_url']}\n"
        "- Call template_echo for streaming demo output.\n"
        "- Call template_collect_note to enter passthrough when you need user input."
    )
    return generate_success_response(message, awaiting_input=False)


def handle_echo_tool(params: Dict[str, Any]) -> Dict[str, Any]:
    user_text = params.get("text", "nothing provided")
    stream_text(f"You asked me to echo: {user_text}")
    stream_text("This is a second chunk emitted by stream_text()")
    STATE["awaiting_input"] = False
    return generate_success_response("", awaiting_input=False)


def handle_collect_note(params: Dict[str, Any]) -> Dict[str, Any]:
    prompt = params.get("prompt", "What note would you like me to save?")
    STATE["pending_note"] = {"prompt": prompt, "notes": []}
    STATE["awaiting_input"] = True
    instructions = (
        f"{prompt}\n"
        "You can send multiple follow-ups. Type 'done' to finish or 'cancel' to abort."
    )
    return generate_success_response(instructions, awaiting_input=True)


def handle_user_input(message: Dict[str, Any]) -> Dict[str, Any]:
    content = message.get("content", "").strip()
    if STATE["wizard_active"]:
        load_config()
        valid, error = validate_config(STATE["config"])
        if valid:
            STATE["wizard_active"] = False
            STATE["awaiting_input"] = False
            success_msg = (
                "Configuration detected successfully!\n"
                "You can now call template functions or start passthrough flows."
            )
            return generate_success_response(success_msg, awaiting_input=False)

        retry_msg = build_setup_instructions(error)
        return generate_success_response(retry_msg, awaiting_input=True)

    if not STATE["awaiting_input"] or STATE["pending_note"] is None:
        return generate_failure_response("No passthrough session is active.", awaiting_input=False)

    if content.lower() in {"done", "exit"}:
        summary = "\n".join(STATE["pending_note"]["notes"]) or "(empty note)"
        STATE["awaiting_input"] = False
        STATE["pending_note"] = None
        response = f"Got it! Here's the summary I captured:\n{summary}"
        return generate_success_response(response, awaiting_input=False)

    if content.lower() == "cancel":
        STATE["awaiting_input"] = False
        STATE["pending_note"] = None
        return generate_success_response("Passthrough cancelled.", awaiting_input=False)

    STATE["pending_note"]["notes"].append(content)
    follow_up = "Noted! You can keep typing or say 'done' when finished."
    return generate_success_response(follow_up, awaiting_input=True)


def handle_tool_call(command: Dict[str, Any]) -> Dict[str, Any]:
    tool_call = command["tool_calls"][0]
    function_name = tool_call.get("func")
    params = tool_call.get("params", {}) or {}

    dispatch = {
        "initialize": lambda: handle_initialize(tool_call),
        "template_echo": lambda: handle_echo_tool(params),
        "template_collect_note": lambda: handle_collect_note(params),
    }

    handler = dispatch.get(function_name)
    if handler:
        return handler()

    return generate_failure_response(f"Unknown function: {function_name}", awaiting_input=False)


# -----------------------------------------------------------------------------
# Main loop
# -----------------------------------------------------------------------------


def main() -> int:
    ensure_directories()
    logging.info("Launching template plugin")

    try:
        while True:
            command = read_command()
            if not command:
                continue

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
        logging.info("Template plugin interrupted, shutting down.")
    finally:
        stop_heartbeat()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

