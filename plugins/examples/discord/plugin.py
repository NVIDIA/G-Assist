import json
import logging
import os
import requests
from ctypes import byref, windll, wintypes
from typing import Optional
# Data Types
Response = dict[bool, Optional[str]]

# Constants
LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'discord-plugin.log')
CONFIG_FILE = os.path.join(
    os.environ.get("PROGRAMDATA", "."),
    r'NVIDIA Corporation\nvtopps\rise\plugins\discord',
    'config.json'
)
CSV_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'Videos', 'NVIDIA', 'G-Assist')
BASE_MP4_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'Videos', 'NVIDIA')
BASE_SCREENSHOT_DIRECTORY = os.path.join(os.environ.get("USERPROFILE", "."), 'Videos', 'NVIDIA')

logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BOT_TOKEN = None
CHANNEL_ID = None
GAME_DIRECTORY = None

def main():
    TOOL_CALLS_PROPERTY = 'tool_calls'
    CONTEXT_PROPERTY = 'messages'
    SYSTEM_INFO_PROPERTY = 'system_info'
    FUNCTION_PROPERTY = 'func'
    PARAMS_PROPERTY = 'params'
    INITIALIZE_COMMAND = 'initialize'
    SHUTDOWN_COMMAND = 'shutdown'

    commands = {
        'initialize': execute_initialize_command,
        'shutdown': execute_shutdown_command,
        'send_message_to_discord_channel': send_message_to_discord_channel,
        'send_latest_chart_to_discord_channel': send_latest_chart_to_discord_channel,
        'send_latest_shadowplay_clip_to_discord_channel': send_latest_shadowplay_clip_to_discord_channel,
        'send_latest_screenshot_to_discord_channel': send_latest_screenshot_to_discord_channel,
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
                        if cmd == INITIALIZE_COMMAND or cmd == SHUTDOWN_COMMAND:
                            response = commands[cmd]()
                        else:
                            execute_initialize_command()
                            params = tool_call.get(PARAMS_PROPERTY, {})
                            context = tool_call.get(CONTEXT_PROPERTY, {})
                            system_info = tool_call.get(SYSTEM_INFO_PROPERTY, {})
                            logging.info(f'Executing command: {cmd} with params: {params}, context: {context}, system_info: {system_info}')
                            response = commands[cmd](params, context, system_info)
                    else:
                        logging.warning(f'Unknown command: {cmd}')
                        response = generate_failure_response(f'Unknown command: {cmd}')
                else:
                    logging.warning('Malformed input: missing function property')
                    response = generate_failure_response('Malformed input.')
        else:
            logging.warning('Malformed input: missing tool_calls property')
            response = generate_failure_response('Malformed input.')

        logging.info(f'Sending response: {response}')
        write_response(response)

        if cmd == SHUTDOWN_COMMAND:
            logging.info('Shutdown command received, terminating plugin')
            break

    logging.info('G-Assist Plugin stopped.')
    return 0


def read_command() -> dict | None:
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
        pass


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
    global BOT_TOKEN
    global CHANNEL_ID
    global GAME_DIRECTORY
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            BOT_TOKEN = config['BOT_TOKEN']
            CHANNEL_ID = config['CHANNEL_ID']
            GAME_DIRECTORY = config['GAME_DIRECTORY']
        logging.info('Config loaded successfully.')
        return generate_success_response('Initialize success.')
    except FileNotFoundError:
        logging.error('Config file not found, creating sample config.')
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                "BOT_TOKEN": "YOUR_BOT_TOKEN_HERE", 
                "CHANNEL_ID": "YOUR_CHANNEL_ID_HERE",
                "GAME_DIRECTORY": "GAME_DIRECTORY_HERE"
            }, f, indent=4)
        return generate_failure_response('Config file not found. Sample config created.')
    except Exception as e:
        logging.error(f'Error loading config: {str(e)}')
        return generate_failure_response('Failed to initialize.')


def execute_shutdown_command() -> dict:
    logging.info('Shutting down plugin')
    return generate_success_response('Shutdown success.')


def send_message_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    try:
        global CHANNEL_ID
        global BOT_TOKEN

        logging.info(f'Sending message to Discord channel: {CHANNEL_ID}')
        
        text = params['message']
        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"}
        payload = {"content": text}

        r = requests.post(url, headers=headers, json=payload)

        if r.status_code == 200 or r.status_code == 201:
            logging.info('Message sent successfully.')
            return generate_success_response('Message sent successfully.')
        else:
            logging.error(f'Failed to send message: {r.text}')
            return generate_failure_response(f'Failed to send message: {r.text}')

    except Exception as e:
        logging.error(f'Error in send_message_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending message.')


def find_latest_file(directory: str, extension: str) -> Optional[str]:
    try:
        files = [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(extension)]
        if not files:
            return None
        return max(files, key=os.path.getmtime)
    except Exception as e:
        logging.error(f'Error finding latest file: {str(e)}')
        return None


def send_latest_chart_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    try:
        caption = params.get('caption', '')
        file_path = find_latest_file(CSV_DIRECTORY, '.csv')

        if not file_path:
            return generate_failure_response('No CSV file found.')

        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        files = {"file": open(file_path, 'rb')}
        payload = {"content": caption}

        r = requests.post(url, headers=headers, data=payload, files=files)

        if r.status_code == 200 or r.status_code == 201:
            return generate_success_response('CSV sent successfully.')
        else:
            return generate_failure_response(f'Failed to send CSV: {r.text}')

    except Exception as e:
        logging.error(f'Error in send_latest_chart_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending CSV.')


def send_latest_shadowplay_clip_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    try:
        caption = params.get('caption', '') if params else ''
        mp4_directory = os.path.join(BASE_MP4_DIRECTORY, GAME_DIRECTORY)
        file_path = find_latest_file(mp4_directory, '.mp4')

        if not file_path:
            return generate_failure_response('No MP4 file found.')

        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        files = {"file": open(file_path, 'rb')}
        payload = {"content": caption}
        r = requests.post(url, headers=headers, data=payload, files=files)

        if r.status_code == 200 or r.status_code == 201:
            return generate_success_response('MP4 sent successfully.')
        else:
            return generate_failure_response(f'Failed to send MP4: {r.text}')

    except Exception as e:
        logging.error(f'Error in send_latest_shadowplay_clip_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending MP4.')


def send_latest_screenshot_to_discord_channel(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    try:
        caption = params.get('caption', '') if params else ''
        screenshot_directory = os.path.join(BASE_SCREENSHOT_DIRECTORY, GAME_DIRECTORY)
        file_path = find_latest_file(screenshot_directory, '.png')

        if not file_path:
            return generate_failure_response('No screenshot found.')

        url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages"
        headers = {"Authorization": f"Bot {BOT_TOKEN}"}
        files = {"file": open(file_path, 'rb')}
        payload = {"content": caption}

        r = requests.post(url, headers=headers, data=payload, files=files)

        if r.status_code == 200 or r.status_code == 201:
            return generate_success_response('Screenshot sent successfully.')
        else:
            return generate_failure_response(f'Failed to send screenshot: {r.text}')

    except Exception as e:
        logging.error(f'Error in send_latest_screenshot_to_discord_channel: {str(e)}')
        return generate_failure_response('Error sending screenshot.')


if __name__ == '__main__':
    main()
