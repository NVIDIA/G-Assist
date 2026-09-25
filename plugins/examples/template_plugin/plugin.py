# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Template G-Assist plugin (Protocol V2).

Copy this directory, rename it, then replace the command handlers.
The SDK owns JSON-RPC framing, ping/pong, and shutdown.
"""

import json
import logging
import os
import sys
from typing import Optional

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

try:
    from gassist_sdk import Plugin, Context
except ImportError as e:
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.stderr.write("Run plugins\\examples\\setup.bat template_plugin to copy the SDK.\n")
    sys.stderr.flush()
    sys.exit(1)

PLUGIN_NAME = "template_plugin"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME,
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

plugin = Plugin(
    name=PLUGIN_NAME,
    version="1.0.0",
    description="Template plugin demonstrating Protocol V2 streaming and passthrough",
)

pending_note: Optional[str] = None


def load_config() -> dict:
    defaults = {"greeting": "Ready"}
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
                if isinstance(loaded, dict):
                    defaults.update(loaded)
    except Exception as exc:
        logger.error("Error loading config: %s", exc)
    return defaults


@plugin.command("template_echo")
def template_echo(text: str = "", context: Context = None):
    """Echo user text in streamed chunks."""
    payload = (text or "").strip() or "nothing"
    logger.info("template_echo: %s", payload[:80])
    plugin.stream("Echoing...\n")
    plugin.stream(payload)
    return ""


@plugin.command("template_collect_note")
def template_collect_note(prompt: str = ""):
    """Start passthrough until the user types done or cancel."""
    global pending_note
    pending_note = ""
    intro = (prompt or "").strip() or "Send a note. Type done when finished, or cancel to abort."
    plugin.set_keep_session(True)
    logger.info("template_collect_note started")
    return intro


@plugin.command("on_input")
def on_input(content: str):
    """Collect follow-up lines while keep_session is true."""
    global pending_note
    text = (content or "").strip()
    lowered = text.lower()

    if lowered in ("cancel", "abort"):
        pending_note = None
        plugin.set_keep_session(False)
        return "Cancelled."

    if lowered in ("done", "exit", "quit"):
        note = pending_note or ""
        pending_note = None
        plugin.set_keep_session(False)
        if not note:
            return "No note collected."
        return f"Saved note:\n{note}"

    if pending_note is None:
        pending_note = ""
    if pending_note:
        pending_note += "\n"
    pending_note += text
    plugin.set_keep_session(True)
    return "Noted. Send more, or type done."


if __name__ == "__main__":
    logger.info("Starting %s (Protocol V2)", PLUGIN_NAME)
    plugin.run()
