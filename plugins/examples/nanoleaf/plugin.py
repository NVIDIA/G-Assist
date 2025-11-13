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
import ctypes
import json
import os
import sys

from ctypes import byref, windll, wintypes
from ipaddress import ip_address
from typing import Optional

from nanoleafapi import Nanoleaf


# Get the directory where the plugin is deployed
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "nanoleaf")
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

# Save log in plugin directory for better organization
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'nanoleaf-plugin.log')


# Data Types
Response = dict[str, bool | Optional[str]]
Color = tuple[int, int, int]


# Globals
NL: Nanoleaf | None = None
NANOLEAF_IP = None
SETUP_COMPLETE = False

# Load config at startup
try:
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            data = json.load(file)
            NANOLEAF_IP = data.get('ip', '')
            if NANOLEAF_IP and ip_address(NANOLEAF_IP):
                SETUP_COMPLETE = True
                write_log(f"Successfully loaded Nanoleaf IP from {CONFIG_FILE}")
            else:
                write_log(f"Invalid IP address in {CONFIG_FILE}")
                NANOLEAF_IP = None
except FileNotFoundError:
    write_log(f"Config file not found at {CONFIG_FILE}")
except Exception as e:
    write_log(f"Error loading config: {e}")


def write_log(line: str) -> None:
    ''' Writes a line to the log file.

    Parameters:
        line: The line to write
    '''
    global LOG_FILE

    try:
        if LOG_FILE is not None:
            with open(LOG_FILE, 'a') as file:
                file.write(f'{line}\n')
                file.flush()
    except Exception:
        # Error writing to the log
        pass


def execute_setup_wizard() -> Response:
    """Guide user through Nanoleaf setup."""
    global SETUP_COMPLETE, NANOLEAF_IP
    
    # Check if config was updated
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as file:
                data = json.load(file)
            new_ip = data.get('ip', '')
            
            if new_ip and ip_address(new_ip):
                NANOLEAF_IP = new_ip
                SETUP_COMPLETE = True
                write_log("Nanoleaf IP configured successfully!")
                return {
                    'success': True,
                    'message': "✓ Nanoleaf configured! You can now control your lights.",
                    'awaiting_input': False
                }
    except:
        pass
    
    # Show setup instructions
    message = f"""
NANOLEAF PLUGIN - FIRST TIME SETUP
===================================

Welcome! Let's set up your Nanoleaf lights. This takes about 2 minutes.

STEP 1 - Find Your Nanoleaf IP Address:
   Method A - Using Nanoleaf App:
   1. Open the Nanoleaf app on your phone
   2. Go to Settings > Device Info
   3. Note the IP address shown

   Method B - Using Router:
   1. Log into your router's admin page
   2. Find the list of connected devices
   3. Look for "Nanoleaf" or "NL" device
   4. Note its IP address

STEP 2 - Configure Plugin:
   1. Open this file: {CONFIG_FILE}
   2. Replace the IP address:
      {{"ip": "192.168.1.XXX"}}
   3. Save the file

After saving, send me ANY message (like "done") and I'll verify it!

Note: Make sure your Nanoleaf is powered on and connected to the same network!
"""
    
    write_log("Showing Nanoleaf setup wizard to user")
    return {
        'success': True,
        'message': message,
        'awaiting_input': True
    }


def execute_initialize_command() -> Response:
    ''' Command handler for "initialize" function

    Returns:
        Function response
    '''
    global NL, NANOLEAF_IP, SETUP_COMPLETE

    # Check if setup is needed
    if not SETUP_COMPLETE or not NANOLEAF_IP:
        return execute_setup_wizard()

    try:
        NL = Nanoleaf(NANOLEAF_IP)
        NL.power_on()
        NL.set_color(get_rgb_code('BLACK'))
        write_log(f"Successfully connected to Nanoleaf at {NANOLEAF_IP}")
        return generate_success_response('Nanoleaf initialized successfully.')
    except Exception as e:
        write_log(f'Error connecting to Nanoleaf device: {str(e)}')
        NL = None
        return generate_failure_response(f'Error connecting to Nanoleaf at {NANOLEAF_IP}. Check IP address and network connection.')


def execute_shutdown_command() -> Response:
    ''' Command handler for "shutdown" function

    Returns:
        Function response
    '''
    global NL

    is_success = True
    if NL:
        try:
            is_success = NL.power_off()
        except Exception as e:
            write_log(f'Error powering off Nanoleaf: {str(e)}')
            is_success = False
    NL = None
    return generate_success_response() if is_success else generate_failure_response()


def execute_color_command(nl:Nanoleaf, params:dict=None, context:dict=None, send_status_callback=None) -> Response:
    ''' Command handler for "nanoleaf_change_room_lights" function

    Parameters:
        nl: Nanoleaf device.
        params: Function parameters.
        context: Function context.
        send_status_callback: Callback to send status updates.

    Returns:
        Function response
    '''
    SUCCESS_MESSAGE = 'Nanoleaf lighting updated.'
    ERROR_MESSAGE = 'Failed to update lighting for the Nanoleaf device.'

    COMMANDS = [ 'OFF', 'BRIGHT_UP', 'BRIGHT_DOWN' ]
    RAINBOW = 'RAINBOW'

    if params is None or 'color' not in params:
        return generate_failure_response(f'{ERROR_MESSAGE} Missing color.')

    try:
        color = params['color'].upper()
        
        # Send status update
        if send_status_callback:
            send_status_callback(generate_status_update(f"Changing Nanoleaf lights to {color.lower()}..."))
        if color == RAINBOW:
            # this is temporary until the model adds a 'change profile' function
            return execute_profile_command(nl, { 'profile': 'Northern Lights' })
        if color in COMMANDS:
            return adjust_brightness(nl, color)
        else:
            return generate_success_response(SUCCESS_MESSAGE) if change_color(nl, color) else generate_failure_response()
    except Exception as e:
        write_log(f'Error in execute_color_command: {str(e)}')
        return generate_failure_response(f'{ERROR_MESSAGE} {str(e)}')


def execute_profile_command(nl:Nanoleaf, params:dict=None, context:dict=None, send_status_callback=None) -> Response:
    ''' Command handler for "nanoleaf_change_profile" function.

    Parameters:
        nl: Nanoleaf device.
        params: Function parameters.
        context: Function context.
        send_status_callback: Callback to send status updates.
    Returns:
        Function response
    '''
    SUCCESS_MESSAGE = 'Nanoleaf profile updated.'
    ERROR_MESSAGE = 'Failed to update profile for the Nanoleaf device.'
    
    if nl is None:
        return generate_failure_response(f'{ERROR_MESSAGE} Device not connected.')
    
    try:
        effects = nl.list_effects()
        if params is None or 'profile' not in params:
            return generate_failure_response(ERROR_MESSAGE)

        profile = params['profile']
        
        # Send status update
        if send_status_callback:
            send_status_callback(generate_status_update(f"Changing Nanoleaf profile to {profile}..."))
        try:
            index = [ s.upper() for s in effects ].index(profile.upper())
            nl.set_effect(effects[index])
            return generate_success_response(SUCCESS_MESSAGE)
        except ValueError:
            return generate_failure_response(f'{ERROR_MESSAGE} Unknown profile: {profile}.')
    except Exception as e:
        write_log(f'Error in execute_profile_command: {str(e)}')
        return generate_failure_response(f'{ERROR_MESSAGE} {str(e)}')


def adjust_brightness(nl: Nanoleaf, command: str) -> bool:
    ''' Adjusts the brightness of the Nanoleaf device.

    Parameters:
        nl: Nanoleaf device.
        command:
            The bright adjustment command. It must be one of the following:
            "BRIGHT_UP", "BRIGHT_DOWN", "OFF".

    Returns:
        True if successful, otherwise False
    '''
    LEVEL = 10

    try:
        match command.upper():
            case 'OFF':
                return nl.power_off()
            case 'BRIGHT_UP':
                return nl.increment_brightness(LEVEL)
            case 'BRIGHT_DOWN':
                return nl.increment_brightness(-LEVEL)
            case _:
                return False
    except Exception as e:
        write_log(f'Error adjusting brightness: {str(e)}')
        return False


def change_color(nl:Nanoleaf, color:str) -> dict:
    ''' Changes the color of the Nanoleaf device.

    Parameters:
        nl: Nanoleaf device.
        color: Predefined color value.

    Returns:
        Boolean indicating if the color was updated.
    '''
    try:
        rgb_value = get_rgb_code(color)
        return nl.set_color(rgb_value) if rgb_value else False
    except Exception as e:
        write_log(f'Error changing color: {str(e)}')
        return False


def get_rgb_code(color:str) -> Color | None:
    ''' Get the RGB value for a predefined color value.

    Parameters:
        color: Predefined color value.

    Returns:
        RGB tuple value if the predefined color value is recognized, otherwise
        None.
    '''
    key = color.upper()
    rgb_values = {
        'RED': (255, 0, 0),
        'GREEN': (0, 255, 0),
        'BLUE': (0, 0, 255),
        'CYAN': (0, 255, 255),
        'MAGENTA': (255, 0, 255),
        'YELLOW': (255, 255, 0),
        'BLACK': (0, 0, 0),
        'WHITE': (255, 255, 255),
        'GREY': (128, 128, 128),
        'GRAY': (128, 128, 128),
        'ORANGE': (255, 165, 0),
        'PURPLE': (128, 0, 128),
        'VIOLET': (128, 0, 128),
        'PINK': (255, 192, 203),
        'TEAL': (0, 128, 128),
        'BROWN': (165, 42, 42),
        'ICE_BLUE': (173, 216, 230),
        'CRIMSON': (220, 20, 60),
        'GOLD': (255, 215, 0),
        'NEON_GREEN': (57, 255, 20)
    }

    return rgb_values[key] if key in rgb_values else None


def generate_failure_response(message:str=None) -> Response:
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


def generate_success_response(message:str=None) -> Response:
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

def generate_status_update(message: str) -> dict:
    """Generate a status update (not a final response).
    
    Status updates are intermediate messages that don't end the plugin execution.
    They should NOT include 'success' field to avoid being treated as final responses.
    """
    return {'status': 'in_progress', 'message': message}


def generate_command_handlers() -> dict:
    ''' Generates the mapping of commands to their handlers.

    Returns:
        Dictionary where the commands is the key and the handler is the value
    '''
    commands = dict()
    commands['initialize'] = execute_initialize_command
    commands['shutdown'] = execute_shutdown_command
    commands['nanoleaf_change_room_lights'] = execute_color_command
    commands['nanoleaf_change_profile'] = execute_profile_command
    return commands


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
                write_log('Error reading from command pipe')
                return None
            
            # Add the chunk we read
            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

             # If we read less than the buffer size, we're done
            if message_bytes.value < BUFFER_SIZE:
                break

        # Combine all chunks and parse JSON
        retval = ''.join(chunks)
        write_log(f'[PIPE] Read {len(retval)} bytes from pipe')
        return json.loads(retval)

    except json.JSONDecodeError:
        write_log(f'Received invalid JSON: {retval}')
        return None
    except Exception as e:
        write_log(f'Exception in read_command(): {str(e)}')
        return None


def write_response(response:Response) -> None:
    ''' Writes a response to the communication pipe.

    Parameters:
        response: Response
    '''
    try:
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)
        
        write_log(f"[PIPE] Writing message: success={response.get('success', 'unknown')}, length={message_len} bytes")

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            byref(bytes_written),
            None
        )

        if success:
            write_log(f"[PIPE] Write OK - bytes={bytes_written.value}/{message_len}")
        else:
            write_log(f"[PIPE] Write FAILED - GetLastError={windll.kernel32.GetLastError()}")

    except Exception as e:
        write_log(f'Exception in write_response(): {str(e)}')


def main():
    ''' Main entry point.

    Sits in a loop listening to a pipe, waiting for commands to be issued. After
    receiving the command, it is processed and the result returned. The loop
    continues until the "shutdown" command is issued.

    Returns:
        Zero if no errors occurred during execution, otherwise a non-zero value
    '''
    global NL

    TOOL_CALLS_PROPERTY = 'tool_calls'
    CONTEXT_PROPERTY = 'context'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'properties'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'

    ERROR_MESSAGE = 'Failed to update lighting for Nanoleaf device(s).'

    # Generate command handler mapping
    commands = generate_command_handlers()
    cmd = ''
    read_failures = 0
    MAX_READ_FAILURES = 3

    write_log('Starting Nanoleaf plugin.')
    while True:
        response = None
        input = read_command()
        
        if input is None:
            read_failures += 1
            write_log(f'Error reading command (failure {read_failures}/{MAX_READ_FAILURES})')
            if read_failures >= MAX_READ_FAILURES:
                write_log('Too many read failures, exiting')
                break
            continue
        
        # Reset failure counter on successful read
        read_failures = 0
        context = input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in input else None

        write_log(f'Input Received: {input}')
        
        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY].lower()

                    if cmd in commands:
                        if(cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND):
                            response = commands[cmd]()
                        else:
                            # Check if setup is needed before executing Nanoleaf functions
                            if not SETUP_COMPLETE or not NANOLEAF_IP:
                                write_log('[COMMAND] Nanoleaf not configured - starting setup wizard')
                                response = execute_setup_wizard()
                            elif NL is None:
                                # Try to initialize if not already connected
                                init_response = execute_initialize_command()
                                if NL is None:
                                    response = generate_failure_response(f'{ERROR_MESSAGE} There is no Nanoleaf device connected. Check the IP address in the configuration file.')
                                else:
                                    response = commands[cmd](NL, tool_call[PARAMS_PROPERTY] if PARAMS_PROPERTY in tool_call else {}, context, send_status_callback=write_response)
                            else:
                                response = commands[cmd](NL, tool_call[PARAMS_PROPERTY] if PARAMS_PROPERTY in tool_call else {}, context, send_status_callback=write_response)
                    else:
                        response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
                else:
                    response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')
        else:
            response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

        write_log(f'Sending Response: {response}')
        write_response(response)
        if cmd == SHUTDOWN_COMMAND:
            break
    
    write_log('Nanoleaf plugin stopped.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
