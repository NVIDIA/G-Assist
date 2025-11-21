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

''' Google Gemini G-Assist plugin. '''
import copy
import ctypes
import json
import logging
import os

from ctypes import byref, windll, wintypes, GetLastError, create_string_buffer
import re
import traceback
from typing import Optional

from google import genai
from google.genai.types import (ModelContent, Part, UserContent, GoogleSearch, Tool, GenerateContentConfig)

# Data Types
Response = dict[str, bool | Optional[str]]

# Get the directory where the plugin is deployed
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "gemini")
API_KEY_FILE = os.path.join(PLUGIN_DIR, 'gemini-api.key')
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

# Save log in plugin directory for better organization
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'gemini-plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_KEY = None
client = None
model: str = 'gemini-pro'  # Default model

# PHASE 1-3: Tethered Mode Support
import threading
import time
import webbrowser
import sys

# Heartbeat background thread state
heartbeat_thread = None
heartbeat_active = False

# Setup state
SETUP_COMPLETE = False

# PHASE 3: Conversation history for passthrough mode
conversation_history = []  # Stores {"role": "user/assistant", "content": "..."}

# Helper response generators (PHASE 3: Updated for tethered mode)
def generate_message_response(message: str, awaiting_input: bool = False) -> dict:
    """
    Generate a message response.
    
    PHASE 3: Tethered Mode Protocol
    - awaiting_input=True: Plugin needs more user interaction, stay in passthrough
    - awaiting_input=False: Plugin is done, exit passthrough mode
    """
    return {
        'success': True,
        'message': message,
        'awaiting_input': awaiting_input
    }

def generate_streaming_chunk(message: str) -> dict:
    """
    Generate a streaming message chunk (without 'success' field).
    
    For use during response streaming - doesn't signal completion.
    The final response should use generate_success_response() with awaiting_input.
    """
    return {
        'message': message
    }

def send_heartbeat():
    """Send silent heartbeat to engine (not visible to user)"""
    try:
        heartbeat_msg = {
            "type": "heartbeat",
            "timestamp": time.time()
        }
        write_response(heartbeat_msg)
        logging.info("[HEARTBEAT] Sent heartbeat")
    except Exception as e:
        logging.error(f"[HEARTBEAT] Error: {e}")

def send_status_message(message):
    """Send visible status update to user"""
    try:
        status_msg = {
            "type": "status",
            "message": message
        }
        write_response(status_msg)
        logging.info(f"[STATUS] Sent: {message[:50]}...")
    except Exception as e:
        logging.error(f"[STATUS] Error: {e}")

def start_heartbeat(interval=5):
    """
    Start background thread that sends periodic heartbeats.
    
    Args:
        interval: Seconds between heartbeats (default 5)
    """
    global heartbeat_thread, heartbeat_active
    
    # Stop any existing heartbeat
    stop_heartbeat()
    
    heartbeat_active = True
    
    def heartbeat_loop():
        while heartbeat_active:
            time.sleep(interval)
            if heartbeat_active:
                send_heartbeat()
    
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    logging.info(f"[HEARTBEAT] Started heartbeat: interval={interval}s")

def stop_heartbeat():
    """Stop background heartbeat thread"""
    global heartbeat_active, heartbeat_thread
    heartbeat_active = False
    if heartbeat_thread and heartbeat_thread.is_alive():
        heartbeat_thread.join(timeout=1)
    logging.info("[HEARTBEAT] Stopped heartbeat")

def execute_setup_wizard() -> dict:
    """
    Interactive setup wizard to help users get their Google Gemini API key.
    
    Returns:
        Response with setup instructions and awaiting_input=True
    """
    global API_KEY, SETUP_COMPLETE
    
    # Check if API key file exists and is valid
    global client
    
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as file:
            key = file.read().strip()
            if key and len(key) > 20 and not key.startswith('<insert'):  # Valid looking key
                # Try to verify it actually works with a test API call
                try:
                    test_client = genai.Client(api_key=key, http_options={'timeout': None})
                    # Actually test the key with an API call
                    test_client.models.list()  # This will fail if key is invalid
                    
                    # Success! Update globals
                    client = test_client
                    API_KEY = key
                    SETUP_COMPLETE = True
                    logging.info("[WIZARD] API key verified successfully with test call")
                    return generate_message_response(
                        """[OK] Google Gemini plugin is configured and ready!

You can now ask me questions and I'll search the web for answers.

I'll stay in conversation mode - just keep typing your questions!
""",
                        awaiting_input=True  # Enter conversation mode immediately
                    )
                except Exception as e:
                    logging.error(f"[WIZARD] API key validation failed: {e}")
                    error_msg = f"""
[ERROR] Invalid API Key

The API key in the file appears to be invalid or expired.

Error: {str(e)}

Please:
1. Visit https://aistudio.google.com/app/apikey
2. Generate a new API key
3. Save it to: {API_KEY_FILE}
4. Type 'done' to verify again

Opening browser and file now...
"""
                    try:
                        webbrowser.open("https://aistudio.google.com/app/apikey")
                        os.startfile(API_KEY_FILE)
                    except:
                        pass
                    
                    return generate_message_response(error_msg, awaiting_input=True)
    
    # API key missing or invalid - show setup wizard
    send_status_message("Starting Google Gemini plugin setup wizard...")
    
    message = """
GOOGLE GEMINI PLUGIN - FIRST TIME SETUP
========================================

Welcome! Let's get your Google Gemini API key. This takes about 1 minute.

I'm opening the Google AI Studio in your browser right now...

YOUR TASK - Get Your API Key:
   1. Click "Create API Key" button
   2. A dialog will appear - you have two options:
      - "Create API key in new project" (easiest - recommended)
      - "Create API key in existing project" (if you have one)
   3. Choose "Create API key in new project"
   4. Give your project a name (e.g., "G-Assist")
   5. Click "Create" - your API key will appear
   6. Click "Copy" to copy the API key
   
   7. I'm opening the key file in Notepad for you...
   8. Paste your API key into the file and SAVE it

After saving the API key, send me ANY message (like "done") and I'll verify it!

Opening Google AI Studio and key file now...
""".format(api_key_file=API_KEY_FILE)
    
    try:
        send_status_message("Opening Google AI Studio...")
        
        # Open browser first
        if sys.platform == 'win32':
            webbrowser.get('windows-default').open("https://aistudio.google.com/app/apikey", new=2, autoraise=True)
        else:
            webbrowser.open("https://aistudio.google.com/app/apikey")
        
        # Give browser time to open
        time.sleep(1)
        
        # Create empty key file if it doesn't exist
        os.makedirs(os.path.dirname(API_KEY_FILE), exist_ok=True)
        if not os.path.exists(API_KEY_FILE):
            with open(API_KEY_FILE, 'w') as f:
                f.write("")
        
        send_status_message("Opening API key file in Notepad...")
        
        # Open the file in notepad for user to paste key
        try:
            import subprocess
            # Use subprocess to ensure Notepad opens and comes to foreground
            subprocess.Popen(['notepad.exe', API_KEY_FILE])
            logging.info("[WIZARD] Opened API key file in Notepad")
            
            # Give Notepad time to open
            time.sleep(0.5)
            
            # Try to bring Notepad to foreground (Windows only)
            if sys.platform == 'win32':
                try:
                    import win32gui
                    import win32con
                    time.sleep(0.5)  # Wait for window to appear
                    def enum_callback(hwnd, results):
                        if 'gemini-api.key' in win32gui.GetWindowText(hwnd).lower() or 'notepad' in win32gui.GetWindowText(hwnd).lower():
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            win32gui.SetForegroundWindow(hwnd)
                            logging.info(f"[WIZARD] Brought Notepad to foreground: {win32gui.GetWindowText(hwnd)}")
                    win32gui.EnumWindows(enum_callback, None)
                except Exception as e:
                    logging.warning(f"[WIZARD] Could not bring Notepad to foreground: {e}")
        except Exception as e:
            logging.error(f"[WIZARD] Error opening file in Notepad: {e}")
            send_status_message(f"Could not open Notepad. Please manually open: {API_KEY_FILE}")
        
        logging.info("[WIZARD] Opened Google AI Studio and API key file")
        
    except Exception as e:
        logging.error(f"[WIZARD] Error opening browser: {e}")
        message += f"\n\nError opening browser: {e}\nPlease manually visit: https://aistudio.google.com/app/apikey"
    
    return generate_message_response(message, awaiting_input=True)  # PHASE 3: Stay in passthrough

def main():
    ''' Main entry point.
    
    Sits in a loop listening to a pipe, waiting for commands to be issued. After
    receiving the command, it is processed and the result returned. The loop
    continues until the "shutdown" command is issued.

    Returns:
        0 if no errors occurred during execution; non-zero if an error occurred
    '''
    TOOL_CALLS_PROPERTY = 'tool_calls'
    CONTEXT_PROPERTY = 'messages'
    SYSTEM_INFO_PROPERTY = 'system_info'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'properties'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'

    ERROR_MESSAGE = 'Could not process request.'

    # Generate command handler mapping
    commands = {
        "initialize": execute_initialize_command,
        "shutdown": execute_shutdown_command,
        "query_gemini": execute_query_gemini_command,
    }
    cmd = ''

    logging.info('Google Gemini plugin started.')
    
    # Check if setup is needed and initialize
    global SETUP_COMPLETE, API_KEY, client, conversation_history
    
    # Always start heartbeat the same way
    start_heartbeat(interval=5)
    logging.info("[HEARTBEAT] Started heartbeat thread")
    
    # Check if API key exists and initialize client
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as file:
            key = file.read().strip()
            if key and len(key) > 20 and not key.startswith('<insert'):
                # Try to initialize the client and validate with a test call
                try:
                    test_client = genai.Client(api_key=key, http_options={'timeout': None})
                    # Actually test the API key with a simple call
                    test_client.models.list()  # This will fail if key is invalid
                    
                    # Success - key is valid
                    client = test_client
                    API_KEY = key
                    SETUP_COMPLETE = True
                    logging.info("[INIT] API key validated successfully")
                except Exception as e:
                    # Invalid key - need setup
                    logging.error(f"[INIT] API key validation failed: {e}")
                    SETUP_COMPLETE = False
                    API_KEY = None
                    client = None
                    logging.info("[INIT] Setup wizard will be triggered on first use")
            else:
                # Empty or too short - need setup
                logging.info("[INIT] API key too short, setup needed")
    else:
        # No file - need setup
        logging.info("[INIT] No API key file found, setup needed")
    
    while True:
        response = None
        input = read_command()
        if input is None:
            logging.error('Error reading command')
            continue
        
        logging.info(f'Command: "{input}"')
        
        # PHASE 3: Handle user input passthrough messages
        if isinstance(input, dict) and input.get('msg_type') == 'user_input':
            user_input_text = input.get('content', '')
            logging.info(f'[INPUT] Received user input passthrough: "{user_input_text}"')
            
            # Check if user wants to exit Gemini conversation mode
            if user_input_text.lower() in ['exit gemini', 'stop gemini', 'quit gemini', 'exit google', 'stop', 'exit']:
                logging.info("[INPUT] User requested to exit Gemini conversation mode")
                conversation_history = []  # Clear history
                response = generate_message_response(
                    "[OK] Exiting Google Gemini conversation mode. Conversation history cleared. You can ask me anything else!",
                    awaiting_input=False  # Exit passthrough mode
                )
                write_response(response)
                continue
            
            # Check if user wants to clear conversation history
            if user_input_text.lower() in ['clear history', 'clear', 'reset', 'new conversation']:
                logging.info("[INPUT] User requested to clear conversation history")
                conversation_history = []  # Clear history
                response = generate_message_response(
                    "[OK] Conversation history cleared. Starting fresh! Ask me anything.",
                    awaiting_input=True  # Stay in conversation mode
                )
                write_response(response)
                continue
            
            # Check if setup is needed
            if not SETUP_COMPLETE:
                logging.info("[WIZARD] User input during setup - advancing wizard")
                response = execute_setup_wizard()
                write_response(response)
                continue
            
            # Plugin configured - treat user input as a new Gemini query
            logging.info("[INPUT] Treating user input as new Gemini query in conversation mode")
            
            # Add user message to conversation history
            conversation_history.append({"role": "user", "content": user_input_text})
            
            # Create a synthetic params dict from the user input
            synthetic_params = {'query': user_input_text}
            
            # Pass conversation history for context
            response = execute_query_gemini_command(synthetic_params, conversation_history, "")
            
            # Extract assistant response from the response and add to history
            if response.get('success'):
                # The actual response text was streamed via write_response calls
                # We need to track what was sent - for now, add a placeholder
                # The streaming happens inside execute_query_gemini_command
                logging.info("[INPUT] Query completed, conversation history updated")
            
            logging.info(f"[INPUT] Final response: {response}")
            write_response(response)
            logging.info("[INPUT] Response written to pipe")
            continue

        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY]
                    if cmd in commands:
                        if(cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND):
                            response = commands[cmd]()
                        else:
                            # Check if setup is needed before executing commands
                            if not SETUP_COMPLETE and not API_KEY:
                                logging.info('[COMMAND] API key not configured - starting setup wizard')
                                response = execute_setup_wizard()
                                break
                            response = commands[cmd](
                                input[PARAMS_PROPERTY] if PARAMS_PROPERTY in input else None,
                                input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in input else None,
                                input[SYSTEM_INFO_PROPERTY] if SYSTEM_INFO_PROPERTY in input else None
                            )
                    else:
                        logging.warning(f'Unknown command: {cmd}')
                        response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
                else:
                    logging.warning('Malformed input.')
                    response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')
        else:
            logging.warning('Malformed input.')
            response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

        logging.info(f'Response: {response}')
        write_response(response)

        if cmd == SHUTDOWN_COMMAND:
            stop_heartbeat()
            break

    logging.info('Google Gemini plugin stopped.')
    stop_heartbeat()
    return 0

def remove_unicode(s: str) -> str:
    '''Remove non-ASCII characters from a string.
    
    First decodes escape sequences into Unicode characters, then filters out non-ASCII characters.
    
    Args:
        s: Input string to process
        
    Returns:
        String with only ASCII characters
    '''
    try:
        s_decoded = s.encode('utf-8').decode('unicode_escape')
    except Exception:
        s_decoded = s

    ascii_only = ''.join(c for c in s_decoded if ord(c) < 128)
    return ascii_only

def read_command() -> dict | None:
    ''' Reads a command from the communication pipe.
    
    Reads data in chunks until the full message is received, then processes it as JSON.
    Handles Unicode escapes and ensures the text is printable.

    Returns:
        Command details if the input was proper JSON; `None` otherwise
    '''
    try:
        STD_INPUT_HANDLE = -10
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)

        chunks = []
        while True:
            BUFFER_SIZE = 4096
            message_bytes = wintypes.DWORD()
            buffer = bytes(BUFFER_SIZE)
            success = windll.kernel32.ReadFile(
                pipe,
                buffer,
                BUFFER_SIZE,
                byref(message_bytes),
                None
            )

            if not success:
                logging.error('Error reading from command pipe')
                return None

            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            if message_bytes.value < BUFFER_SIZE:
                break

        retval = ''.join(chunks)
        
        # PHASE 3: Remove <<END>> token if present
        END_TOKEN = '<<END>>'
        if retval.endswith(END_TOKEN):
            retval = retval[:-len(END_TOKEN)]
        
        logging.info(f'Raw Input: {retval[:100]}...')
        clean_text = retval.encode('utf-8').decode('raw_unicode_escape')
        clean_text = ''.join(ch for ch in clean_text if ch.isprintable() or ch in ['\n', '\t', '\r'])
        return json.loads(clean_text)

    except json.JSONDecodeError as e:
        logging.error(f'Received invalid JSON: {clean_text[:200] if "clean_text" in locals() else retval[:200]}')
        logging.exception("JSON decoding failed:")
        return None
    except Exception as e:
        logging.error(f'Exception in read_command(): {str(e)}')
        return None


def write_response(response: Response) -> None:
    ''' Writes a response to the communication pipe.
    
    Converts the response to JSON and sends it through the pipe with an end marker.

    Args:
        response: Dictionary containing return value(s)
    '''
    try:
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)
        
        # Log what we're sending
        msg_type = response.get('type', 'response') if isinstance(response, dict) else 'unknown'
        logging.info(f"[PIPE] Writing message: type={msg_type}, length={message_len} bytes")

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
            None
        )
        
        if success:
            logging.info(f"[PIPE] Write OK - type={msg_type}, bytes={bytes_written.value}/{message_len}")
        else:
            logging.error(f"[PIPE] Write FAILED - type={msg_type}, error={GetLastError()}")

    except Exception as e:
        logging.error(f'Exception in write_response: {e}')
        logging.exception("Full traceback:")


def generate_failure_response(message: str = None, awaiting_input: bool = False) -> Response:
    ''' Generates a response indicating failure.

    Args:
        message: String to be returned in the response (optional)
        awaiting_input: If True, engine stays in passthrough mode (PHASE 3)

    Returns:
        A failure response with the attached message
    '''
    response = { 'success': False, 'awaiting_input': awaiting_input }
    if message is not None:  # Include even if empty string!
        response['message'] = message
    return response


def generate_success_response(message: str = None, awaiting_input: bool = False) -> Response:
    ''' Generates a response indicating success.

    Args:
        message: String to be returned in the response (optional)
        awaiting_input: If True, engine stays in passthrough mode (PHASE 3)

    Returns:
        A success response with the attached message
    '''
    response = { 'success': True, 'awaiting_input': awaiting_input }
    if message is not None:  # Include even if empty string!
        response['message'] = message
    return response


def execute_initialize_command() -> dict:
    ''' Initialize the Gemini API connection.
    
    Reads the API key from file and configures the Gemini client.
    If no key is found, triggers the setup wizard.
    
    Returns:
        Success or failure response
    '''
    global API_KEY, API_KEY_FILE, client, SETUP_COMPLETE

    key = None
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as file:
            key = file.read().strip()

    if not key:
        logging.error('No API key found - triggering setup wizard')
        return execute_setup_wizard()  # PHASE 3: Interactive setup

    try:
        # Configure client with no timeout to prevent hanging on slow networks/proxies
        # 'timeout': None disables all timeouts (connect, read, write, pool)
        client = genai.Client(api_key=key, http_options={'timeout': None})
        logging.info('Successfully configured Gemini API')
        API_KEY = key
        SETUP_COMPLETE = True
        # Return with awaiting_input=True to stay in conversational mode
        return generate_success_response("Gemini initialized. Ask me anything!", awaiting_input=True)
    except Exception as e:
        logging.error(f'Configuration failed: {str(e)}')
        API_KEY = None
        SETUP_COMPLETE = False
        return generate_failure_response(str(e))

def execute_shutdown_command() -> dict:
    ''' Cleanup resources.
    
    Returns:
        Success response
    '''
    logging.info('Gemini plugin shutdown')
    return generate_success_response()

def convert_oai_to_gemini_history(oai_history):
    """Convert OpenAI-style chat history to Gemini-compatible format.
    
    Args:
        oai_history: OpenAI format history
        
    Returns:
        List of messages in Gemini format
    """
    gemini_history = []
    for msg in oai_history:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_history.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })
    return gemini_history

def convert_openai_history_to_google_gemini(openai_history):
    """Convert an OpenAI chat history to a list formatted for Google Gemini.

    Args:
        openai_history: List of dictionaries with 'role' and 'content' keys

    Returns:
        List of UserContent or ModelContent objects
    """
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

def extract_parts(history):
    """Extract text parts from message history.
    
    Args:
        history: Message history
        
    Returns:
        List of Part objects containing text
    """
    parts = []
    for message in history:
        for part in message.parts:
            if part.text:
                parts.append(Part.from_text(text=part.text))
    return parts

def sanitize_history_for_search(history: list) -> list:
    """Sanitize conversation history for search queries.
    
    1. Removes complex tool calls (JSON blobs) that confuse Gemini.
    2. Limits history depth to keep focus on the current query.
    3. Replaces tool calls with simple text summaries if needed.
    """
    clean_history = []
    
    # Only keep the last 4 turns (2 user, 2 assistant) to prevent context pollution
    # We need at least 1 previous turn for "follow-up" questions to work
    start_idx = max(0, len(history) - 4)
    recent_history = history[start_idx:]
    
    for msg in recent_history:
        content = msg.get('content', '')
        role = msg.get('role', 'user')
        
        # If content looks like a JSON tool call, simplify it
        if '"tool":' in content and '"func":' in content:
            if role == 'assistant':
                # Replace tool call with a generic action description
                # This stops Gemini from apologizing for missing tools
                clean_history.append({"role": "assistant", "content": "I checked the information for you."})
            continue
            
        clean_history.append(msg)
        
    return clean_history

def execute_query_gemini_command(params: dict = None, context: dict = None, system_info: str = None) -> dict:
    ''' Handle Gemini query with conversation history.
    
    Processes the query by first classifying whether it needs search or LLM response,
    then routes to the appropriate handler. Handles streaming responses back to the client.
    
    Args:
        params: Additional parameters for the query
        context: Conversation history
        system_info: System information including game data
        
    Returns:
        Success or failure response
    '''
    global API_KEY, CONFIG_FILE, model, client, SETUP_COMPLETE, conversation_history

    # PHASE 3: If API key missing or not configured, trigger setup wizard
    if API_KEY is None or not SETUP_COMPLETE or client is None:
        logging.error('API key is None or not configured - triggering setup wizard')
        wizard_response = execute_setup_wizard()
        
        # If wizard completed setup, try to execute the query now
        if not wizard_response.get('awaiting_input', False) and SETUP_COMPLETE and client:
            logging.info('GEMINI_HANDLER: Setup complete, executing original query now')
            # Recursively call this function - now that client is initialized
            # Fall through to execute the query below
        else:
            # Setup still needs user input, return wizard response
            return wizard_response
    
    # PHASE 3: Initialize conversation history if this is a new conversation
    # (coming from normal tool call, not passthrough)
    if not context or len(context) == 0:
        # Fresh query - use our internal conversation history
        context = conversation_history if conversation_history else []
        logging.info(f"GEMINI_HANDLER: Using internal conversation history (length: {len(context)})")
    else:
        # Context provided from tool call - this is first query, initialize our history
        if len(conversation_history) == 0:
            conversation_history = context.copy()
            logging.info(f"GEMINI_HANDLER: Initialized conversation history from tool call (length: {len(context)})")

    # Load model config
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
            model = config.get('model', model)

    try:
        logging.info("GEMINI_HANDLER: Starting request processing")
        
        # PHASE 3: Prioritize explicit query parameter over context
        # This handles cases where LLM reformulates the query (e.g., "yes" -> "latest NFL announcements")
        if params and 'query' in params and params['query']:
            # Explicit query provided - use it and append to context
            query_from_params = params['query']
            logging.info(f"GEMINI_HANDLER: Using explicit query parameter: {query_from_params[:50]}...")
            
            if not context or len(context) == 0:
                context = [{"role": "user", "content": query_from_params}]
                logging.info("GEMINI_HANDLER: Created new context from query parameter")
            else:
                # Replace the last user message with the explicit query
                # This handles cases where user said "yes" but LLM reformulated it
                context = context[:-1] + [{"role": "user", "content": query_from_params}]
                logging.info("GEMINI_HANDLER: Replaced last context entry with explicit query parameter")
        elif not context or len(context) == 0:
            logging.error("GEMINI_HANDLER: No context or query provided")
            return generate_failure_response("No query provided")
        
        # Store the incoming prompt
        prompt = context[-1]["content"] if context else ""
        logging.info(f"GEMINI_HANDLER: Received prompt: {prompt[:50]}...")
        # Preserve the original context
        incoming_context = copy.deepcopy(context)
        logging.info(f"GEMINI_HANDLER: Context length: {len(context)}")
        
        # Simplified: Always use Gemini with grounding enabled
        # Gemini 2.0 Flash will automatically use Google Search when needed
        logging.info("GEMINI_HANDLER: Using Gemini with automatic grounding")
        
        try:
            # Convert OpenAI-style context to Google Gemini format
            # Sanitize history first to remove confusing tool calls
            clean_context = sanitize_history_for_search(context)
            gemini_history = convert_openai_history_to_google_gemini(clean_context)
            parts = extract_parts(gemini_history)
            
            # Use Gemini with Google Search grounding enabled
            # Gemini will automatically decide when to search
            response = client.models.generate_content_stream(
                model=model,
                contents=parts,
                config=GenerateContentConfig(
                    tools=[Tool(google_search=GoogleSearch())],
                ),
            )
            
            # Stream the response
            logging.info("GEMINI_HANDLER: Streaming response with automatic grounding")
            
            full_response = ""
            for chunk in response:
                if chunk.text:
                    logging.info(f'GEMINI_HANDLER: Response chunk: {chunk.text[:30]}...')
                    write_response(generate_streaming_chunk(chunk.text))
                    full_response += chunk.text
            
            # Add assistant response to conversation history
            if full_response and len(conversation_history) > 0:
                conversation_history.append({"role": "assistant", "content": full_response})
                logging.info(f"GEMINI_HANDLER: Added response to history (length: {len(full_response)} chars)")
            
            logging.info("GEMINI_HANDLER: Response completed successfully")
            # PHASE 3: Stay in conversational mode - keep awaiting_input=true
            return generate_success_response("", awaiting_input=True)  # Empty message, but field must exist!
        except Exception as error:
            error_str = str(error)
            # Check for 429 (Rate Limit) specifically
            if '429' in error_str or 'RESOURCE_EXHAUSTED' in error_str:
                logging.error(f'GEMINI_HANDLER: Rate limit hit during grounding: {error_str}')
                error_msg = "I'm sorry, I'm currently overloaded with requests (Rate Limit Exceeded). Please try again in a few moments."
                write_response(generate_streaming_chunk(error_msg))
                return generate_success_response("", awaiting_input=True)
            
            # If grounding fails for other reasons, fall back to LLM without grounding
            logging.error(f'GEMINI_HANDLER: Grounding failed, falling back to LLM: {error_str}')
            return execute_llm_query(convert_openai_history_to_google_gemini(context[:-1]), incoming_context, system_info)
        
    except Exception as e:
        # Catch and log any other exceptions that occur
        error_str = str(e)
        logging.error(f'GEMINI_HANDLER: API error: {error_str}')
        logging.error(f'GEMINI_HANDLER: Stack trace: {traceback.format_exc()}')
        
        # PHASE 3: Check if error is due to invalid API key - trigger setup wizard
        if 'API_KEY_INVALID' in error_str or 'API key not valid' in error_str or '400' in error_str or 'INVALID_ARGUMENT' in error_str:
            logging.error('GEMINI_HANDLER: Invalid API key detected - triggering setup wizard')
            SETUP_COMPLETE = False
            API_KEY = None
            client = None
            
            # Show error context before wizard
            error_context = f"[ERROR] API Key Invalid\n\nYour Google Gemini API key is invalid or expired.\nError: {error_str[:200]}\n\nLet's get you set up with a valid key...\n\n"
            wizard_response = execute_setup_wizard()
            
            # Prepend error context to wizard message
            if 'message' in wizard_response:
                wizard_response['message'] = error_context + wizard_response['message']
            
            return wizard_response
        
        return generate_failure_response(f'API error: {error_str}')

def execute_llm_query(gemini_history, incoming_context, system_info):
    """Execute LLM query path.
    
    Handles knowledge-based responses using the LLM without search.
    Augments the prompt with system information and streams the response.
    
    Args:
        gemini_history: Conversation history in Gemini format
        incoming_context: Original conversation context
        system_info: System information including game data
        
    Returns:
        Success response after streaming the answer
    """
    global conversation_history, client, model
    
    logging.info("GEMINI_HANDLER: Query classified as LLM path")
    
    # PHASE 3: Show progress during LLM query
    send_status_message("Thinking...")
    
    # Construct prompt with user query FIRST, then context as supplementary info
    user_query = incoming_context[-1]['content']
    aug_prompt = f"""Answer this question: {user_query}

IMPORTANT: Focus on answering the user's question above. The following context is only for reference if relevant:

Context: You are a helpful AI assistant within the Nvidia G-Assist ecosystem. Keep responses concise (under 100 words if possible). 
{f"System info (only relevant for game/GPU questions): {system_info}" if system_info else ""}

Remember: The user's question takes priority. Only use the context if it's directly relevant to their question."""
    logging.info("GEMINI_HANDLER: Reset context with system information")
    
    chat = client.chats.create(model=model, history=gemini_history)
    logging.info("GEMINI_HANDLER: Created new chat with updated history")
    
    # Track the full response for conversation history
    full_response = ""
    
    response = chat.send_message_stream(aug_prompt)
    for chunk in response:
        if chunk.text:
            logging.info(f'GEMINI_HANDLER: Response chunk: {chunk.text[:30]}...')
            write_response(generate_streaming_chunk(chunk.text))
            full_response += chunk.text
    
    # Add assistant response to conversation history
    if full_response and len(conversation_history) > 0:
        conversation_history.append({"role": "assistant", "content": full_response})
        logging.info(f"GEMINI_HANDLER: Added assistant response to history (length: {len(full_response)} chars)")
    
    logging.info("GEMINI_HANDLER: LLM response completed successfully")
    # PHASE 3: Stay in conversational mode - keep awaiting_input=true
    return generate_success_response("", awaiting_input=True)  # Empty message, but field must exist!

if __name__ == '__main__':
    main()
