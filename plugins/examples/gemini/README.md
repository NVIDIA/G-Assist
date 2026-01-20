# Gemini Plugin for G-Assist

Transform your G-Assist experience with the power of Google's Gemini AI! This plugin integrates Gemini's advanced AI capabilities directly into G-Assist, allowing you to generate text, maintain contextual conversations, and get AI-powered responses with ease.

## What Can It Do?
- Generate human-like text responses using Gemini
- Hold context-aware conversations that remember previous interactions
- Built-in safety settings for content filtering
- Real-time streaming responses
- Seamless integration with G-Assist

## Before You Start
Make sure you have:
- Python 3.8 or higher
- Google Cloud API key with Gemini access
- G-Assist installed on your system

💡 **Tip**: You'll need a Google Cloud API key specifically enabled for Gemini. Get one from the [Google AI Studio](https://aistudio.google.com/apikey)!

## Installation Guide

### Step 1: Get the Files
```bash
git clone <repo link>
cd gemini-plugin
```

### Step 2: Set Up Python Packages
```bash
python -m pip install -r requirements.txt
```

### Step 3: Configure the Model (Optional)
Adjust `config.json` to your needs:
```json
{
  "model": "gemini-2.5-flash"
}
```

### Step 4: Build and Deploy the Plugin
From the `plugins/examples` directory, run:
```bash
setup.bat gemini --deploy
```
This will build the plugin and deploy it to the G-Assist plugins directory.


## How to Use
Once installed, you can use Gemini through G-Assist! On first use, the plugin will guide you through a setup wizard to configure your API key - just paste it directly in the chat when prompted.

Try these examples:

### Basic Text Generation
- Tell me about artificial intelligence.
- Explain ray tracing using a real-world analogy in one sentence. ELI5

### Search
- What's the weather in Santa Clara, CA?
- What are the top five features in the latest major patch of RUST?

## Limitations
- Requires active internet connection
- Subject to Google's API rate limits
- Image generation not supported
- Must be used within G-Assist environment

### Logging
The plugin logs all activity to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gassist_sdk.log
```
Check this file for detailed error messages and debugging information.

## Troubleshooting Tips
- **API Key Not Working?** The plugin will prompt you to paste a new key in chat
- **Commands Not Working?** Ensure all files are in the correct plugin directory
- **Unexpected Responses?** Check the configuration in `config.json`
- **Logs**: Check `gassist_sdk.log` in the plugin directory for detailed logs

## Developer Documentation

### Architecture Overview
The Gemini plugin is built using the G-Assist Python SDK (`gassist_sdk`), which handles communication with G-Assist via JSON-RPC 2.0 over pipes. The plugin provides:
1. Web search queries using Google Search grounding
2. Conversational AI responses with context awareness

### Core Components

#### SDK Integration
- Uses `gassist_sdk.Plugin` for protocol handling and command registration
- Commands are registered via decorators: `@plugin.command("command_name")`
- Streaming responses sent via `plugin.stream()` for real-time output
- Session management via `plugin.set_keep_session()` for conversational mode

#### Key Functions

##### Command: `query_gemini`
- Main entry point for Gemini queries
- Handles API key validation with background keepalives (prevents timeout during slow network operations)
- Builds conversation context and streams responses
- Parameters:
  - `query`: The user's question
  - `context`: Conversation history from G-Assist

##### Command: `on_input`
- Handles follow-up user input in passthrough/conversational mode
- Detects and saves API keys pasted by users
- Routes messages to `query_gemini` for processing

##### Helper: `stream_gemini_response()`
- Streams Gemini API responses with timeout handling
- Sends keepalives every 2 seconds to prevent engine timeout
- Categorizes and displays user-friendly error messages

### Configuration

#### API Key
- Stored in `gemini-api.key` file
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gemini-api.key`
- On first use, the plugin will prompt you to paste your API key in chat

#### Model Configuration
- Configured via `config.json`
- Default model: `gemini-2.5-flash`
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\config.json`

### Logging
- Log file location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gassist_sdk.log`
- Log level: DEBUG
- Format: `%(asctime)s [%(levelname)s] %(name)s: %(message)s`

### Error Handling
- Comprehensive error handling for Gemini API calls
- Categorized error messages (rate limits, timeouts, permissions, safety filters)
- Background keepalives prevent engine timeout during slow operations
- Detailed error logging for debugging

### Message Format Conversion
The plugin handles conversion between different message formats:
- OpenAI-style chat history to Gemini format
- Handles role mapping (assistant → model, user → user)
- Preserves conversation context and parts

### Adding New Features
To add new features:
1. Register a new command using the decorator:
   ```python
   @plugin.command("new_command")
   def new_command(param: str, context: Context = None):
       plugin.stream("Processing...")
       # Your implementation
       return "Result message"
   ```
2. Add the function to the `functions` list in `manifest.json`:
   ```json
   {
      "name": "new_command",
      "description": "Description of what the command does",
      "tags": ["relevant", "tags"],
      "properties": {
         "param": {
            "type": "string",
            "description": "Description of the parameter"
         }
      }
   }
   ```
3. Test using the plugin emulator from `plugins/plugin-builder`:
   ```bash
   python -m plugin_emulator --plugin gemini --interactive
   ```
4. Run `setup.bat gemini --deploy` from the `plugins/examples` directory to build and deploy

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.


