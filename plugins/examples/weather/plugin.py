"""
Weather Plugin - A Windows-based plugin that provides weather information for specified cities.

This plugin communicates through standard input/output pipes and provides weather data
using the wttr.in service. It includes logging functionality and proper error handling.

The plugin is a service that:
1. Listens for commands through standard input
2. Processes weather requests using the wttr.in API
3. Returns responses through standard output
4. Maintains detailed logging of all operations

Dependencies:
    - requests: For making HTTP requests to wttr.in
    - ctypes: For Windows API interaction
    - logging: For operation logging
    - json: For message serialization/deserialization

Usage:
    The plugin is designed to be run as a Windows service and communicates through
    standard input/output pipes. It accepts JSON-formatted commands and returns
    JSON-formatted responses.

Example Command Format:
    {
        "tool_calls": [
            {
                "func": "get_weather_info",
                "params": {"city": "London"}
            }
        ]
    }

Example Response Format:
    {
        "success": true,
        "message": "Partly cloudy, 15 degrees Celsius, Humidity: 65%"
    }
"""

import json
import sys
import requests
import logging
import os
from ctypes import byref, windll, wintypes
from typing import Optional, Dict, Any

# Type definitions
Response = Dict[bool, Optional[str]]


# Configure logging with a more detailed format
LOG_FILE = os.path.join(os.environ.get('USERPROFILE', '.'), 'weather-plugin.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
)

def get_weather_info(params: dict = None) -> dict:
    """
    Retrieves weather information for a specified city using the wttr.in service.
    
    Args:
        params (dict, optional): Dictionary containing parameters. Must include 'city' key.
            Example: {"city": "London"}
        
    Returns:
        dict: A dictionary containing:
            - success (bool): Whether the operation was successful
            - message (str): Weather information or error message
            
    Example:
        >>> get_weather_info({"city": "London"})
        {
            "success": True,
            "message": "Partly cloudy, 15 degrees Celsius, Humidity: 65%"
        }
        
    Raises:
        No exceptions are raised. All errors are caught and returned in the response dict.
    """
    if not params or "city" not in params:
        logging.error("City parameter is required in get_weather_info")
        return {"success": False, "message": "City parameter is required."}
    
    city = params["city"]
    url = f"https://wttr.in/{city}?format=j1"
    
    try:
        response = requests.get(url, timeout=10)  # Add timeout for better reliability
        if response.status_code == 200:
            weather_data = response.json()
            
            # Extract relevant information from the JSON response
            current_condition = weather_data.get('current_condition', [{}])[0]
            temperature = current_condition.get('temp_C', 'N/A')
            condition = current_condition.get('weatherDesc', [{'value': 'Unknown'}])[0].get('value', 'Unknown')
            humidity = current_condition.get('humidity', 'N/A')
            
            # Sanitize the condition text
            condition = ''.join(c for c in condition if c.isprintable() and c.isascii())
            
            # Create a human-readable message with sanitized text
            message = f"{condition}, {temperature} degrees Celsius, Humidity: {humidity}%"
            
            logging.info(f"Weather data retrieved successfully for city: {city}")
            return {
                "success": True,
                "message": message
            }
        else:
            logging.error(f"Failed to retrieve weather data for city: {city}. Status code: {response.status_code}")
            return {"success": False, "message": f"Failed to retrieve weather data. Status code: {response.status_code}"}
    except requests.Timeout:
        logging.error(f"Timeout while retrieving weather data for city: {city}")
        return {"success": False, "message": "Request timed out. Please try again."}
    except requests.RequestException as e:
        logging.error(f"Request error while retrieving weather data for city: {city}. Error: {str(e)}")
        return {"success": False, "message": f"Error retrieving weather data: {str(e)}"}
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse weather data for city: {city}. Error: {str(e)}")
        return {"success": False, "message": "Failed to parse weather data."}
    except Exception as e:
        logging.error(f"Unexpected error while retrieving weather data for city: {city}. Error: {str(e)}")
        return {"success": False, "message": f"An unexpected error occurred: {str(e)}"}

def main():
    """
    Main entry point for the weather plugin.
    
    Sets up command handling and maintains the main event loop for processing commands.
    The plugin supports the following commands:
        - initialize: Initializes the plugin
        - shutdown: Terminates the plugin
        - get_weather_info: Retrieves weather information for a city
        
    The function continues running until a shutdown command is received.
    
    Command Processing:
        1. Reads input from standard input
        2. Parses the JSON command
        3. Executes the appropriate function
        4. Writes the response to standard output
        
    Error Handling:
        - Invalid commands are logged and ignored
        - Communication errors are logged
        - All errors are caught and handled gracefully
    """
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'
    GET_WEATHER_INFO_COMMAND = 'get_weather_info'

    commands = {
        'initialize': lambda _: {"success": True, "message": "Plugin initialized"},
        'shutdown': lambda _: {"success": True, "message": "Plugin shutdown"},
        'get_weather_info': get_weather_info,
    }
    
    while True:
        command = read_command()
        if command is None:
            logging.error('Error reading command')
            continue
        
        tool_calls = command.get("tool_calls", [])
        for tool_call in tool_calls:
            logging.info(f"Tool call: {tool_call}")
            func = tool_call.get("func")
            logging.info(f"Function: {func}")
            params = tool_call.get("params", {})
            logging.info(f"Params: {params}")
            
            if func == INITIALIZE_COMMAND:
                response = commands.get(INITIALIZE_COMMAND, lambda _: {"success": False, "message": "Unknown command"})()
            elif func == GET_WEATHER_INFO_COMMAND:
                logging.info(f"Getting weather info for {params}")
                response = get_weather_info(params)
                logging.info(f"Weather info: {response}")
            elif func == SHUTDOWN_COMMAND:
                response = commands.get(SHUTDOWN_COMMAND, lambda _: {"success": False, "message": "Unknown command"})()
                write_response(response)
                return
            else:
                response = {'success': False, 'message': "Unknown function call"}
            
            write_response(response)
    
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

        # Combine all chunks and parse JSON
        retval = ''.join(chunks)
        return json.loads(retval)

    except json.JSONDecodeError:
        logging.error(f'Received invalid JSON: {retval}')
        return None
    except Exception as e:
        logging.error(f'Exception in read_command(): {str(e)}')
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
            logging.error('Error writing to response pipe')

    except Exception as e:
        logging.error(f'Exception in write_response(): {str(e)}')


if __name__ == '__main__':
    main()
