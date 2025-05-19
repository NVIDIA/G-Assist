import json
import logging
import os
import requests
import feedparser
from ctypes import byref, windll, wintypes
from typing import Dict, Optional, List

# Data Types
Response = Dict[bool, Optional[str]]

CONFIG_FILE = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    "NVIDIA Corporation",
    "nvtopps",
    "rise",
    "plugins",
    "ifttt",
    "config.json"
)

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'ifttt_plugin.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

IFTTT_WEBHOOK_KEY = None
EVENT_NAME = None
MAIN_RSS_URL = "https://feeds.feedburner.com/ign/pc-articles"  # using IGN PC Gaming RSS feed as default
ALTERNATE_RSS_URL = "https://feeds.feedburner.com/ign/all"  # using IGN All RSS feed as default

def main():
    TOOL_CALLS_PROPERTY = 'tool_calls'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'params'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'
    ERROR_MESSAGE = 'Plugin Error!'

    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'trigger_gaming_setup': execute_run_applet_command,
    }
    cmd = ''

    logging.info('IFTTT Plugin started')
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
                        if cmd in [INITIALIZE_COMMAND, SHUTDOWN_COMMAND]:
                            response = commands[cmd]()
                        else:
                            params = tool_call.get(PARAMS_PROPERTY, {})
                            response = commands[cmd](params)
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

    logging.info('IFTTT Plugin stopped.')
    return 0

def read_command() -> dict or None:
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
                logging.error('Error reading from command pipe')
                return None

            chunk = buffer.decode('utf-8')[:message_bytes.value]
            chunks.append(chunk)

            if message_bytes.value < BUFFER_SIZE:
                break

        retval = ''.join(chunks)
        return json.loads(retval)

    except json.JSONDecodeError:
        logging.error('Failed to decode JSON input')
        return None
    except Exception as e:
        logging.error(f'Unexpected error in read_command: {str(e)}')
        return None

def write_response(response: Response) -> None:
    try:
        STD_OUTPUT_HANDLE = -11
        pipe = windll.kernel32.GetStdHandle(STD_OUTPUT_HANDLE)

        json_message = json.dumps(response) + '<<END>>'
        message_bytes = json_message.encode('utf-8')
        message_len = len(message_bytes)

        bytes_written = wintypes.DWORD()
        windll.kernel32.WriteFile(pipe, message_bytes, message_len, byref(bytes_written), None)

    except Exception as e:
        logging.error(f'Failed to write response: {str(e)}')

def generate_failure_response(message: str = None) -> Response:
    response = { 'success': False }
    if message:
        response['message'] = message
    return response

def generate_success_response(message: str = None) -> Response:
    response = { 'success': True }
    if message:
        response['message'] = message
    return response

def execute_initialize_command() -> dict:
    logging.info('Initializing plugin')
    return generate_success_response('initialize success.')

def execute_shutdown_command() -> dict:
    logging.info('Shutting down plugin')
    return generate_success_response('shutdown success.')

def fetch_ign_gaming_news() -> List[str]:
    """
    Fetches the latest gaming news from IGN RSS feed.
    
    Returns:
        List of headlines for the top 3 gaming news articles.
    """
    try:
        logging.info('Fetching IGN gaming news')
        
        # using feedparser to fetch and parse the IGN gaming news RSS feed
        feed_url = MAIN_RSS_URL
        feed = feedparser.parse(feed_url)
        
        # if the feed URL is not working, try the alternative
        if not feed.entries:
            logging.info(f'Main RSS feed returned no entries, trying alternative: {ALTERNATE_RSS_URL}')
            feed_url = ALTERNATE_RSS_URL
            feed = feedparser.parse(feed_url)
        
        # get the top 3 news headlines and store in headlines list
        headlines = []
        for entry in feed.entries[:3]:
            headlines.append(entry.title)
        
        logging.info(f'Successfully fetched {len(headlines)} news headlines from IGN')
        return headlines
    
    except Exception as e:
        logging.error(f'Error fetching IGN gaming news: {str(e)}')
        return []

def execute_run_applet_command(params: dict = None) -> dict:
    logging.info(f'Executing run_applet with params: {params}')

    global IFTTT_WEBHOOK_KEY, EVENT_NAME, MAIN_RSS_URL, ALTERNATE_RSS_URL, CONFIG_FILE

    if os.path.isfile(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as file:
            config = json.load(file)
            IFTTT_WEBHOOK_KEY = config.get('webhook_key')
            EVENT_NAME = config.get('event_name')
            MAIN_RSS_URL = config.get('main_rss_url', MAIN_RSS_URL)
            ALTERNATE_RSS_URL = config.get('alternate_rss_url', ALTERNATE_RSS_URL)
    
    try:
        if EVENT_NAME is None or IFTTT_WEBHOOK_KEY is None:
            return generate_failure_response('Missing required parameter: event_name or webhook_key')

        webhook_url = f'https://maker.ifttt.com/trigger/{EVENT_NAME}/with/key/{IFTTT_WEBHOOK_KEY}'
        
        # initialize webhook data
        webhook_data = {}
        
        # Always fetch and include IGN news in the webhook
        headlines = fetch_ign_gaming_news()
        
        if headlines:
            # format the news items for IFTTT webhook (up to 3 values) from the headlines list
            # formatting based on the IFTTT webhook body documentation (https://ifttt.com/maker_webhooks)
            for i, headline in enumerate(headlines[:3], 1):
                webhook_data[f'value{i}'] = headline
                
            logging.info(f'Including {len(headlines)} news headlines in webhook')
        
        # Send the webhook request with data if we have any, otherwise send without data
        if webhook_data:
            response = requests.post(webhook_url, json=webhook_data)
        else:
            response = requests.post(webhook_url)

        if response.status_code >= 200 and response.status_code < 300:
            return generate_success_response(f'IFTTT applet {EVENT_NAME} triggered successfully.')
        else:
            logging.error(f'IFTTT webhook {EVENT_NAME} failed: {response.text}')
            return generate_failure_response(f'IFTTT applet {EVENT_NAME} failed: {response.text}')

    except Exception as e:
        logging.error(f'Error triggering IFTTT webhook {EVENT_NAME}: {str(e)}')
        return generate_failure_response(f'Error triggering IFTTT applet {EVENT_NAME}: {str(e)}')

if __name__ == '__main__':
    main()