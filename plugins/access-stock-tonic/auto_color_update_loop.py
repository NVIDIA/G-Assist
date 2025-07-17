#!/usr/bin/env python3
"""
Auto Color Update Loop for Access Stock Tonic Plugin

This script repeatedly calls the Access Stock Tonic plugin's auto_color_update tool
(e.g., via subprocess or direct import) at a configurable interval (default: 60 seconds).

Usage:
    python auto_color_update_loop.py [--interval SECONDS] [--log LOGFILE]

- Ensure the G-Assist plugin is installed and accessible.
- This script can be run in the background or as a scheduled task.
- Logs actions and errors to a file (default: auto_color_update_loop.log).

Example:
    python auto_color_update_loop.py --interval 30

"""
import time
import argparse
import logging
import sys
import os
import subprocess
from datetime import datetime

DEFAULT_INTERVAL = 60  # seconds
DEFAULT_LOG = 'auto_color_update_loop.log'

parser = argparse.ArgumentParser(description='Auto Color Update Loop for Access Stock Tonic')
parser.add_argument('--interval', type=int, default=DEFAULT_INTERVAL, help='Update interval in seconds (default: 60)')
parser.add_argument('--log', type=str, default=DEFAULT_LOG, help='Log file path')
args = parser.parse_args()

logging.basicConfig(filename=args.log, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Path to the plugin executable (update if needed)
PLUGIN_EXECUTABLE = os.path.abspath('./access_stock_tonic.exe')

# JSON command to send to the plugin
AUTO_COLOR_UPDATE_COMMAND = '{"tool_calls": [{"func": "auto_color_update", "params": {}}]}'

logging.info('Starting auto_color_update loop with interval %d seconds', args.interval)

while True:
    try:
        # On Windows, use subprocess to call the plugin executable
        # The plugin should read JSON from stdin and write JSON to stdout
        logging.info('Calling auto_color_update tool')
        proc = subprocess.Popen(
            [PLUGIN_EXECUTABLE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False
        )
        stdout, stderr = proc.communicate(input=AUTO_COLOR_UPDATE_COMMAND.encode('utf-8'), timeout=30)
        if proc.returncode != 0:
            logging.error('Plugin exited with code %d: %s', proc.returncode, stderr.decode('utf-8', errors='ignore'))
        else:
            logging.info('Plugin response: %s', stdout.decode('utf-8', errors='ignore'))
    except Exception as e:
        logging.error('Error during auto_color_update: %s', str(e))
    time.sleep(args.interval) 