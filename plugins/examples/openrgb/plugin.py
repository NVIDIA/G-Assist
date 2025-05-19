''' G-Assist plugin template code.

The following code can be used to create a G-Assist plugin written in Python. G-Assist
plugins are Windows based executables. They are spawned by the G-Assist plugin
manager. Communication between the plugin and the manager are done via pipes.
'''
import json
import logging
import os
from ctypes import byref, windll, wintypes
from xmlrpc.client import boolean
import requests
from typing import Optional
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor, DeviceType


# Data Types
Response = dict[bool,Optional[str]]

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'openrgb_plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

SIGNALRGB_URL = "http://127.0.0.1:16038/api/v1"
global CLI 

COLOR_MAP = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'purple': (128, 0, 128),
    'orange': (255, 165, 0),
    'pink': (255, 192, 203),
    'white': (255, 255, 255),
    'black': (0, 0, 0)
}

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
    PARAMS_PROPERTY = 'params'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'


    ERROR_MESSAGE = 'Plugin Error!'

    try:
        # Generate command handler mapping
        commands = {
            'initialize': execute_initialize_command,
            'shutdown': execute_shutdown_command,
            'list_devices': execute_list_devices,
            'disable_lighting': execute_disable_lighting,
            # 'list_colors': execute_list_colors,
            # 'list_effects': execute_list_effects,
            'set_color': execute_set_color,
            'set_mode': execute_set_mode,
        }
        cmd = ''

        logging.info('Plugin started')
        while cmd != SHUTDOWN_COMMAND:
            response = None
            input = read_command()
            if input is None:
                logging.error('Error reading command')
                continue

            logging.info(f'Received input: {input}')
            
            if TOOL_CALLS_PROPERTY in input:
                tool_calls = input[TOOL_CALLS_PROPERTY]
                for tool_call in tool_calls:
                    if FUNCTION_PROPERTY in tool_call:
                        cmd = tool_call[FUNCTION_PROPERTY]
                        logging.info(f'Processing command: {cmd}')
                        if cmd in commands:
                            if(cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND):
                                response = commands[cmd]()
                            else:
                                response = execute_initialize_command()
                                response = commands[cmd](
                                    tool_call.get(PARAMS_PROPERTY, {}),
                                    input[CONTEXT_PROPERTY] if CONTEXT_PROPERTY in input else None,
                                    input[SYSTEM_INFO_PROPERTY] if SYSTEM_INFO_PROPERTY in input else None  # Pass system_info directly
                                )
                        else:
                            logging.warning(f'Unknown command: {cmd}')
                            response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
                    else:
                        logging.warning('Malformed input: missing function property')
                        response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')
            else:
                logging.warning('Malformed input: missing tool_calls property')
                response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

            logging.info(f'Sending response: {response}')
            write_response(response)

            if cmd == SHUTDOWN_COMMAND:
                logging.info('Shutdown command received, terminating plugin')
                break
        
        logging.info('G-Assist Plugin stopped.')
        return 0
    except Exception as e:
        logging.error(f'Unexpected error in main: {str(e)}')
        return 1


def read_command() -> dict | None:
    ''' Reads a command from the communication pipe.

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

            # Add the chunk we read
            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            # If we read less than the buffer size, we're done
            if message_bytes.value < BUFFER_SIZE:
                break

        retval = buffer.decode('utf-8')[:message_bytes.value]
        return json.loads(retval)

    except json.JSONDecodeError:
        logging.error('Failed to decode JSON input')
        return None
    except Exception as e:
        logging.error(f'Unexpected error in read_command: {str(e)}')
        return None


def write_response(response:Response) -> None:
    ''' Writes a response to the communication pipe.

    Args:
        response: Function response
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

    except Exception as e:
        logging.error(f'Failed to write response: {str(e)}')
        pass


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


def execute_initialize_command() -> dict:
    ''' Command handler for `initialize` function

    This handler is responseible for initializing the plugin.

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info('Initializing plugin')
    # initialization function body
    global CLI 
    CLI = OpenRGBClient('127.0.0.1', 6742, 'G-Assist Plugin')

    return generate_success_response('initialize success.')


def execute_shutdown_command() -> dict:
    ''' Command handler for `shutdown` function

    This handler is responsible for releasing any resources the plugin may have
    acquired during its operation (memory, access to hardware, etc.).

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    global CLI
    try:
        if CLI:
            CLI.disconnect()
        return generate_success_response('Shutdown OpenRGB client successfully.')
    except Exception as e:
        logging.error(f'Failed to shutdown OpenRGB: {str(e)}')
        return generate_failure_response('Failed to shutdown OpenRGB client.')


def execute_list_devices(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    SUCCESS_MESSAGE = 'Here is a list of devices:\n'
    ERROR_MESSAGE = 'Failed to get devices information for OpenRGB.'
    logging.info(f'Executing execute_get_devices')
    global CLI 

    try:
        devices = [device.name for device in CLI.devices]
        readable_devices = '\n'.join(devices)
        print(devices)

        logging.info(f'Devices: {readable_devices}')

        if devices:
            return generate_success_response(f'{SUCCESS_MESSAGE} {readable_devices}')
        else:
            return generate_failure_response(ERROR_MESSAGE)
    except Exception as e:
        return generate_failure_response(f'{ERROR_MESSAGE} {e}')

def execute_set_color(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    SUCCESS_MESSAGE = 'Lighting for '
    ERROR_MESSAGE = 'Failed to set lighting to color for OpenRGB.'
    logging.info(f'Executing execute_set_color')

    try:
        color = params.get('color_name')
        logging.info(f'Color: {color}')
        if not color:
            return generate_failure_response(f'{ERROR_MESSAGE} Missing color')
        
        device_name = params.get('device_name')
        logging.info(f'Device Name: {device_name}')
        try:
            # Look up color in our map
            color = color.lower()
            if color not in COLOR_MAP:
                return generate_failure_response(f'{ERROR_MESSAGE} Unknown color: {color}')
            r, g, b = COLOR_MAP[color]
            color = RGBColor(r, g, b)
        except Exception as e:
            return generate_failure_response(f'{ERROR_MESSAGE} Invalid color format: {e}')

        if device_name and "all" not in device_name.lower():
            # Set color for specific device
            try:
                devices = CLI.get_devices_by_name(device_name, False)
                logging.info(f'Devices: {devices}')

                if devices and len(devices) > 0:
                    logging.info(f'Setting color for device: {devices[0]}')
                    devices[0].set_color(color)
                    return generate_success_response(f'{SUCCESS_MESSAGE} {device_name} set to {color}')
                else:
                    return generate_failure_response(f'{ERROR_MESSAGE} Device not found')
            except Exception as e:
                return generate_failure_response(f'{ERROR_MESSAGE} Error finding device: {e}')
        else:
            # Set color for all devices
            try:
                all_devices = CLI.devices
                logging.info(f'All Devices: {all_devices}')
                if not all_devices:
                    return generate_failure_response(f'{ERROR_MESSAGE} No devices found')
                
                success_messages = []
                for device in all_devices:
                    device.set_color(color)
                    success_messages.append(f'{device.name} set to {color}')
                
                return generate_success_response(f'{SUCCESS_MESSAGE} all devices: ' + '\n '.join(success_messages))
            except Exception as e:
                return generate_failure_response(f'{ERROR_MESSAGE} Error setting color on devices: {e}')
        
    except Exception as e:
        return generate_failure_response(f'{ERROR_MESSAGE} {e}')

def execute_disable_lighting(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    SUCCESS_MESSAGE = 'SignalRGB lighting disabled.'
    ERROR_MESSAGE = 'Failed to disable lighting for SignalRGB.'
    logging.info(f'Executing execute_disable_lighting')
    try:    
        global CLI
        for device in CLI.devices:
            device.set_mode('off')

        return generate_success_response(SUCCESS_MESSAGE)
    except Exception as e:
        return generate_failure_response(f'{ERROR_MESSAGE} {e}')

def execute_set_mode(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    SUCCESS_MESSAGE = 'Mode set successfully.'
    ERROR_MESSAGE = 'Failed to set mode for OpenRGB.'
    logging.info(f'Executing execute_set_mode')     
    try:
        global CLI
        device_name = params.get('device_name')
        effect_name = params.get('effect_name')
        
        if not effect_name:
            return generate_failure_response(f'{ERROR_MESSAGE} Missing effect_name')

        if device_name and "all" not in device_name.lower():
            # Set mode for specific device
            try:
                devices = CLI.get_devices_by_name(device_name, False)
                logging.info(f'Devices: {devices}')

                if devices and len(devices) > 0:
                    device = devices[0]
                    modes = {mode.name.lower(): mode for mode in device.modes}
                    if effect_name.lower() in modes:
                        device.set_mode(effect_name)
                        return generate_success_response(f'{SUCCESS_MESSAGE} {device_name} set to {effect_name}')
                    else:
                        return generate_failure_response(f'{ERROR_MESSAGE} Effect not supported on device')
                else:
                    return generate_failure_response(f'{ERROR_MESSAGE} Device not found')
            except Exception as e:
                return generate_failure_response(f'{ERROR_MESSAGE} Error finding device: {e}')
        else:
            # Set mode for all devices
            try:
                all_devices = CLI.devices
                logging.info(f'All Devices: {all_devices}')
                if not all_devices:
                    return generate_failure_response(f'{ERROR_MESSAGE} No devices found')
                
                success_messages = []
                for device in all_devices:
                    modes = {mode.name.lower(): mode for mode in device.modes}
                    if effect_name.lower() in modes:
                        device.set_mode(effect_name)
                        success_messages.append(f'{device.name} set to {effect_name}')
                    else:
                        success_messages.append(f'{device.name} does not support {effect_name}')
                
                return generate_success_response(f'{SUCCESS_MESSAGE} all devices: ' + '\n '.join(success_messages))
            except Exception as e:
                return generate_failure_response(f'{ERROR_MESSAGE} Error setting mode on devices: {e}')
        
    except Exception as e:
        logging.error(f'Error setting mode: {str(e)}')
        return generate_failure_response(f'{ERROR_MESSAGE} {e}')


if __name__ == '__main__':
    main()
