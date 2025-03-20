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


# Globals
# The plugin's configuration file.
CONFIG_FILE = os.path.join(os.getcwd(), 'config.json')

# By default, logging is turned off. To enable logging, update the following
# with a path the plugin is allowed to write to.
LOG_FILE = os.path.join(os.environ.get('USERPROFILE', '.'), 'nanoleaf.log')


# Data Types
type Response = dict[bool,Optional[str]]
type Color = tuple[int, int, int]


# Globals
NL: Nanoleaf | None = None


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

    write_log('Starting plugin.')
    while True:
        response = None
        input = read_command()
        context = input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in cmd else None

        write_log(f'Input Received: {input}')
        if input is None:
            # Error reading command; continue
            continue
        if TOOL_CALLS_PROPERTY in input:
            tool_calls = input[TOOL_CALLS_PROPERTY]
            for tool_call in tool_calls:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY].lower()

                    if cmd in commands:
                        if(cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND):
                            response = commands[cmd]()
                        else:
                            response = execute_initialize_command()

                            if NL is None:
                                response = generate_failure_response(f'{ERROR_MESSAGE} There is no Nanoleaf device connected. Check the IP address in the configuration file.')
                            else:
                                response = commands[cmd](NL, tool_call[PARAMS_PROPERTY] if PARAMS_PROPERTY in tool_call else {}, context)
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
    return 0


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

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
            None
        )

        if not success:
            write_log('Error writing to response pipe')

    except Exception as e:
        write_log(f'Exception in write_response(): {str(e)}')


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


def execute_initialize_command() -> Response:
    ''' Command handler for "initialize" function

    The parameters are present to conform to the command handler interface.

    Parameters:
        nl: Nanoleaf device
        params: function parameters

    Returns:
        Function response
    '''
    global NL
    global CONFIG_FILE

    ip = get_ip_address(CONFIG_FILE)
    if ip is None:
        return generate_failure_response(f'Error reading configuration file: {os.path.abspath(CONFIG_FILE)}')

    try:
        NL = Nanoleaf(ip)
        NL.power_on()
        NL.set_color(get_rgb_code('BLACK'))
        return generate_success_response()
    except Exception as e:
        write_log(f'Error connecting to Nanoleaf device: {str(e)}')
        NL = None
        return generate_failure_response('Error initializing Nanoleaf device')


def get_ip_address(config_file:str) -> str | None:
    ''' Loads the IP address from the configuration file.

    Parameters:
        config_file: Path to the configuration file.

    Returns:
        The IP address of the Nanoleaf device or `None` if an IP address cannot
        be determined.
    '''
    ip = None
    try:
        if os.path.exists(config_file):
            with open(config_file, 'r') as file:
                data = json.load(file)
                if 'ip' in data and ip_address(data['ip']):
                    ip = data['ip']
    except json.JSONDecodeError:
        # malformed json; return None
        pass

    return ip


def execute_shutdown_command() -> Response:
    ''' Command handler for "shutdown" function

    Parameters:
        nl: Nanoleaf device
        params: function parameters

    Returns:
        Function response
    '''
    global NL

    is_success = True
    if NL:
        is_success = NL.power_off()
    NL = None
    return generate_success_response() if is_success else generate_failure_response()


def execute_color_command(nl:Nanoleaf, params:dict=None, context:dict=None) -> Response:
    ''' Command handler for "nanoleaf_change_room_lights" function

    Parameters:
        nl: Nanoleaf device.
        params: Function parameters.
        context: Function context.

    Returns:
        Function response
    '''
    SUCCESS_MESSAGE = 'Nanoleaf lighting updated.'
    ERROR_MESSAGE = 'Failed to update lighting for the Nanoleaf device.'

    COMMANDS = [ 'OFF', 'BRIGHT_UP', 'BRIGHT_DOWN' ]
    RAINBOW = 'RAINBOW'

    if params is None or 'color' not in params:
        return generate_failure_response(f'{ERROR_MESSAGE} Missing color.')

    color = params['color'].upper()
    if color == RAINBOW:
        # this is temporary until the model adds a 'change profile' function
        return execute_profile_command(nl, { 'profile': 'Northern Lights' })
    if color in COMMANDS:
        return adjust_brightness(nl, color)
    else:
        return generate_success_response(SUCCESS_MESSAGE) if change_color(nl, color) else generate_failure_response()


def execute_profile_command(nl:Nanoleaf, params:dict=None, context:dict=None) -> Response:
    ''' Command handler for "nanoleaf_change_profile" function.

    Parameters:
        nl: Nanoleaf device.
        params: Function parameters.
        context: Function context.
    Returns:
        Function response
    '''
    SUCCESS_MESSAGE = 'Nanoleaf profile updated.'
    ERROR_MESSAGE = 'Failed to update profile for the Nanoleaf device.'
    if nl is not None:
        effects = nl.list_effects()
        if params is None or 'profile' not in params:
            return generate_failure_response(ERROR_MESSAGE)

        profile = params['profile']
        try:
            index = [ s.upper() for s in effects ].index(profile.upper())
            nl.set_effect(effects[index])
            return generate_success_response(SUCCESS_MESSAGE)
        except ValueError:
            return generate_failure_response(f'{ERROR_MESSAGE} Unknown profile: {profile}.')


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

    match command.upper():
        case 'OFF':
            return nl.power_off()
        case 'BRIGHT_UP':
            return nl.increment_brightness(LEVEL)
        case 'BRIGHT_DOWN':
            return nl.increment_brightness(-LEVEL)
        case _:
            return False


def change_color(nl:Nanoleaf, color:str) -> dict:
    ''' Changes the color of the Nanoleaf device.

    Parameters:
        nl: Nanoleaf device.
        color: Predefined color value.

    Returns:
        Boolean indicating if the color was updated.
    '''
    rgb_value = get_rgb_code(color)
    return nl.set_color(rgb_value) if rgb_value else False


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


if __name__ == '__main__':
    sys.exit(main())
