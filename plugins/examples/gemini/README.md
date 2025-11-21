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

### Step 3: Configure Your API Key
1. Create a file named `gemini.key` in the root directory
2. Add your API key to the file:
```gemini.key
your_api_key_here
```

### Step 4: Configure the Model (Optional)
Adjust `config.json` to your needs:
```json
{
  "model": "gemini-2.0-flash"
}
```

### Step 5: Build the Plugin
```bash
build.bat
```
This will create a `dist\google` folder containing all the required files for the plugin.


### Step 6: Install the Plugin
1. Create a new folder here (if it doesn't exist):
   ```
   %PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini
   ```
   💡 **Tip**: Copy and paste this path into File Explorer's address bar!

2. Copy these files to the folder you just created:
   - `gemini-plugin.exe` (from the `dist` folder)
   - `manifest.json`
   - `config.json`
   - `gemini.key`

## How to Use
Once installed, you can use Gemini through G-Assist! Try these examples:

### Basic Text Generation
- Hey Google, tell me about artificial intelligence.
- /google Explain ray tracing using a real-world analogy in one sentence. ELI5

### Search
- Hey Google, what's the weather in Santa Clara, CA?
- /google What are the top five features in the latest major patch of RUST?

## Limitations
- Requires active internet connection
- Subject to Google's API rate limits
- Image generation not supported
- Must be used within G-Assist environment

### Logging
The plugin logs all activity to:
```
%USERPROFILE%\gemini.log
```
Check this file for detailed error messages and debugging information.

## Troubleshooting Tips
- **API Key Not Working?** Verify your API key is correctly copied to `gemini.key`
- **Commands Not Working?** Ensure all files are in the correct plugin directory
- **Unexpected Responses?** Check the configuration in `config.json`
- **Logs**: Check `%USERPROFILE%\gemini.log` for detailed logs

## Developer Documentation

### Architecture Overview
The Gemini plugin is implemented as a Python-based service that communicates with G-Assist through a pipe-based protocol. The plugin handles two main types of queries:
1. Search-based queries using Google Search integration
2. LLM-based queries using Gemini's language model capabilities

### Core Components

#### Communication Protocol
- Uses Windows named pipes for IPC (Inter-Process Communication)
- Commands are sent as JSON messages with the following structure:
  ```json
  {
    "tool_calls": [{
      "func": "command_name",
      "properties": {},
      "messages": [],
      "system_info": ""
    }]
  }
  ```
- Responses are returned as JSON with success/failure status and optional messages

#### Key Functions

##### Main Entry Point (`main()`)
- Initializes the plugin and enters command processing loop
- Handles command routing and response generation
- Supports commands: `initialize`, `shutdown`, `query_gemini`

##### Query Processing (`execute_query_gemini_command()`)
- Processes incoming queries through a classification step
- Routes queries to either search or LLM path based on content
- Handles streaming responses back to the client
- Parameters:
  - `params`: Additional query parameters
  - `context`: Conversation history
  - `system_info`: System information including game data

##### LLM Query Handler (`execute_llm_query()`)
- Processes knowledge-based queries using Gemini
- Augments prompts with system context
- Streams responses back to client
- Parameters:
  - `gemini_history`: Conversation history in Gemini format
  - `incoming_context`: Original conversation context
  - `system_info`: System information including game data

### Configuration

#### API Key
- Stored in `google.key` file
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\google\google.key`

#### Model Configuration
- Configured via `config.json`
- Default model: `gemini-pro`
- Location: `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\google\config.json`

### Logging
- Log file location: `%USERPROFILE%\gemini.log`
- Log level: INFO
- Format: `%(asctime)s - %(levelname)s - %(message)s`

### Error Handling
- Comprehensive error handling for API calls
- Fallback mechanisms (e.g., search to LLM fallback)
- Detailed error logging with stack traces
- User-friendly error messages

### Message Format Conversion
The plugin handles conversion between different message formats:
- OpenAI-style chat history to Gemini format
- Handles role mapping (assistant → model, user → user)
- Preserves conversation context and parts

### Adding New Features
To add new features:
1. Add new command to the `commands` dictionary in `main()`
2. Implement corresponding execute function
3. Implement proper error handling and logging
4. Add the function to the `functions` list in `manifest.json` file: 
   ```json
   {
      "name": "new_command",
      "description": "Description of what the command does",
      "tags": ["relevant", "tags"],
      "properties": {
      "parameter_name": {
         "type": "string",
         "description": "Description of the parameter"
      }
      }
   }
   ```
5. Manually test the function:

   First, run the script:
   ``` bash
   python plugin.py
   ```

   Run the initialize command: 
      ``` json
      {
         "tool_calls" : "initialize"
      }
      ```
   Run the new command:
      ``` json
      {
         "tool_calls" : "new_command", 
         "params": {
            "parameter_name": "parameter_value"
         }
      }
      ```
6. Run the setup & build scripts as outlined above, install the plugin by placing the files in the proper location and test your updated plugin. Use variations of standard user messages to make sure the function is adequately documented in the `manifest.json`

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.


