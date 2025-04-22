import json
import logging
import os
from ctypes import byref, windll, wintypes
from typing import Optional, Dict, Any
import requests

# Type definitions
Response = Dict[bool, Optional[str]]

# Constants
TOOL_CALLS_PROPERTY = 'tool_calls'
CONTEXT_PROPERTY = 'messages'
SYSTEM_INFO_PROPERTY = 'system_info'
FUNCTION_PROPERTY = 'func'
PARAMS_PROPERTY = 'params'
INITIALIZE_COMMAND = 'initialize'
SHUTDOWN_COMMAND = 'shutdown'
ERROR_MESSAGE = 'Plugin Error!'

# Configure logging
LOG_FILE = os.path.join(os.path.expanduser("~"), 'stock_plugin.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load API Key from config file
with open("config.json", "r") as config_file:
    config = json.load(config_file)
API_KEY = config.get("TWELVE_DATA_API_KEY")

def execute_initialize_command() -> Response:
    """Initialize the plugin.
    
    Returns:
        Response: Success response indicating plugin initialization.
    """
    logger.info("Initializing plugin...")
    return generate_success_response("initialize success.")

def execute_shutdown_command() -> Response:
    """Shutdown the plugin.
    
    Returns:
        Response: Success response indicating plugin shutdown.
    """
    logger.info("Shutting down plugin...")
    return generate_success_response("shutdown success.")

def execute_get_ticker_from_company_command(params: Dict[str, Any] = None, *_) -> Response:
    """Get stock ticker symbol from company name.
    
    Args:
        params (Dict[str, Any], optional): Parameters containing company_name.
        *_ : Additional unused arguments.
    
    Returns:
        Response: Success response with ticker symbol or failure response.
    """
    name = params.get("company_name", "")
    if not name:
        logger.error("No company name provided.")
        return generate_failure_response("Missing company_name.")
    url = f"https://api.twelvedata.com/symbol_search?symbol={name}&apikey={API_KEY}"
    try:
        response = requests.get(url).json()
        results = response.get("data", [])
        if not results:
            logger.error(f"No match found for company name. {response}")
            return generate_failure_response("No match found for company name.")
        best = results[0]
        logger.info(f"Found ticker for '{best['instrument_name']}' on {best['exchange']}: {best['symbol']}")
        return generate_success_response(f"Found ticker for '{best['instrument_name']}' on {best['exchange']}: {best['symbol']}")
    except Exception as e:
        logger.error(f"Error in get_ticker_from_company: {str(e)}")
        return generate_failure_response("Failed to get ticker from company name.")

def execute_get_stock_price_command(params: Dict[str, Any] = None, *_) -> Response:
    """Get current stock price for a given ticker or company name.
    
    Args:
        params (Dict[str, Any], optional): Parameters containing ticker or company_name.
        *_ : Additional unused arguments.
    
    Returns:
        Response: Success response with stock price or failure response.
    """
    query = params.get("ticker") or params.get("company_name")
    if not query:
        logger.error("No query provided.")
        return generate_failure_response("Provide either ticker or company_name.")
    url = f"https://api.twelvedata.com/quote?symbol={query}&apikey={API_KEY}"
    try:
        data = requests.get(url).json()
        if "symbol" not in data:
            logger.error(f"No quote found for that input. {data}")
            return generate_failure_response("No quote found for that input.")
        
        # Get the appropriate price based on market status
        is_market_open = data.get("is_market_open", False)
        if is_market_open:
            price = data.get("close", "0")  # Use current price when market is open
            price_type = "current"
        else:
            price = data.get("close", "0")  # Use closing price when market is closed
            price_type = "closing"
            
        timestamp = data.get("datetime", "unknown time")
        change = data.get("change", "0")
        percent_change = data.get("percent_change", "0")
        logger.info(f"Stock price: {price}, Timestamp: {timestamp}, Market Open: {is_market_open}")
        return generate_success_response(
            f"The {price_type} stock price for {data['symbol']} is ${price} USD (as of {timestamp}). "
            f"Change: ${change} ({percent_change}%)"
        )
    except Exception as e:
        logger.error(f"Error in get_stock_price: {str(e)}")
        return generate_failure_response("Failed to fetch stock price.")

def generate_failure_response(message: str = None) -> Response:
    """Generate a failure response.
    
    Args:
        message (str, optional): Error message. Defaults to "Command failed."
    
    Returns:
        Response: Failure response with message.
    """
    return {'success': False, 'message': message or "Command failed."}

def generate_success_response(message: str = None) -> Response:
    """Generate a success response.
    
    Args:
        message (str, optional): Success message. Defaults to "Command succeeded."
    
    Returns:
        Response: Success response with message.
    """
    return {'success': True, 'message': message or "Command succeeded."}

def read_command() -> Dict[str, Any] | None:
    """Read command from stdin pipe.
    
    Reads JSON-formatted command from Windows pipe.
    
    Returns:
        Dict[str, Any] | None: Parsed command dictionary or None if error.
    """
    try:
        STD_INPUT_HANDLE = -10
        pipe = windll.kernel32.GetStdHandle(STD_INPUT_HANDLE)
        chunks = []
        while True:
            BUFFER_SIZE = 4096
            message_bytes = wintypes.DWORD()
            buffer = bytes(BUFFER_SIZE)
            success = windll.kernel32.ReadFile(pipe, buffer, BUFFER_SIZE, byref(message_bytes), None)
            if not success:
                return None
            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)
            if message_bytes.value < BUFFER_SIZE:
                break
        retval = ''.join(chunks)
        return json.loads(retval)
    except:
        return None

def write_response(response: Response) -> None:
    """Write response to stdout pipe.
    
    Writes JSON-formatted response to Windows pipe with <<END>> marker.
    The marker is used by the reader to determine the end of the response.
    
    Args:
        response (Response): Response dictionary to write.
    
    Response Format:
        JSON-encoded dictionary followed by <<END>> marker.
        Example: {"success":true,"message":"Plugin initialized successfully"}<<END>>
    """
    try:
        pipe = windll.kernel32.GetStdHandle(-11)
        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        
        bytes_written = wintypes.DWORD()
        windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            len(message_bytes),
            bytes_written,
            None
        )
    except Exception as e:
        logging.error(f'Error writing response: {e}')

def main() -> int:
    """Main plugin entry point.
    
    Processes commands from stdin and writes responses to stdout.
    Commands are processed in a loop until shutdown command is received.
    
    Returns:
        int: Exit code (0 for success).
    """
    logger.info("Starting plugin...")
    
    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'get_stock_price': execute_get_stock_price_command,
        'get_ticker_from_company': execute_get_ticker_from_company_command
    }

    cmd = ''
    logger.info('Plugin started')
    while cmd != SHUTDOWN_COMMAND:
        response = None
        input = read_command()
        if input is None:
            logger.error('Error reading command')
            continue

        logger.info(f'Received input: {input}')
        if TOOL_CALLS_PROPERTY in input:
            for tool_call in input[TOOL_CALLS_PROPERTY]:
                if FUNCTION_PROPERTY in tool_call:
                    cmd = tool_call[FUNCTION_PROPERTY]
                    logger.info(f'Processing command: {cmd}')
                    if cmd in commands:
                        if cmd in ['initialize', 'shutdown']:
                            response = commands[cmd]()
                        else:
                            params = tool_call.get(PARAMS_PROPERTY, {})
                            context = input.get(CONTEXT_PROPERTY)
                            system_info = input.get(SYSTEM_INFO_PROPERTY)
                            response = commands[cmd](params, context, system_info)
                    else:
                        logger.error(f'Unknown command: {cmd}')
                        response = generate_failure_response(f'{ERROR_MESSAGE} Unknown command: {cmd}')
                else:
                    logger.error(f'Malformed input: {tool_call}')
                    response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')
        else:
            logger.error(f'Malformed input: {input}')
            response = generate_failure_response(f'{ERROR_MESSAGE} Malformed input.')

        write_response(response)
        if cmd == SHUTDOWN_COMMAND:
            break
    return 0

if __name__ == "__main__":
    main()
