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
Google Gemini G-Assist Plugin (SDK Version)

This plugin integrates Google Gemini with G-Assist, providing:
- Web search via Google Search grounding
- Conversational AI responses
- Interactive setup wizard for API key configuration
"""

import json
import logging
import os
import sys
import time
import queue
import threading
import webbrowser
import subprocess
from typing import Optional

# LAZY IMPORTS - these are slow and will be loaded on first use
# from google import genai  # Loaded lazily in _ensure_genai_loaded()
genai = None
ModelContent = None
Part = None
UserContent = None
GoogleSearch = None
Tool = None
GenerateContentConfig = None
_genai_loaded = False

def _ensure_genai_loaded():
    """Lazy load the Google GenAI library (it's slow to import)."""
    global genai, ModelContent, Part, UserContent, GoogleSearch, Tool, GenerateContentConfig, _genai_loaded
    if _genai_loaded:
        return
    
    from google import genai as _genai
    from google.genai.types import (
        ModelContent as _ModelContent, 
        Part as _Part, 
        UserContent as _UserContent, 
        GoogleSearch as _GoogleSearch, 
        Tool as _Tool, 
        GenerateContentConfig as _GenerateContentConfig
    )
    
    genai = _genai
    ModelContent = _ModelContent
    Part = _Part
    UserContent = _UserContent
    GoogleSearch = _GoogleSearch
    Tool = _Tool
    GenerateContentConfig = _GenerateContentConfig
    _genai_loaded = True
    logger.info("[INIT] Google GenAI library loaded")

# ============================================================================
# SDK IMPORT
# ============================================================================
# Try multiple SDK locations (deployed bundle, development, pip-installed)
# Add libs folder to path (contains SDK and all dependencies)
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
_libs_path = os.path.join(_plugin_dir, "libs")
if os.path.exists(_libs_path):
    sys.path.insert(0, _libs_path)

try:
    from gassist_sdk import Plugin, Context
except ImportError as e:
    # Fatal error - write to stderr (not stdout!) and exit
    sys.stderr.write(f"FATAL: Cannot import gassist_sdk: {e}\n")
    sys.stderr.write("Install SDK: pip install -e <path_to_sdk>\n")
    sys.stderr.flush()
    sys.exit(1)

# ============================================================================
# CONFIGURATION
# ============================================================================
PLUGIN_DIR = os.path.join(
    os.environ.get("PROGRAMDATA", "."), 
    "NVIDIA Corporation", "nvtopps", "rise", "plugins", "gemini"
)
API_KEY_FILE = os.path.join(PLUGIN_DIR, 'gemini-api.key')
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')
LOG_FILE = os.path.join(PLUGIN_DIR, 'gemini-plugin.log')

os.makedirs(PLUGIN_DIR, exist_ok=True)

# Logging with immediate flush
class FlushingFileHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[FlushingFileHandler(LOG_FILE)]
)
logger = logging.getLogger(__name__)

# ============================================================================
# GLOBAL STATE
# ============================================================================
API_KEY: Optional[str] = None
client = None
model: str = 'gemini-pro'
SETUP_COMPLETE = False
conversation_history = []  # Stores {"role": "user/assistant", "content": "..."}

# ============================================================================
# PLUGIN DEFINITION
# ============================================================================
plugin = Plugin(
    name="gemini",
    version="2.0.0",
    description="Google Gemini AI assistant with web search"
)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def load_api_key() -> bool:
    """Load and validate API key from file."""
    global API_KEY, client, SETUP_COMPLETE
    
    if not os.path.isfile(API_KEY_FILE):
        logger.info("[INIT] No API key file found")
        return False
    
    with open(API_KEY_FILE) as f:
        key = f.read().strip()
    
    if not key or len(key) < 20 or key.startswith('<insert'):
        logger.info("[INIT] API key too short or placeholder")
        return False
    
    try:
        # Lazy load genai library
        _ensure_genai_loaded()
        
        test_client = genai.Client(api_key=key, http_options={'timeout': None})
        test_client.models.list()  # Validate key
        
        client = test_client
        API_KEY = key
        SETUP_COMPLETE = True
        logger.info("[INIT] API key validated successfully")
        return True
    except Exception as e:
        logger.error(f"[INIT] API key validation failed: {e}")
        return False


def load_model_config():
    """Load model configuration from file."""
    global model
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            model = config.get('model', model)


def sanitize_history_for_search(history: list) -> list:
    """Sanitize conversation history for search queries."""
    clean_history = []
    start_idx = max(0, len(history) - 4)
    recent_history = history[start_idx:]
    
    for msg in recent_history:
        content = msg.get('content', '')
        role = msg.get('role', 'user')
        
        if '"tool":' in content and '"func":' in content:
            if role == 'assistant':
                clean_history.append({
                    "role": "assistant", 
                    "content": "I checked the information for you."
                })
            continue
        clean_history.append(msg)
    
    return clean_history


def convert_openai_history_to_google_gemini(openai_history):
    """Convert OpenAI chat history to Google Gemini format."""
    google_history = []
    for message in openai_history:
        role = message.get("role")
        content = message.get("content")
        part = Part(text=content)
        if role == "user":
            google_history.append(UserContent(parts=[part]))
        elif role == "assistant":
            google_history.append(ModelContent(parts=[part]))
    return google_history


def stream_gemini_response(context: list, timeout_seconds: int = 30) -> str:
    """
    Stream Gemini response with timeout.
    
    Args:
        context: List of message dicts with role/content
        timeout_seconds: Maximum time to wait
        
    Returns:
        Full response text
    """
    global client, model, conversation_history
    
    import sys
    logger.info("GEMINI: Entering stream_gemini_response()")
    sys.stderr.flush()
    
    # Send keep-alive IMMEDIATELY to buy time
    plugin.stream(".")
    logger.info("GEMINI: Sent pre-init keep-alive")
    sys.stderr.flush()
    
    # Ensure genai is loaded
    _ensure_genai_loaded()
    logger.info("GEMINI: genai loaded")
    sys.stderr.flush()
    
    full_response = ""
    result_queue = queue.Queue()
    
    def stream_worker():
        try:
            parts = []
            for msg in context:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    parts.append(UserContent(parts=[Part(text=content)]))
                else:
                    parts.append(ModelContent(parts=[Part(text=content)]))
            
            response = client.models.generate_content_stream(
                model=model,
                contents=parts,
                config=GenerateContentConfig(
                    tools=[Tool(google_search=GoogleSearch())],
                ),
            )
            
            for chunk in response:
                if chunk.text:
                    result_queue.put(("chunk", chunk.text))
            
            result_queue.put(("done", None))
            
        except Exception as e:
            result_queue.put(("error", str(e)))
    
    stream_thread = threading.Thread(target=stream_worker, daemon=True)
    stream_thread.start()
    
    logger.info("GEMINI: Started streaming thread")
    import sys
    sys.stderr.flush()  # Force flush logs
    
    start_time = time.time()
    last_keepalive = time.time()
    received_first_chunk = False
    
    # Send immediate keep-alive to extend heartbeat window
    plugin.stream(".")
    logger.info("GEMINI: Sent initial keep-alive")
    
    while True:
        current_time = time.time()
        
        if current_time - start_time > timeout_seconds:
            logger.error(f"GEMINI: Timeout after {timeout_seconds}s")
            plugin.stream("\n\nResponse timed out. Please try again.")
            break
        
        # Send keep-alive every 2 seconds while waiting for first chunk
        # This prevents heartbeat timeout in the engine
        if not received_first_chunk and (current_time - last_keepalive) > 2.0:
            logger.info("GEMINI: Sending keep-alive...")
            plugin.stream(".")  # Small dot to show we're alive
            last_keepalive = current_time
        
        try:
            msg_type, msg_data = result_queue.get(timeout=0.1)
            
            if msg_type == "chunk":
                if not received_first_chunk:
                    plugin.stream("\n")  # Newline before response starts
                received_first_chunk = True
                logger.info(f'GEMINI: Response chunk: {msg_data[:30]}...')
                plugin.stream(msg_data)
                full_response += msg_data
            elif msg_type == "done":
                logger.info("GEMINI: Stream completed successfully")
                if received_first_chunk:
                    plugin.stream("\r")  # Blank line after response
                break
            elif msg_type == "error":
                logger.error(f"GEMINI: Stream error: {msg_data}")
                error_upper = msg_data.upper()
                
                # Categorize based on Gemini API error codes
                if 'DEADLINE_EXCEEDED' in error_upper or '504' in msg_data:
                    plugin.stream("\n\nRequest timed out. Try a shorter question.")
                elif 'RESOURCE_EXHAUSTED' in error_upper or '429' in msg_data:
                    plugin.stream("\n\nRate limit reached. Please wait a moment and try again.")
                elif 'UNAVAILABLE' in error_upper or '503' in msg_data:
                    plugin.stream("\n\nService temporarily unavailable. Please try again later.")
                elif 'INTERNAL' in error_upper or '500' in msg_data:
                    plugin.stream("\n\nServer error. Try a shorter question or try again later.")
                elif 'PERMISSION_DENIED' in error_upper or '403' in msg_data:
                    plugin.stream("\n\nPermission denied. Check your API key permissions.")
                elif 'INVALID_ARGUMENT' in error_upper or '400' in msg_data:
                    plugin.stream("\n\nInvalid request. Try rephrasing your question.")
                elif 'SAFETY' in error_upper or 'BLOCKED' in error_upper:
                    plugin.stream("\n\nResponse blocked by safety filters. Try rephrasing.")
                else:
                    plugin.stream("\n\nCouldn't get a response. Please try again.")
                break
                
        except queue.Empty:
            pass
    
    # Add to conversation history
    if full_response and len(conversation_history) > 0:
        conversation_history.append({"role": "assistant", "content": full_response})
        logger.info(f"GEMINI: Added response to history ({len(full_response)} chars)")
    
    return full_response


# ============================================================================
# SETUP WIZARD
# ============================================================================

def run_setup_wizard() -> str:
    """Interactive setup wizard for API key configuration."""
    global API_KEY, client, SETUP_COMPLETE
    
    # Check if key exists and is valid
    if load_api_key():
        plugin.set_keep_session(True)
        return """Google Gemini plugin is configured and ready!

You can now ask me questions and I'll search the web for answers.
I'll stay in conversation mode - just keep typing your questions!

Type "exit" to leave Gemini mode."""
    
    # Show setup instructions
    message = """_
**Gemini Plugin - First Time Setup**

Welcome! Let's get your Google Gemini API key. This takes about **1 minute**.

I'm opening Google AI Studio in your browser...

---

**Step 1: Get Your API Key**

1. Click **Create API Key**
2. Choose **Create API key in new project** (easiest)
3. Name your project (e.g., "G-Assist")
4. Click **Create** — your API key will appear
5. Click **Copy** to copy it

---

**Step 2: Save Your Key**

I'm opening the key file in Notepad...

1. Paste your API key
2. Save the file

Save the file and try your query again!

---
"""
    
    try:
        # Open browser
        if sys.platform == 'win32':
            webbrowser.get('windows-default').open(
                "https://aistudio.google.com/app/apikey", 
                new=2, autoraise=True
            )
        else:
            webbrowser.open("https://aistudio.google.com/app/apikey")
        
        time.sleep(1)
        
        # Create key file if needed
        os.makedirs(os.path.dirname(API_KEY_FILE), exist_ok=True)
        if not os.path.exists(API_KEY_FILE):
            with open(API_KEY_FILE, 'w') as f:
                f.write("")
        
        # Open in Notepad
        subprocess.Popen(['notepad.exe', API_KEY_FILE])
        
        # Try to bring Notepad to foreground
        if sys.platform == 'win32':
            try:
                import win32gui
                import win32con
                time.sleep(0.5)
                def enum_callback(hwnd, results):
                    title = win32gui.GetWindowText(hwnd).lower()
                    if 'gemini-api.key' in title or 'notepad' in title:
                        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                        win32gui.SetForegroundWindow(hwnd)
                win32gui.EnumWindows(enum_callback, None)
            except:
                pass
                
    except Exception as e:
        logger.error(f"[WIZARD] Error: {e}")
        message += "\n\nCouldn't open browser automatically."
        message += "\nPlease visit: https://aistudio.google.com/app/apikey"
    
    plugin.set_keep_session(True)
    return message


# ============================================================================
# COMMAND HANDLERS
# ============================================================================

@plugin.command("query_gemini")
def query_gemini(query: str = None, context: Context = None):
    """
    Handle Gemini query with optional web search.
    
    Args:
        query: The user's question
        context: Conversation history
    """
    global API_KEY, client, SETUP_COMPLETE, conversation_history
    
    # Check if setup is needed - try to load API key silently first
    if not SETUP_COMPLETE or not client:
        logger.info("[QUERY] API not initialized, attempting to load API key...")
        if not load_api_key():
            # Key doesn't exist or is invalid - run setup wizard
            logger.info("[QUERY] API key not configured, running setup wizard")
            return run_setup_wizard()
    
    load_model_config()
    
    logger.info(f"GEMINI: Processing query: {query[:50] if query else 'None'}...")
    
    # Send immediate acknowledgment
    plugin.stream("Searching..._")
    
    # Build context
    if context and context.messages:
        ctx = [{"role": m.role, "content": m.content} for m in context.messages]
    else:
        ctx = conversation_history.copy() if conversation_history else []
    
    # Add query if provided
    if query:
        ctx.append({"role": "user", "content": query})
        if not conversation_history:
            conversation_history.append({"role": "user", "content": query})
    
    if not ctx:
        plugin.set_keep_session(True)
        return "No query provided."
    
    try:
        clean_context = sanitize_history_for_search(ctx)
        stream_gemini_response(clean_context, timeout_seconds=30)
        
        # Stay in conversation mode
        plugin.set_keep_session(True)
        return ""  # Response was streamed
        
    except Exception as e:
        error_str = str(e)
        logger.error(f"GEMINI: API error: {error_str}")
        
        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
            plugin.stream("\n\nRate limit reached. Please try again in a moment.")
            plugin.set_keep_session(True)
            return ""
        
        if 'API_KEY_INVALID' in error_str or 'INVALID_ARGUMENT' in error_str:
            SETUP_COMPLETE = False
            API_KEY = None
            client = None
            return "API key is invalid. Please check your key and try again.\n\n" + run_setup_wizard()
        
        # Keep session active so user can retry
        plugin.set_keep_session(True)
        return "Something went wrong with the API. Please try again."


@plugin.command("on_input")
def on_input(content: str):
    """
    Handle follow-up user input in passthrough mode.
    
    Args:
        content: The user's message
    """
    global SETUP_COMPLETE, client, conversation_history
    
    logger.info(f"[INPUT] Received: {content[:50]}...")
    
    # If setup isn't complete, try to load API key and process the query directly
    if not SETUP_COMPLETE:
        logger.info("[INPUT] Setup not complete, verifying API key...")
        if load_api_key():
            # Key is valid - stream confirmation and process the query immediately
            logger.info("[INPUT] API key verified, processing user query...")
            plugin.stream("API key configured!\n\n")
            conversation_history.append({"role": "user", "content": content})
            return query_gemini(query=content)
        else:
            return run_setup_wizard()
    
    # Check for exit commands (only after setup is complete)
    exit_commands = ['exit', 'quit', 'stop', 'bye', 'done', 'exit gemini', 
                     'stop gemini', 'quit gemini']
    if content.lower().strip() in exit_commands:
        logger.info("[INPUT] Exit command received")
        conversation_history = []
        plugin.set_keep_session(False)
        return "Exiting Gemini mode. Conversation history cleared."
    
    # Check for clear history
    if content.lower().strip() in ['clear', 'reset', 'new conversation', 'clear history']:
        conversation_history = []
        plugin.set_keep_session(True)
        return "Conversation history cleared. Ask me anything!"
    
    # Add user message to history
    conversation_history.append({"role": "user", "content": content})
    
    # Process as query
    return query_gemini(query=content)


# ============================================================================
# INITIALIZATION
# ============================================================================

# DON'T load API key at startup - it makes network calls that block plugin init!
# API key will be loaded lazily when first command is executed.
load_model_config()  # This is local file only, OK to do at startup

if __name__ == "__main__":
    logger.info("Starting Gemini plugin (SDK version)...")
    plugin.run()
