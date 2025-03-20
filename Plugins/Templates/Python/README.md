# RISE Python Plugin Template

A template for creating Windows-based RISE plugins in Python. This plugin template provides a foundation for building plugins that communicate with the RISE plugin manager through pipes.

## Features

- Windows-based plugin architecture
- Pipe-based communication with RISE plugin manager
- Built-in command handling system
- Comprehensive logging system
- Support for initialization and shutdown procedures
- Extensible function framework

## Requirements

- Python 3.12 or higher
- Windows operating system
- pywin32 >= 223

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

The plugin template provides a basic structure with:

- Command handling system
- Pipe-based communication
- Logging functionality (logs to `python_plugin.log` in user's profile directory)
- Three example functions ready to be customized

### Basic Structure

The plugin operates as follows:
1. Initializes and waits for commands via pipe
2. Processes received commands
3. Returns responses
4. Continues until receiving a shutdown command

### Available Commands

- `initialize`: Plugin initialization
- `shutdown`: Clean plugin shutdown
- `plugin_py_func1`: Example function 1
- `plugin_py_func2`: Example function 2
- `plugin_py_func3`: Example function 3

### Customizing Functions

To add new functionality:

1. Create a new command handler function:
```python
def execute_new_function(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    logging.info(f'Executing new function with params: {params}')
    # Implementation here
    return generate_success_response('success message')
```

2. Add the function to the commands dictionary in main():
```python
commands = {
    'initialize': execute_initialize_command,
    'shutdown': execute_shutdown_command,
    'new_function': execute_new_function,
}
```

## Logging

The plugin logs all major operations to `python_plugin.log` in the user's profile directory. Logs include:
- Plugin startup and shutdown
- Command reception and processing
- Error conditions
- Function execution details

## Error Handling

The plugin includes comprehensive error handling for:
- Malformed input
- Communication errors
- Command processing failures
- Response writing issues

## License

Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Copyright

SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## Support

For support, please [open an issue](../../issues) in the repository.
