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

''' RISE plugin template code.

The following code can be used to create a RISE plugin written in Python. RISE
plugins are Windows based executables. They are spawned by the RISE plugin
manager. Communication between the plugin and the manager are done via pipes.
'''
import json
import logging
import os
from ctypes import byref, windll, wintypes
from typing import Optional

# Add import for CalendarTool
from src.tools.calendar_tool import CalendarTool
from src.tools import predictions

# Instantiate the calendar tool globally
calendar_tool_instance = CalendarTool()

# Add the handler

def execute_calendar_tool_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `calendar_tool` function
    Args:
        params: Function parameters (expects 'action' and optionally 'symbol')
    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing calendar_tool with params: {params}')
    try:
        action = params.get('action') if params else None
        symbol = params.get('symbol') if params else None
        result = calendar_tool_instance._run(action, symbol)
        return {'success': True, 'result': result}
    except Exception as e:
        logging.error(f'Error in calendar_tool: {str(e)}')
        return generate_failure_response(f'calendar_tool error: {str(e)}')

def execute_predict_daily_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for daily stock prediction '''
    try:
        args = params or {}
        result = predictions.predict_daily(
            symbol=args.get('symbol'),
            prediction_days=args.get('prediction_days', 30),
            lookback_days=args.get('lookback_days', 365),
            strategy=args.get('strategy', 'chronos'),
            use_ensemble=args.get('use_ensemble', True),
            use_regime_detection=args.get('use_regime_detection', True),
            use_stress_testing=args.get('use_stress_testing', True),
            risk_free_rate=args.get('risk_free_rate', 0.02),
            market_index=args.get('market_index', '^GSPC'),
            chronos_weight=args.get('chronos_weight', 0.6),
            technical_weight=args.get('technical_weight', 0.2),
            statistical_weight=args.get('statistical_weight', 0.2),
            random_real_points=args.get('random_real_points', 4),
            use_smoothing=args.get('use_smoothing', True),
            smoothing_type=args.get('smoothing_type', 'exponential'),
            smoothing_window=args.get('smoothing_window', 5),
            smoothing_alpha=args.get('smoothing_alpha', 0.3),
            use_covariates=args.get('use_covariates', True),
            use_sentiment=args.get('use_sentiment', True)
        )
        return {'success': True, 'result': result}
    except Exception as e:
        logging.error(f'Error in predict_daily: {str(e)}')
        return generate_failure_response(f'predict_daily error: {str(e)}')

def execute_predict_hourly_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for hourly stock prediction '''
    try:
        args = params or {}
        result = predictions.predict_hourly(
            symbol=args.get('symbol'),
            prediction_days=args.get('prediction_days', 3),
            lookback_days=args.get('lookback_days', 14),
            strategy=args.get('strategy', 'chronos'),
            use_ensemble=args.get('use_ensemble', True),
            use_regime_detection=args.get('use_regime_detection', True),
            use_stress_testing=args.get('use_stress_testing', True),
            risk_free_rate=args.get('risk_free_rate', 0.02),
            market_index=args.get('market_index', '^GSPC'),
            chronos_weight=args.get('chronos_weight', 0.6),
            technical_weight=args.get('technical_weight', 0.2),
            statistical_weight=args.get('statistical_weight', 0.2),
            random_real_points=args.get('random_real_points', 4),
            use_smoothing=args.get('use_smoothing', True),
            smoothing_type=args.get('smoothing_type', 'exponential'),
            smoothing_window=args.get('smoothing_window', 5),
            smoothing_alpha=args.get('smoothing_alpha', 0.3),
            use_covariates=args.get('use_covariates', True),
            use_sentiment=args.get('use_sentiment', True)
        )
        return {'success': True, 'result': result}
    except Exception as e:
        logging.error(f'Error in predict_hourly: {str(e)}')
        return generate_failure_response(f'predict_hourly error: {str(e)}')

def execute_predict_min15_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for 15-minute stock prediction '''
    try:
        args = params or {}
        result = predictions.predict_min15(
            symbol=args.get('symbol'),
            prediction_days=args.get('prediction_days', 1),
            lookback_days=args.get('lookback_days', 3),
            strategy=args.get('strategy', 'chronos'),
            use_ensemble=args.get('use_ensemble', True),
            use_regime_detection=args.get('use_regime_detection', True),
            use_stress_testing=args.get('use_stress_testing', True),
            risk_free_rate=args.get('risk_free_rate', 0.02),
            market_index=args.get('market_index', '^GSPC'),
            chronos_weight=args.get('chronos_weight', 0.6),
            technical_weight=args.get('technical_weight', 0.2),
            statistical_weight=args.get('statistical_weight', 0.2),
            random_real_points=args.get('random_real_points', 4),
            use_smoothing=args.get('use_smoothing', True),
            smoothing_type=args.get('smoothing_type', 'exponential'),
            smoothing_window=args.get('smoothing_window', 5),
            smoothing_alpha=args.get('smoothing_alpha', 0.3),
            use_covariates=args.get('use_covariates', True),
            use_sentiment=args.get('use_sentiment', True)
        )
        return {'success': True, 'result': result}
    except Exception as e:
        logging.error(f'Error in predict_min15: {str(e)}')
        return generate_failure_response(f'predict_min15 error: {str(e)}')


# Data Types
type Response = dict[bool,Optional[str]]

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'python_plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

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


    ERROR_MESSAGE = 'Plugin Error!'

    # Generate command handler mapping
    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'plugin_py_func1': execute_func1_command,
        'plugin_py_func2': execute_func2_command,
        'plugin_py_func3': execute_func3_command,
        'calendar_tool': execute_calendar_tool_command,
        'predict_daily': execute_predict_daily_command,
        'predict_hourly': execute_predict_hourly_command,
        'predict_min15': execute_predict_min15_command,
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
                                input[PARAMS_PROPERTY] if PARAMS_PROPERTY in input else None,
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

        json_message = json.dumps(response)
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
    logging.info('Shutting down plugin')
    # shutdown function body
    return generate_success_response('shutdown success.')


def execute_func1_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `plugin_py_func1` function

    Customize this function as needed.

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing func1 with params: {params}')
    
    # implement command handler body here
    return generate_success_response('plugin_py_func1 success.')


def execute_func2_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `plugin_py_func2` function

    Customize this function as needed.

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing func2 with params: {params}')
    # implement command handler body here
    return generate_success_response('plugin_py_func2 success.')


def execute_func3_command(params:dict=None, context:dict=None, system_info:dict=None) -> dict:
    ''' Command handler for `plugin_py_func3` function

    Customize this function as needed.

    Args:
        params: Function parameters

    Returns:
        The function return value(s)
    '''
    logging.info(f'Executing func3 with params: {params}')
    # implement command handler body here
    return generate_success_response('plugin_py_func3 success.')


if __name__ == '__main__':
    main()

# Optionally, add a help string for calendar commands
CALENDAR_HELP = '''\nCalendar Tool Commands:\n- add [ticker] to calendar: action='add', symbol='TICKER'\n- remove [ticker] from calendar: action='remove', symbol='TICKER'\n- update calendar: action='update'\n- get today's events: action='today'\n- get events for [ticker]: action='get_events', symbol='TICKER'\n'''
