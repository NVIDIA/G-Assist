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

# Get the directory where the plugin is deployed
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "stock")
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

# Save log in plugin directory for better organization
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'stock-plugin.log')
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load API Key from config file using absolute path
SETUP_COMPLETE = False
try:
    with open(CONFIG_FILE, "r") as config_file:
        config = json.load(config_file)
    API_KEY = config.get("TWELVE_DATA_API_KEY", "")
    if API_KEY and len(API_KEY) > 10:
        SETUP_COMPLETE = True
        logger.info(f"Successfully loaded API key from {CONFIG_FILE}")
    else:
        logger.warning(f"API key is empty or invalid in {CONFIG_FILE}")
        API_KEY = None
except FileNotFoundError:
    logger.error(f"Config file not found at {CONFIG_FILE}")
    API_KEY = None
except Exception as e:
    logger.error(f"Error loading config: {e}")
    API_KEY = None

def execute_setup_wizard() -> Response:
    """Guide user through API key setup.
    
    Returns:
        Response: Message response with setup instructions.
    """
    global SETUP_COMPLETE, API_KEY
    
    # Check if API key was added
    try:
        with open(CONFIG_FILE, "r") as config_file:
            config = json.load(config_file)
        new_key = config.get("TWELVE_DATA_API_KEY", "")
        if new_key and len(new_key) > 10:
            API_KEY = new_key
            SETUP_COMPLETE = True
            logger.info("API key successfully configured!")
            return {
                'success': True,
                'message': "✓ API key configured! You can now ask about stock prices. Try: 'What's the price of NVDA?'",
                'awaiting_input': False
            }
    except:
        pass
    
    # Show setup instructions
    message = f"""
STOCK PLUGIN - FIRST TIME SETUP
================================

Welcome! Let's get your free Twelve Data API key. This takes about 1 minute.

YOUR TASK - Get Your Free API Key:
   1. Visit: https://twelvedata.com/pricing
   2. Click "Get Free API Key" (no credit card required)
   3. Sign up with your email
   4. Copy your API key from the dashboard
   5. Open this file: {CONFIG_FILE}
   6. Replace the empty quotes with your API key:
      {{"TWELVE_DATA_API_KEY": "your_key_here"}}
   7. Save the file

After saving, send me ANY message (like "done") and I'll verify it!

Note: The free tier includes 800 API calls per day - plenty for personal use!
"""
    
    logger.info("Showing setup wizard to user")
    return {
        'success': True,
        'message': message,
        'awaiting_input': True
    }

def execute_initialize_command() -> Response:
    """Initialize the plugin.
    
    Returns:
        Response: Success response indicating plugin initialization.
    """
    logger.info("Initializing plugin...")
    
    # Check if setup is needed
    if not SETUP_COMPLETE or not API_KEY:
        return execute_setup_wizard()
    
    return generate_success_response("Stock plugin initialized successfully.")

def execute_shutdown_command() -> Response:
    """Shutdown the plugin.
    
    Returns:
        Response: Success response indicating plugin shutdown.
    """
    logger.info("Shutting down plugin...")
    return generate_success_response("shutdown success.")

def execute_get_ticker_from_company_command(params: Dict[str, Any] = None, *_, send_status_callback=None) -> Response:
    """Get stock ticker symbol from company name.
    
    Args:
        params (Dict[str, Any], optional): Parameters containing company_name.
        *_ : Additional unused arguments.
        send_status_callback (callable, optional): Callback to send status updates.
    
    Returns:
        Response: Success response with ticker symbol or failure response.
    """
    name = params.get("company_name", "")
    if not name:
        logger.error("No company name provided.")
        return generate_failure_response("Missing company_name.")
    
    # Send status update
    if send_status_callback:
        send_status_callback(generate_status_update(f"Looking up ticker for {name}..."))
    
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

def execute_get_stock_price_command(params: Dict[str, Any] = None, *_, send_status_callback=None) -> Response:
    """Get current stock price for a given ticker or company name.
    
    Args:
        params (Dict[str, Any], optional): Parameters containing ticker or company_name.
        *_ : Additional unused arguments.
        send_status_callback (callable, optional): Callback to send status updates.
    
    Returns:
        Response: Success response with stock price or failure response.
    """
    query = params.get("ticker") or params.get("company_name")
    if not query:
        logger.error("No query provided.")
        return generate_failure_response("Provide either ticker or company_name.")
    
    # Send status update
    if send_status_callback:
        send_status_callback(generate_status_update(f"Fetching stock price for {query}..."))
    
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

def generate_status_update(message: str) -> Dict[str, Any]:
    """Generate a status update (not a final response).
    
    Status updates are intermediate messages that don't end the plugin execution.
    They should NOT include 'success' field to avoid being treated as final responses.
    
    Args:
        message (str): Status message to display to user.
    
    Returns:
        Dict: Status update with message only.
    """
    return {'status': 'in_progress', 'message': message}

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
            success = windll.kernel32.ReadFile(
                pipe,
                buffer,
                BUFFER_SIZE,
                byref(message_bytes),
                None
            )

            if not success:
                logger.error('Error reading from command pipe')
                return None

            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            if message_bytes.value < BUFFER_SIZE:
                break

        retval = ''.join(chunks)
        logger.info(f'[PIPE] Read {len(retval)} bytes from pipe')
        return json.loads(retval)
    except Exception as e:
        logger.error(f'Error in read_command: {e}')
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
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)
        
        # Log what we're sending
        msg_type = response.get('success', 'unknown') if isinstance(response, dict) else 'unknown'
        logger.info(f"[PIPE] Writing message: success={msg_type}, length={message_len} bytes")

        bytes_written = wintypes.DWORD()
        success = windll.kernel32.WriteFile(
            pipe,
            message_bytes,
            message_len,
            bytes_written,
            None
        )
        
        if success:
            logger.info(f"[PIPE] Write OK - success={msg_type}, bytes={bytes_written.value}/{message_len}")
        else:
            logger.error(f"[PIPE] Write FAILED - GetLastError={windll.kernel32.GetLastError()}")
    except Exception as e:
        logger.error(f'Error writing response: {e}')

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
    read_failures = 0
    MAX_READ_FAILURES = 3
    
    while cmd != SHUTDOWN_COMMAND:
        response = None
        input = read_command()
        if input is None:
            read_failures += 1
            logger.error(f'Error reading command (failure {read_failures}/{MAX_READ_FAILURES})')
            if read_failures >= MAX_READ_FAILURES:
                logger.error('Too many read failures, exiting')
                break
            continue
        
        # Reset failure counter on successful read
        read_failures = 0

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
                            # Check if setup is needed before executing stock functions
                            if not SETUP_COMPLETE or not API_KEY:
                                logger.info('[COMMAND] API key not configured - starting setup wizard')
                                response = execute_setup_wizard()
                            else:
                                params = tool_call.get(PARAMS_PROPERTY, {})
                                context = input.get(CONTEXT_PROPERTY)
                                system_info = input.get(SYSTEM_INFO_PROPERTY)
                                response = commands[cmd](params, context, system_info, send_status_callback=write_response)
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
