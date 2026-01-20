"""
Plugin Emulator entry point

Allows running the plugin emulator as a module:
    python -m plugin_emulator ...
"""

from .cli import main

if __name__ == '__main__':
    main()

