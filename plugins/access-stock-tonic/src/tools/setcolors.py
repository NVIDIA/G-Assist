import os
import json
import logging
from openrgb import OpenRGBClient
from openrgb.utils import RGBColor
from datetime import datetime, timedelta
from src.tools.calendar_tool import CalendarTool

LOG_FILE = os.path.join(os.environ.get("USERPROFILE", "."), 'access_stock_tonic.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

COLOR_MAP = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'purple': (128, 0, 128),
    'violet': (128, 0, 128),
    'orange': (255, 165, 0),
    'pink': (255, 192, 203),
    'white': (255, 255, 255),
    'black': (0, 0, 0),
    'grey': (128, 128, 128),
    'gray': (128, 128, 128)
}
COLOR_ALIASES = {
    'grey': 'gray',
    'violet': 'purple'
}

openrgb_client = None
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '../../color_feedback_config.json')

def load_color_feedback_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {"none": "blue", "near": "yellow", "imminent": "red"}

def save_color_feedback_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def list_supported_colors():
    return sorted(set(COLOR_MAP.keys()))

def set_keyboard_color(color):
    global openrgb_client
    color_name = color.lower()
    color_name = COLOR_ALIASES.get(color_name, color_name)
    if color_name not in COLOR_MAP:
        supported = ', '.join(sorted(COLOR_MAP.keys()))
        raise ValueError(f'Unknown color: {color_name}. Supported colors are: {supported}')
    r, g, b = COLOR_MAP[color_name]
    rgb_color = RGBColor(r, g, b)
    if openrgb_client is None:
        openrgb_client = OpenRGBClient('127.0.0.1', 6742, 'Access Stock Tonic Plugin')
    devices = openrgb_client.devices
    if not devices:
        raise RuntimeError('No RGB devices found.')
    for device in devices:
        device.set_color(rgb_color)
    logging.info(f'Successfully set color {color_name} on all devices.')
    return color_name

def configure_color_feedback(mode, color):
    mode = mode.lower()
    color_name = color.lower()
    color_name = COLOR_ALIASES.get(color_name, color_name)
    if color_name not in COLOR_MAP:
        supported = ', '.join(sorted(COLOR_MAP.keys()))
        raise ValueError(f'Unknown color: {color_name}. Supported colors are: {supported}')
    config = load_color_feedback_config()
    config[mode] = color_name
    save_color_feedback_config(config)
    logging.info(f'Configured color feedback: {mode} -> {color_name}')
    return mode, color_name

def auto_color_update():
    """Reads the calendar and sets the color based on event proximity."""
    calendar = CalendarTool()
    events = calendar.get_todays_events()  # Should return a list of events with timestamps
    config = load_color_feedback_config()
    now = datetime.now()
    imminent_threshold = timedelta(hours=1)
    near_threshold = timedelta(hours=6)
    soonest_event = None
    soonest_time = None
    for event in events:
        event_time = event.get('datetime')
        if isinstance(event_time, str):
            event_time = datetime.fromisoformat(event_time)
        if soonest_time is None or event_time < soonest_time:
            soonest_time = event_time
            soonest_event = event
    if soonest_time is None:
        # No events today
        set_keyboard_color(config.get('none', 'blue'))
        return 'none', config.get('none', 'blue')
    delta = soonest_time - now
    if delta <= imminent_threshold:
        set_keyboard_color(config.get('imminent', 'red'))
        return 'imminent', config.get('imminent', 'red')
    elif delta <= near_threshold:
        set_keyboard_color(config.get('near', 'yellow'))
        return 'near', config.get('near', 'yellow')
    else:
        set_keyboard_color(config.get('none', 'blue'))
        return 'none', config.get('none', 'blue') 