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
import ctypes
import json
import logging
import os

from ctypes import byref, windll, wintypes, GetLastError, create_string_buffer
import re
from typing import Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

# Data Types
type Response = dict[bool,Optional[str]]


# Globals
API_KEY_FILE = os.path.join(f'{os.environ.get("PROGRAMDATA", ".")}{r'\NVIDIA Corporation\nvtopps\rise\plugins\gemini'}', 'gemini.key')
CONFIG_FILE = os.path.join(f'{os.environ.get("PROGRAMDATA", ".")}{r'\NVIDIA Corporation\nvtopps\rise\plugins\gemini'}', 'config.json')

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'gemini.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

API_KEY = None
model: str = 'gemini-pro'  # Default model

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
    SYSTEM_INFO_PROPERTY = 'system_info'  # Added for game information
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
            # Error reading command; continue
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
                                input[SYSTEM_INFO_PROPERTY] if SYSTEM_INFO_PROPERTY in input else None  # Pass system_info directly
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
    # First, decode any escape sequences (like \U0001f3ac) into actual Unicode characters.
    try:
        s_decoded = s.encode('utf-8').decode('unicode_escape')
    except Exception:
        s_decoded = s

    # Then, remove any non-ASCII characters (you can adjust the filter as needed)
    ascii_only = ''.join(c for c in s_decoded if ord(c) < 128)
    return ascii_only

def read_command() -> dict | None:
    ''' Reads a command from the communication pipe.

    Returns:
        Command details if the input was proper JSON; `None` otherwise
    '''
    try:
        STD_INPUT_HANDLE = -10
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)

        # Read in chunks until we get the full message
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

            # Add the chunk we read
            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            # If we read less than the buffer size, we're done
            if message_bytes.value < BUFFER_SIZE:
                break

        # Combine all chunks and fix Unicode escapes if needed
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

    Args:
        response: dictionary containing return value(s)
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

    Parameters:
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

    Parameters:
        message: String to be returned in the response (optional)

    Returns:
        A success response with the attached massage
    '''
    response = { 'success': True }
    if message:
        response['message'] = message
    return response


def generate_message_response(message:str):
    ''' Generates a message.

    Parameters:
        message: String to be returned to the driver

    Returns:
        A message response
    '''
    return { 'message': message }


def execute_initialize_command() -> dict:
    ''' Initialize the Gemini API connection '''
    global API_KEY, API_KEY_FILE

    key = None
    if os.path.isfile(API_KEY_FILE):
        with open(API_KEY_FILE) as file:
            key = file.read().strip()

    if not key:
        logging.error('No API key found')
        return generate_failure_response('Missing API key')

    try:
        genai.configure(api_key=key)
        logging.info('Successfully configured Gemini API')
        API_KEY = key
        return generate_success_response()
    except Exception as e:
        logging.error(f'Configuration failed: {str(e)}')
        API_KEY = None
        return generate_failure_response(str(e))

def execute_shutdown_command() -> dict:
    ''' Cleanup resources '''
    # Gemini API doesn't require explicit shutdown
    logging.info('Gemini plugin shutdown')
    return generate_success_response()

def convert_oai_to_gemini_history(oai_history):
    """Convert OpenAI-style chat history to Gemini-compatible format"""
    gemini_history = []
    for msg in oai_history:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_history.append({
            "role": role,
            "parts": [{"text": msg["content"]}]
        })
    return gemini_history

def execute_query_gemini_command(params: dict = None, context: dict = None, system_info: str = None) -> dict:
    ''' Handle Gemini query with conversation history '''
    global API_KEY, CONFIG_FILE, model

    execute_initialize_command()

    if API_KEY is None:
        ERROR_MESSAGE = (
            "It looks like your API key is missing or invalid. Please update " +
            f"{API_KEY_FILE} with a valid key and restart G-Assist.\n\n" +
            "To obtain an API, visit https://ai.google.dev."
        )
        return generate_failure_response(ERROR_MESSAGE)

    # Load model config
    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
            model = config.get('model', model)

    try:

        if len(context) > 0:
            context[0]["content"] = f"You are a helpful AI assistant that can help with a wide range of topics. You are a plugin within the Nvidia G-Assist ecosystem of plugins. Keep your responses concise and within 100 words if possible. If a user is inquiring about games and Nvidia GPUs, keep in mind the list of games installed on the user PC including the current playing game as: {system_info}. {context[0]["content"]}"

        logging.info(context)
        # Convert OpenAI-style context
        gemini_history = convert_oai_to_gemini_history(context)
        logging.info(gemini_history)
        # Get latest user input
        if not context or len(context) == 0:
            return generate_failure_response("No context provided")

        latest_input = context[-1]["content"]

        # Initialize model and chat session
        generative_model = genai.GenerativeModel(model)
        chat = generative_model.start_chat(history=gemini_history)

        # Stream response
        response = chat.send_message(latest_input, stream=True)

        for chunk in response:
            if chunk.text:
                logging.info(f'Response chunk: {chunk.text}')
                write_response(generate_message_response(chunk.text))

        return generate_success_response()

    except Exception as e:
        logging.error(f'Gemini API error: {str(e)}')
        return generate_failure_response(f'API error: {str(e)}')

if __name__ == '__main__':
    main()
