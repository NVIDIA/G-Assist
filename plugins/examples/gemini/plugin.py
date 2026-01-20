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

import atexit
import json
import logging
import os
import sys
import time
import queue
import threading
import webbrowser
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

os.makedirs(PLUGIN_DIR, exist_ok=True)

# Use SDK's logging (writes to gassist_sdk.log)
logger = logging.getLogger(__name__)


def _cleanup_resources():
    """Clean up genai client HTTP connections on shutdown."""
    global client
    if client is not None:
        try:
            if hasattr(client, '_http_client') and client._http_client:
                client._http_client.close()
            elif hasattr(client, 'close'):
                client.close()
        except Exception:
            pass


# Register cleanup to run on exit
atexit.register(_cleanup_resources)


# ============================================================================
# GLOBAL STATE
# ============================================================================
API_KEY: Optional[str] = None
client = None
model: str = 'gemini-2.5-flash'  # Fast model, override via config.json
SETUP_COMPLETE = False
conversation_history = []  # Stores {"role": "user/assistant", "content": "..."}
PENDING_CALL: Optional[dict] = None  # {"func": callable, "args": {...}}

# Store last query for retry after API key change
_last_query: Optional[str] = None

# Track API key file modification time to detect external changes
_api_key_file_mtime: float = 0.0


def store_pending_call(func, **kwargs):
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
    global API_KEY, client, SETUP_COMPLETE, _api_key_file_mtime
    
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
        # Track file modification time to detect external changes
        _api_key_file_mtime = os.path.getmtime(API_KEY_FILE)
        logger.info("[INIT] API key validated successfully")
        return True
    except Exception as e:
        logger.error(f"[INIT] API key validation failed: {e}")
        return False


def load_api_key_with_keepalive() -> bool:
    """
    Load API key in background thread while sending keepalives.
    
    This prevents heartbeat timeout during slow operations like:
    - Importing google.genai library (2-5 seconds)
    - Validating API key via network call (5-10 seconds)
    
    Returns:
        True if API key loaded and validated successfully, False otherwise.
    """
    result_queue = queue.Queue()
    
    def worker():
        try:
            success = load_api_key()
            result_queue.put(("success", success))
        except Exception as e:
            logger.error(f"[INIT] API key loading error: {e}")
            result_queue.put(("error", str(e)))
    
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    
    # Send keepalives every 2 seconds while waiting for background thread
    logger.info("[INIT] Loading API key with keepalives...")
    while thread.is_alive():
        plugin.stream(".")
        thread.join(timeout=2.0)
    
    # Get result from completed thread
    try:
        msg_type, result = result_queue.get(timeout=1.0)
        if msg_type == "error":
            return False
        return result
    except queue.Empty:
        logger.error("[INIT] API key loading thread completed but no result received")
        return False


def _check_api_key_file_changed() -> bool:
    """Check if API key file was modified externally and reload if needed."""
    global API_KEY, client, SETUP_COMPLETE, _api_key_file_mtime
    
    if not os.path.isfile(API_KEY_FILE):
        return False
    
    try:
        current_mtime = os.path.getmtime(API_KEY_FILE)
        if current_mtime > _api_key_file_mtime:
            logger.info("[INIT] API key file changed externally, reloading...")
            # Reset state to force reload
            API_KEY = None
            client = None
            SETUP_COMPLETE = False
            return load_api_key_with_keepalive()
    except Exception as e:
        logger.debug(f"[INIT] Error checking API key file mtime: {e}")
    
    return True  # No change, current key is still valid


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


def stream_gemini_response(context: list, timeout_seconds: int = 120) -> str:
    """
    Stream Gemini response with timeout.
    
    Args:
        context: List of message dicts with role/content
        timeout_seconds: Maximum time to wait (default 120s for web search queries)
        
    Returns:
        Full response text
    """
    global client, model, conversation_history
    
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
    if load_api_key_with_keepalive():
        plugin.set_keep_session(True)
        return """_
Google Gemini plugin is configured and ready!

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

**Step 2: Paste Your Key Here**

Just paste your API key in this chat and I'll save it for you.

_(Your key starts with "AIza...")_\r"""
    
    try:
        # Open browser
        if sys.platform == 'win32':
            webbrowser.get('windows-default').open(
                "https://aistudio.google.com/app/apikey", 
                new=2, autoraise=True
            )
        else:
            webbrowser.open("https://aistudio.google.com/app/apikey")
                
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
def query_gemini(query: str = None, context: Context = None, _from_on_input: bool = False, _from_pending: bool = False):
    """
    Handle Gemini query with optional web search.
    
    Args:
        query: The user's question
        context: Conversation history
        _from_on_input: Internal flag - True when called from on_input (italics already escaped)
        _from_pending: Internal flag - True when called from execute_pending_call
    """
    global API_KEY, client, SETUP_COMPLETE, conversation_history, _last_query
    
    # Check if API key file was modified externally
    _check_api_key_file_changed()
    
    # Check if setup is needed - try to load API key silently first
    if not SETUP_COMPLETE or not client:
        logger.info("[QUERY] API not initialized, attempting to load API key...")
        if not load_api_key_with_keepalive():
            # Key doesn't exist or is invalid - store pending call and run setup wizard
            logger.info("[QUERY] API key not configured, storing pending call and running setup wizard")
            store_pending_call(query_gemini, query=query, context=context)
            return run_setup_wizard()
    
    load_model_config()
    
    # Store query for retry after API key errors
    if query:
        _last_query = query
        logger.info(f"[QUERY] Stored _last_query: {_last_query[:50]}...")
    
    logger.info(f"GEMINI: Processing query: {query[:50] if query else 'None'}...")
    
    # Send immediate acknowledgment
    if not _from_on_input and not _from_pending:
        plugin.stream("_ ")  # Close engine's italic
    plugin.stream("_Searching..._")
    
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
        return "_ **Who should I search for?** Please provide a question."
    
    try:
        clean_context = sanitize_history_for_search(ctx)
        stream_gemini_response(clean_context, timeout_seconds=120)
        
        # Clear last query after successful response
        _last_query = None
        
        # Stay in conversation mode
        plugin.set_keep_session(True)
        return ""  # Response was streamed
        
    except Exception as e:
        error_str = str(e).upper()
        logger.error(f"GEMINI: API error: {error_str}")
        
        # API key issues - prompt for new key
        key_error_indicators = [
            'API_KEY_INVALID', 'INVALID_API_KEY', 'API KEY',
            'UNAUTHENTICATED', '401',
            'PERMISSION_DENIED', '403',
            'INVALID_ARGUMENT',
        ]
        if any(indicator in error_str for indicator in key_error_indicators):
            logger.info("[ERROR] API key issue detected, prompting for new key")
            SETUP_COMPLETE = False
            API_KEY = None
            client = None
            plugin.set_keep_session(True)
            return (
                "_ **API key issue detected.**\n\n"
                "Your API key may be invalid, expired, or lack permissions.\n\n"
                "Please paste a new API key to continue.\n\n"
                "_(Get one at https://aistudio.google.com/app/apikey)_"
            )
        
        # Rate limit / quota - offer to use different key
        if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str or 'QUOTA' in error_str:
            logger.info("[ERROR] Rate limit or quota exceeded")
            plugin.set_keep_session(True)
            return (
                "_ **Rate limit or quota exceeded.**\n\n"
                "You can:\n"
                "- Wait a moment and try again\n"
                "- Paste a different API key to switch accounts\n\n"
                "_(Your key starts with \"AIza...\")_"
            )
        
        # Keep session active so user can retry
        plugin.set_keep_session(True)
        return "_ **Error:** Something went wrong with the API. Please try again."


@plugin.command("on_input")
def on_input(content: str):
    """
    Handle follow-up user input in passthrough mode.
    
    Args:
        content: The user's message
    """
    global SETUP_COMPLETE, client, conversation_history, API_KEY, _last_query
    
    # Check if API key file was modified externally
    _check_api_key_file_changed()
    
    logger.info(f"[INPUT] Received: {content[:50]}...")
    
    # Save query for potential retry (before any checks that might fail)
    # Only save if it's not an API key
    if 'AIza' not in content:
        _last_query = content
        logger.info(f"[INPUT] Saved _last_query: {content[:50]}...")
    
    # Always check for API key input first (allows switching keys after errors)
    # Check if input looks like an API key (starts with AIza, ~39 chars)
    # Also handle common cases: quotes, "my key is...", etc.
    content_stripped = content.strip().strip('"\'')  # Remove quotes
    
    # Extract API key if user typed something like "my key is AIza..."
    if 'AIza' in content_stripped:
        # Find the API key portion
        idx = content_stripped.find('AIza')
        potential_key = content_stripped[idx:].split()[0].strip('"\'.,;:')
        
        if potential_key.startswith('AIza') and len(potential_key) >= 35:
            logger.info("[INPUT] Detected API key input, saving to file...")
            try:
                os.makedirs(os.path.dirname(API_KEY_FILE), exist_ok=True)
                with open(API_KEY_FILE, 'w') as f:
                    f.write(potential_key)
                logger.info("[INPUT] API key saved to file")
                
                # Reset state to force re-validation with new key
                SETUP_COMPLETE = False
                API_KEY = None
                client = None
                
                # Now try to load and validate it
                if load_api_key_with_keepalive():
                    logger.info("[INPUT] API key validated")
                    plugin.stream("_ ")  # Close engine's italic
                    plugin.stream("_API key saved and verified!_\n\n")
                    
                    # Try pending call first (from setup wizard)
                    result = execute_pending_call()
                    if result is not None:
                        return result
                    
                    # No pending call - check if we have a last query to retry
                    logger.info(f"[INPUT] Checking _last_query: {_last_query}")
                    if _last_query:
                        saved_query = _last_query
                        logger.info(f"[INPUT] Retrying last query: {saved_query[:50]}...")
                        return query_gemini(query=saved_query, _from_on_input=True)
                    
                    plugin.set_keep_session(True)
                    return "You're all set! Ask me anything."
                else:
                    plugin.set_keep_session(True)
                    return (
                        "**API key saved but validation failed.**\n\n"
                        "Please check that you copied the complete key from Google AI Studio.\n\n"
                        "Paste your API key again to retry."
                    )
            except Exception as e:
                logger.error(f"[INPUT] Error saving API key: {e}")
                plugin.set_keep_session(True)
                return f"**Error saving API key:** {e}\n\nPlease try again."
    
    # If setup isn't complete, try to load existing key or prompt for one
    if not SETUP_COMPLETE:
        logger.info("[INPUT] Setup not complete, checking for existing key...")
        
        if load_api_key_with_keepalive():
            logger.info("[INPUT] API key verified from file, executing pending call...")
            plugin.stream("_ ")
            plugin.stream("_Gemini plugin configured!_\n\n")
            result = execute_pending_call()
            if result is not None:
                return result
            plugin.set_keep_session(True)
            return "You're all set! Ask me anything."
        
        # No valid key yet - prompt user with context
        plugin.set_keep_session(True)
        if _last_query:
            return (
                "**API key invalid or expired.**\n\n"
                "Please paste a valid Gemini API key to continue.\n\n"
                "Your query will be sent automatically once the key is verified.\n\n"
                "_(Get a key at https://aistudio.google.com/app/apikey)_"
            )
        else:
            return (
                "**Waiting for your API key.**\n\n"
                "Please paste your Gemini API key here.\n\n"
                "_(It starts with \"AIza...\")_"
            )
    
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
