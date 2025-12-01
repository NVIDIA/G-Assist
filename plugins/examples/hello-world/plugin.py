# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Hello World G-Assist Plugin (SDK Version)

A simple example plugin demonstrating the JSON-RPC V2 protocol using the G-Assist SDK.

Features demonstrated:
- Basic command handling with @plugin.command decorator
- Streaming responses with plugin.stream()
- Passthrough mode for multi-turn conversations
- Configuration file loading
- Logging

This plugin is intentionally minimal to serve as a starting point for new plugins.
"""

import json
import logging
import os
import sys
from typing import Optional

# ============================================================================
# SDK IMPORT
# ============================================================================
# The engine adds the plugin's libs/ folder to Python path automatically.
# For development, we also add it manually here.
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path) and _libs_path not in sys.path:
    sys.path.insert(0, _libs_path)

try:
    from gassist_sdk import Plugin, Context
except ImportError as e:
    # Fatal error - write to stderr (not stdout!) and exit
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.stderr.write("Ensure gassist_sdk is in the libs/ folder.\n")
    sys.stderr.flush()
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_NAME = "hello-world"
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."), 
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}.log")

os.makedirs(PLUGIN_DIR, exist_ok=True)

# Logging setup
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================================================
# PLUGIN DEFINITION
# ============================================================================
plugin = Plugin(
    name=PLUGIN_NAME,
    version="1.0.0",
    description="A simple Hello World plugin demonstrating the G-Assist SDK"
)

# ============================================================================
# GLOBAL STATE
# ============================================================================
conversation_history = []

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_config() -> dict:
    """Load configuration from file."""
    default_config = {"greeting": "Hello", "farewell": "Goodbye"}
    
    try:
        if os.path.isfile(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
    
    return default_config


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@plugin.command("say_hello")
def say_hello(name: str = "World", context: Context = None):
    """
    Greet the user with a personalized message.
    
    This is the simplest example of a plugin command. It takes a name parameter
    and returns a greeting.
    
    Args:
        name: The name of the person to greet (default: "World")
        context: Conversation context (optional, provided by engine)
    
    Returns:
        A greeting message
    """
    config = load_config()
    greeting = config.get("greeting", "Hello")
    
    logger.info(f"[HELLO] Greeting: {name}")
    
    return f"{greeting}, {name}! Welcome to G-Assist plugins. 🎉"


@plugin.command("count_with_streaming")
def count_with_streaming(count_to: int = 5):
    """
    Count from 1 to N with streaming output.
    
    This demonstrates how to use plugin.stream() to send partial results
    to the user as they become available. Useful for long-running operations.
    
    Args:
        count_to: The number to count to (default: 5, max: 20)
    
    Returns:
        Empty string (all output is streamed)
    """
    import time
    
    # Clamp to reasonable range
    count_to = max(1, min(20, count_to))
    
    logger.info(f"[COUNT] Counting to {count_to}")
    
    plugin.stream(f"Counting to {count_to}...\n\n")
    
    for i in range(1, count_to + 1):
        plugin.stream(f"🔢 {i}\n")
        time.sleep(0.3)  # Small delay to show streaming effect
    
    plugin.stream(f"\n✅ Done counting to {count_to}!")
    
    return ""  # All output was streamed


@plugin.command("start_conversation")
def start_conversation(topic: str = "anything"):
    """
    Start an interactive conversation (enters passthrough mode).
    
    This demonstrates passthrough mode where the plugin maintains a session
    and receives follow-up user messages via on_input.
    
    Args:
        topic: What the user wants to talk about
    
    Returns:
        Initial conversation message
    """
    global conversation_history
    
    logger.info(f"[CHAT] Starting conversation about: {topic}")
    
    # Clear previous conversation
    conversation_history = []
    conversation_history.append({"role": "user", "content": f"Let's talk about {topic}"})
    
    # Enter passthrough mode - subsequent user messages come to on_input
    plugin.set_keep_session(True)
    
    return f"""💬 Starting a conversation about: {topic}

I'm now in conversation mode! You can:
- Send messages and I'll echo them back
- Type "summary" to see our conversation so far
- Type "exit" to end the conversation

What would you like to say?"""


@plugin.command("on_input")
def on_input(content: str):
    """
    Handle follow-up user input in passthrough mode.
    
    This is called automatically when:
    1. Plugin previously set keep_session=True
    2. User sends a new message
    3. Engine routes that message here
    
    Args:
        content: The user's message
    
    Returns:
        Response to the user
    """
    global conversation_history
    
    content = content.strip()
    logger.info(f"[INPUT] Received: {content[:50]}...")
    
    # Check for exit commands
    if content.lower() in ["exit", "quit", "bye", "done"]:
        config = load_config()
        farewell = config.get("farewell", "Goodbye")
        
        conversation_history = []
        plugin.set_keep_session(False)  # Exit passthrough mode
        
        return f"👋 {farewell}! Conversation ended."
    
    # Check for summary command
    if content.lower() == "summary":
        if not conversation_history:
            plugin.set_keep_session(True)
            return "📝 No conversation yet! Say something first."
        
        summary = "\n".join([
            f"- **{msg['role'].title()}**: {msg['content'][:50]}..."
            for msg in conversation_history[-5:]  # Last 5 messages
        ])
        
        plugin.set_keep_session(True)
        return f"📝 **Conversation Summary** (last 5 messages):\n\n{summary}\n\nContinue chatting or type 'exit' to end."
    
    # Add to conversation history
    conversation_history.append({"role": "user", "content": content})
    
    # Echo with a twist
    response = f"🗣️ You said: \"{content}\"\n\n(Message #{len(conversation_history)} in our conversation)"
    conversation_history.append({"role": "assistant", "content": response})
    
    # Stay in passthrough mode
    plugin.set_keep_session(True)
    
    return response


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    logger.info(f"Starting {PLUGIN_NAME} plugin (SDK version)...")
    plugin.run()

