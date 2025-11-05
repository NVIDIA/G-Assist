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
import webbrowser
import subprocess

from ctypes import byref, windll, wintypes, GetLastError, create_string_buffer
import re
import traceback
from typing import Optional

from google import genai
from google.genai.types import (ModelContent, Part, UserContent, GoogleSearch, Tool, GenerateContentConfig)

# Data Types
Response = dict[str, bool | Optional[str]]

# Get the directory where the script is running from
API_KEY_FILE = os.path.join(os.environ.get("PROGRAMDATA", "."), 'NVIDIA Corporation', 'nvtopps', 'rise', 'plugins', 'google', 'google.key')
CONFIG_FILE = os.path.join(os.environ.get("PROGRAMDATA", "."), 'NVIDIA Corporation', 'nvtopps', 'rise', 'plugins', 'google', 'config.json')

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'gemini.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_KEY = None
client = None
model: str = 'gemini-pro'  # Default model
setup_windows_opened = False  # Track if we've already opened setup windows this session

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
    while True:
        response = None
        input = read_command()
        if input is None:
            logging.error('Error reading command')
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
            break

    logging.info('Google Gemini plugin stopped.')
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
        logging.info(f'Raw Input: {retval}')
        clean_text = retval.encode('utf-8').decode('raw_unicode_escape')
        clean_text = ''.join(ch for ch in clean_text if ch.isprintable() or ch in ['\n', '\t', '\r'])
        return json.loads(clean_text)

    except json.JSONDecodeError:
        logging.error(f'Received invalid JSON: {clean_text}')
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

        bytes_written = wintypes.DWORD()
        windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
            None
        )

    except Exception:
        logging.error('Unknown exception caught.')
        pass


def generate_failure_response(message: str = None) -> Response:
    ''' Generates a response indicating failure.

    Args:
        message: String to be returned in the response (optional)

    Returns:
        A failure response with the attached message
    '''
    response = { 'success': False }
    if message:
        response['message'] = message
    return response


def generate_success_response(message: str = None) -> Response:
    ''' Generates a response indicating success.

    Args:
        message: String to be returned in the response (optional)

    Returns:
        A success response with the attached message
    '''
    response = { 'success': True }
    if message:
        response['message'] = message
    return response


def generate_message_response(message:str):
    ''' Generates a message response.

    Args:
        message: String to be returned to the driver

    Returns:
        A message response dictionary
    '''
    return { 'message': message }


def open_file_in_notepad(file_path: str, show_maximized: bool = False) -> bool:
    ''' Opens a file in Notepad using Windows ShellExecute API.
    
    Args:
        file_path: Path to the file to open
        show_maximized: If True, opens the window maximized; otherwise normal
        
    Returns:
        True if successful, False otherwise
    '''
    try:
        # SW_SHOWNORMAL = 1 (normal window)
        # SW_SHOWMAXIMIZED = 3 (maximized window)
        # SW_SHOW = 5 (activates and displays in current size/position)
        show_cmd = 3 if show_maximized else 5
        
        # Use ShellExecuteW to open the file with Notepad
        result = ctypes.windll.shell32.ShellExecuteW(
            None,           # hwnd
            "open",         # operation
            "notepad.exe",  # file
            file_path,      # parameters
            None,           # directory
            show_cmd        # show command
        )
        
        # ShellExecute returns a value > 32 on success
        if result > 32:
            logging.info(f'Successfully opened {file_path} in Notepad')
            return True
        else:
            logging.error(f'Failed to open file in Notepad. Return code: {result}')
            return False
            
    except Exception as e:
        logging.error(f'Exception opening file in Notepad: {e}')
        return False


def open_browser_maximized(url: str) -> bool:
    ''' Opens URL in default browser and brings the window to foreground.
    
    Args:
        url: URL to open
        
    Returns:
        True if successful, False otherwise
    '''
    try:
        import time
        
        # Open the URL in the default browser
        webbrowser.open(url)
        logging.info(f'Opened URL in browser: {url}')
        
        # Give the browser a moment to start
        time.sleep(0.5)
        
        # Find and activate the browser window
        # This brings the browser to the foreground
        EnumWindows = ctypes.windll.user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
        GetWindowText = ctypes.windll.user32.GetWindowTextW
        GetWindowTextLength = ctypes.windll.user32.GetWindowTextLengthW
        IsWindowVisible = ctypes.windll.user32.IsWindowVisible
        SetForegroundWindow = ctypes.windll.user32.SetForegroundWindow
        ShowWindow = ctypes.windll.user32.ShowWindow
        
        def foreach_window(hwnd, lParam):
            if IsWindowVisible(hwnd):
                length = GetWindowTextLength(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                GetWindowText(hwnd, buff, length + 1)
                title = buff.value.lower()
                
                # Check if it's a browser window (common browser names in title)
                browser_indicators = ['chrome', 'firefox', 'edge', 'brave', 'opera', 'google', 'mozilla']
                if any(indicator in title for indicator in browser_indicators):
                    # Show the window if minimized (SW_RESTORE = 9)
                    ShowWindow(hwnd, 9)
                    # Bring to foreground
                    SetForegroundWindow(hwnd)
                    logging.info(f'Brought browser window to foreground: {title}')
                    return False  # Stop enumerating
            return True
        
        EnumWindows(EnumWindowsProc(foreach_window), 0)
        return True
        
    except Exception as e:
        logging.error(f'Exception in open_browser_maximized: {e}')
        # Fallback to regular webbrowser.open if custom method fails
        try:
            webbrowser.open(url)
            return True
        except:
            return False


def execute_initialize_command() -> dict:
    ''' Initialize the Gemini API connection.
    
    Reads the API key from file and configures the Gemini client.
    If no key is found, opens browser and provides interactive setup instructions.
    
    Returns:
        Success or failure response
    '''
    global API_KEY, API_KEY_FILE, client, setup_windows_opened

    key = None
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as file:
            key = file.read().strip()
            # Check if it's the placeholder text
            if key.startswith("<insert your API key") or key.startswith("YOUR_API_KEY_HERE"):
                key = None

    if not key:
        logging.error('No API key found')
        
        # Only open setup windows if we haven't already done so this session
        if not setup_windows_opened:
            # Auto-open Google AI Studio API key page in browser (brings to foreground)
            try:
                open_browser_maximized("https://aistudio.google.com/app/apikey")
                logging.info('Opened Google AI Studio API key page in browser')
            except Exception as e:
                logging.warning(f'Could not open browser: {e}')
            
            # Auto-open the API key file in Notepad (normal window, not minimized)
            try:
                open_file_in_notepad(API_KEY_FILE, show_maximized=False)
                logging.info('Opened API key file in Notepad')
            except Exception as e:
                logging.warning(f'Could not open API key file: {e}')
            
            setup_windows_opened = True
        
        # Provide helpful setup message
        setup_message = (
            "\n**Welcome to the Gemini Plugin**\n\n"
            "To get started, you'll need a free Google AI API key.\n\n"
            "**I've opened two windows for you:**\n"
            "    1. Your browser - Google AI Studio (to get the key)\n"
            "    2. Notepad - google.key file (to paste the key)\n\n"
            "**Quick Setup (90 seconds):**\n\n"
            "**Step 1: Get Your API Key** (in your browser window)\n"
            "   1. Click the \"Create API key\" button\n"
            "   2. Sign in with Google if prompted\n"
            "   3. Click \"Create API key in new project\" (easiest option)\n"
            "   4. Copy the API key that appears\n\n"
            "**Step 2: Save Your Key** (in the Notepad window)\n"
            "   1. Switch to the Notepad window I opened\n"
            "   2. Select all (Ctrl+A) and delete the template\n"
            "   3. Paste your API key (Ctrl+V)\n"
            "   4. Save (Ctrl+S) and close Notepad\n\n"
            "**Step 3: Ask Your Question**\n"
            "   1. Come back here and send your prompt\n"
            "   2. G-Assist will automatically detect the new key\n"
            "   3. No restart needed!\n\n"
            "**Note:** The API is completely free and takes less than 2 minutes to set up.\n\n"
            "**Need help?** Visit: https://github.com/NVIDIA/G-Assist/tree/main/plugins/examples/gemini\n"
        )
        
        write_response(generate_message_response(setup_message))
        return generate_success_response() # this allows us to print the error ##bug to be fixed in driver

    try:
        client = genai.Client(api_key=key)
        logging.info('Successfully configured Gemini API')
        API_KEY = key
        
        # Send a friendly welcome message
        welcome_message = (
            "**Gemini Plugin Ready**\n\n"
            "I'm powered by Google's Gemini AI and ready to help you with:\n"
            "\n\t Knowledge questions and explanations\n"
            "\n\t Real-time web searches\n"
            "\n\t Gaming tips and strategies\n\n"
            "Just ask me anything!"
        )
        write_response(generate_message_response(welcome_message))
        
        return generate_success_response()
    except Exception as e:
        logging.error(f'Configuration failed: {str(e)}')
        API_KEY = None
        
        # Only open setup windows if we haven't already done so this session
        if not setup_windows_opened:
            # Auto-open browser to get a new key (brings to foreground)
            try:
                open_browser_maximized("https://aistudio.google.com/app/apikey")
                logging.info('Opened Google AI Studio for new API key')
            except Exception:
                pass
            
            # Auto-open the key file for editing
            try:
                open_file_in_notepad(API_KEY_FILE, show_maximized=False)
                logging.info('Opened API key file for editing')
            except Exception:
                pass
            
            setup_windows_opened = True
        
        # Provide actionable error message
        error_message = (
            "\n**API Key Error**\n\n"
            "Your API key appears to be invalid or expired.\n\n"
            "**I've opened two windows to help you fix this:**\n"
            "    1. Browser - Get a new API key\n"
            "    2. Notepad - Paste the new key\n\n"
            "**Quick Fix (60 seconds):**\n"
            "    1. In your browser - Generate a new API key\n"
            "    2. In Notepad - Replace the old key with the new one\n"
            "    3. Save (Ctrl+S) and close Notepad\n"
            "    4. Just try your request again - No restart needed!\n\n"
            f"**Technical details:** {str(e)}"
        )
        write_response(generate_message_response(error_message))
        
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
    global API_KEY, CONFIG_FILE, model, client, setup_windows_opened

    # Re-check for API key if it was missing before (user may have just added it)
    if API_KEY is None:
        logging.info('API_KEY is None, attempting to re-read from file')
        key = None
        if os.path.isfile(API_KEY_FILE):
            try:
                with open(API_KEY_FILE) as file:
                    key = file.read().strip()
                    # Check if it's the placeholder text
                    if key and not key.startswith("<insert your API key") and not key.startswith("YOUR_API_KEY_HERE") and len(key) > 10:
                        # Try to initialize with the new key
                        try:
                            client = genai.Client(api_key=key)
                            API_KEY = key
                            logging.info('Successfully initialized with newly added API key')
                            
                            # Send welcome message
                            welcome_message = (
                                "**Gemini Plugin Ready**\n\n"
                                "Your API key is now configured! I'm powered by Google's Gemini AI and ready to help.\n\n"
                            )
                            write_response(generate_message_response(welcome_message))
                            # Continue to process the query below
                        except Exception as init_error:
                            logging.error(f'Failed to initialize with new key: {init_error}')
                            API_KEY = None
            except Exception as read_error:
                logging.error(f'Failed to read API key file: {read_error}')
    
    if API_KEY is None:
        # Only open setup windows if we haven't already done so this session
        if not setup_windows_opened:
            # Auto-open the API key page in browser (brings to foreground)
            try:
                open_browser_maximized("https://aistudio.google.com/app/apikey")
                logging.info('Opened Google AI Studio API key page for user')
            except Exception as e:
                logging.warning(f'Could not open browser: {e}')
            
            # Auto-open the API key file in Notepad (normal window, not minimized)
            try:
                open_file_in_notepad(API_KEY_FILE, show_maximized=False)
                logging.info('Opened API key file in Notepad for user')
            except Exception as e:
                logging.warning(f'Could not open API key file: {e}')
            
            setup_windows_opened = True
        
        ERROR_MESSAGE = (
            "\n**Gemini API Key Required**\n\n"
            "I need a Google AI API key to answer your question.\n\n"
            "**I've opened two windows for you:**\n"
            "    1. Your browser - Google AI Studio (to get the key)\n"
            "    2. Notepad - google.key file (to paste the key)\n\n"
            "**Quick Setup (90 seconds):**\n\n"
            "**Step 1: Get Your Free API Key**\n"
            "   1. Switch to your browser window\n"
            "   2. Click the \"Create API key\" button\n"
            "   3. Click \"Create API key in new project\"\n"
            "   4. Copy the API key that appears\n\n"
            "**Step 2: Save Your Key**\n"
            "   1. Switch to the Notepad window\n"
            "   2. Select all (Ctrl+A) and delete the template\n"
            "   3. Paste your API key (Ctrl+V)\n"
            "   4. Save (Ctrl+S) and close Notepad\n\n"
            "**Step 3: Ask Your Question**\n"
            "   1. Come back here and send your prompt again\n"
            "   2. G-Assist will automatically detect the new key\n"
            "   3. No restart needed!\n\n"
            "**Note:** The API is free and this takes less than 2 minutes.\n\n"
            "**Still stuck?** Visit: https://github.com/NVIDIA/G-Assist/tree/main/plugins/examples/gemini"
        )
        write_response(generate_message_response(ERROR_MESSAGE))
        return generate_success_response() #print nothing, the initialize will have done so ## bug to be fixed in driver

    # Load model config
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
            model = config.get('model', model)

    try:
        logging.info("GEMINI_HANDLER: Starting request processing")

        # Validate that context exists
        if not context or len(context) == 0:
            logging.error("GEMINI_HANDLER: No context provided")
            return generate_failure_response("No context provided")
        
        # Clean the context - remove assistant messages that are just tool call JSON
        # This prevents Gemini from mimicking the JSON format
        cleaned_context = []
        for msg in context:
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                # Skip if it's a tool call JSON (starts with {"tool": or {"text":)
                if content.strip().startswith('{"tool":') or content.strip().startswith('{"text":'):
                    logging.info(f"GEMINI_HANDLER: Filtering out tool call JSON from history: {content[:50]}...")
                    continue
            cleaned_context.append(msg)
        
        context = cleaned_context
        
        # Store the incoming prompt
        prompt = context[-1]["content"] if context else ""
        logging.info(f"GEMINI_HANDLER: Received prompt: {prompt[:50]}...")
        # Preserve the original context
        incoming_context = copy.deepcopy(context)
        logging.info(f"GEMINI_HANDLER: Context length after cleaning: {len(context)}")
        
        # Augment the last user message with the system prompt to classify the input prompt
        logging.info("GEMINI_HANDLER: Augmenting context with classification instructions")
        aug_prompt = f'''Respond with "{{"classifier": "search"}}" if the following prompt is better served with a google search query of current and news events or respond with "{{"classifier": "llm"}}" if it is better served with LLM knowledge base where time and recent events do not have an impact. Here is the prompt: {incoming_context[-1]["content"]}'''
      
        # Convert OpenAI-style context to Google Gemini format
        gemini_history = convert_openai_history_to_google_gemini(context[:-1])
        logging.info(f"GEMINI_HANDLER: Converted to Gemini format: {gemini_history}")

        # Initialize model and chat session
        if len(gemini_history):
            logging.info("GEMINI_HANDLER: Multi-turn conversation detected")
            chat = client.chats.create(model=model, history=gemini_history)
            logging.info("GEMINI_HANDLER: Created chat with history")
        else:
            logging.info("GEMINI_HANDLER: First-turn conversation detected")
            chat = client.chats.create(model=model)
            logging.info("GEMINI_HANDLER: Created new chat")

        # Send the message to get classifier response
        logging.info("GEMINI_HANDLER: Sending message for classification")
        json_response = chat.send_message(aug_prompt, config={'response_mime_type': 'application/json'})
        logging.info(f"GEMINI_HANDLER: Received classifier response: {json_response.text}")
        try:
            # Parse the JSON response to determine query type
            json_response_obj = json.loads(json_response.text)
            logging.info(f"GEMINI_HANDLER: Parsed classifier response: {json_response_obj}")
            
            if json_response_obj.get("classifier") == "llm":
                return execute_llm_query(gemini_history, incoming_context, system_info)
            else:
                logging.info("GEMINI_HANDLER: Query classified as search path")
                try:
                    # Search path: Use Google Search Tool for search queries
                    logging.info("GEMINI_HANDLER: Initializing Google Search Tool")
                    gemini_history = convert_openai_history_to_google_gemini(context)
                    parts = extract_parts(gemini_history)
                    response = client.models.generate_content_stream(
                        model=model,
                        contents=parts,
                        config=GenerateContentConfig(
                            tools=[Tool(google_search=GoogleSearch())],
                        ),
                    )
                    # Process and stream the search-enhanced response
                    logging.info("GEMINI_HANDLER: Streaming search-enhanced response")
                    for chunk in response:
                        if chunk.text:
                            logging.info(f'GEMINI_HANDLER: Search response chunk: {chunk.text[:30]}...')
                            write_response(generate_message_response(chunk.text))
                    logging.info("GEMINI_HANDLER: Search response completed successfully")
                    return generate_success_response()
                except Exception as search_error:
                    # If search fails, fall back to LLM
                    logging.error(f'GEMINI_HANDLER: Search failed, falling back to LLM: {str(search_error)}')
                    write_response(generate_message_response("Unable to ground search the query, falling back to LLM.\n"))
                    return execute_llm_query(gemini_history, incoming_context, system_info)
        except json.JSONDecodeError:
            # Handle JSON parsing errors from classifier response
            logging.error(f'GEMINI_HANDLER: Failed to parse classifier response: {json_response.text}')
            return generate_failure_response("Failed to classify the query")
        
    except Exception as e:
        # Catch and log any other exceptions that occur
        logging.error(f'GEMINI_HANDLER: API error: {str(e)}')
        logging.error(f'GEMINI_HANDLER: Stack trace: {traceback.format_exc()}')
        return generate_failure_response(f'API error: {str(e)}')

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
    logging.info("GEMINI_HANDLER: Query classified as LLM path")
    aug_prompt = f"You are a helpful AI assistant that can help with a wide range of topics. You are a plugin within the Nvidia G-Assist ecosystem of plugins. Keep your responses concise and within 100 words if possible. If a user is inquiring about games and Nvidia GPUs, keep in mind the list of games installed on the user PC including the current playing game as: {system_info}. {incoming_context[-1]['content']}"
    logging.info("GEMINI_HANDLER: Reset context with system information")
    
    chat = client.chats.create(model=model, history=gemini_history)
    logging.info("GEMINI_HANDLER: Created new chat with updated history")
    
    response = chat.send_message_stream(aug_prompt)
    for chunk in response:
        if chunk.text:
            logging.info(f'GEMINI_HANDLER: Response chunk: {chunk.text[:30]}...')
            write_response(generate_message_response(chunk.text))
    logging.info("GEMINI_HANDLER: LLM response completed successfully")
    return generate_success_response()

if __name__ == '__main__':
    main()
