import json
import logging
import os
import threading
import time
from ctypes import byref, windll, wintypes
from ipaddress import ip_address
from typing import Any, Dict, Optional, Tuple

from nanoleafapi import Nanoleaf

STD_INPUT_HANDLE = -10
STD_OUTPUT_HANDLE = -11

PLUGIN_NAME = "nanoleaf"
PROGRAM_DATA = os.environ.get("PROGRAMDATA", ".")
PLUGIN_DIR = os.path.join(
    PROGRAM_DATA, "NVIDIA Corporation", "nvtopps", "rise", "plugins", PLUGIN_NAME
)
CONFIG_FILE = os.path.join(PLUGIN_DIR, "config.json")
LOG_FILE = os.path.join(PLUGIN_DIR, f"{PLUGIN_NAME}-plugin.log")

DEFAULT_CONFIG: Dict[str, Any] = {
    "ip": "",
    "features": {
        "enable_passthrough": False,
        "stream_chunk_size": 240,
        "use_setup_wizard": True,
    },
}

STATE: Dict[str, Any] = {
    "config": DEFAULT_CONFIG.copy(),
    "awaiting_input": False,
    "wizard_active": False,
    "heartbeat_active": False,
    "heartbeat_thread": None,
    "heartbeat_message": "",
    "nanoleaf": None,
}


def ensure_directories() -> None:
    os.makedirs(PLUGIN_DIR, exist_ok=True)


def setup_logging() -> None:
    ensure_directories()
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )


def apply_config_defaults(raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = DEFAULT_CONFIG.copy()
    merged.update({k: v for k, v in raw.items() if k != "features"})
    merged_features = DEFAULT_CONFIG["features"].copy()
    merged_features.update(raw.get("features", {}))
    merged["features"] = merged_features
    return merged


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
        
        # Handle user input passthrough messages (for setup wizard interaction)
        if isinstance(input, dict) and input.get('msg_type') == 'user_input':
            user_input_text = input.get('content', '')
            write_log(f'[INPUT] Received user input passthrough: "{user_input_text}"')
            
            # Check if setup is needed
            global SETUP_COMPLETE, NANOLEAF_IP
            if not SETUP_COMPLETE:
                write_log("[WIZARD] User input during setup - checking config")
                response = execute_setup_wizard()
                write_response(response)
                continue
            else:
                # Setup already complete, acknowledge the input
                write_log("[INPUT] Setup already complete, acknowledging user input")
                response = generate_success_response("Got it! The Nanoleaf plugin is ready to use.")
                write_response(response)
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
