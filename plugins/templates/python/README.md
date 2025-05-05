# G-Assist Python Plugin Template

Transform your ideas into powerful G-Assist plugins with our Python template! This template provides everything you need to create Windows-based plugins that seamlessly communicate with the G-Assist plugin manager. Whether you're building your first plugin or your fiftieth, this template will help you get started quickly.

## What Can It Do?
- Built-in pipe communication with G-Assist plugin manager
- Ready-to-use command handling system
- Comprehensive logging system
- Support for initialization and shutdown procedures
- Easily extensible function framework

## Before You Start
Make sure you have:
- Windows PC
- Python 3.12 or higher
- G-Assist installed on your system
- pywin32 >= 223
- Basic knowledge of Python

💡 **Tip**: Use a virtual environment to keep your plugin dependencies isolated from other Python projects!

## Installation Guide

### Step 1: Get the Files
```bash
git clone --recurse-submodules <repository-url>
cd python-template
```
This downloads the template and all necessary files to your computer.

### Step 2: Set Up Python Environment
```bash
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
```
This creates a clean environment and installs all required packages.

## How to Customize

### Basic Command Structure
The template comes with three example functions ready for customization:
```python
def execute_new_function(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    logging.info(f'Executing new function with params: {params}')
    # Your code here!
    return generate_success_response('Success!')
```

💡 **Tip**: Each function gets params, context, and system_info dictionaries - use them to make your plugin smarter!

### Adding New Commands
1. Create your function in `commands.py`:
```python
def execute_my_command(params: dict = None, context: dict = None, system_info: dict = None) -> dict:
    # Your amazing code here
    return generate_success_response('Done!')
```

2. Register it in the commands dictionary:
```python
commands = {
    'initialize': execute_initialize_command,
    'my_command': execute_my_command,
}
```

💡 **Tip**: Use descriptive command names that reflect what your function does!

## Logging
Your plugin automatically logs to `python_plugin.log` in your user's profile directory. It tracks:
- Plugin startup and shutdown
- Command reception and processing
- Error conditions
- Function execution details

## Troubleshooting Tips
- **Plugin not starting?** Check if Python 3.12+ is installed and in PATH
- **Communication errors?** Verify pywin32 is installed correctly
- **Commands not working?** Double-check your command registration
- **Missing logs?** Ensure write permissions in user profile directory

## Want to Contribute?
We'd love your help making this template even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.