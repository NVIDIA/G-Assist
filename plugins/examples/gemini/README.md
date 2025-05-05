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

### Step 5: Build It
```bash
pyinstaller --name gemini-plugin plugin.py
```

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

## Limitations
- Requires active internet connection
- Subject to Google's API rate limits
- Image generation not supported
- Must be used within G-Assist environment

## Troubleshooting Tips
- **API Key Not Working?** Verify your API key is correctly copied to `gemini.key`
- **Connection Issues?** Check your internet connection
- **Commands Not Working?** Ensure all files are in the correct plugin directory
- **Unexpected Responses?** Check the configuration in `config.json`

## Want to Contribute?
We'd love your help making this plugin even better! Check out [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments
We use some amazing open-source software to make this work. See [ATTRIBUTIONS.md](ATTRIBUTIONS.md) for the full list.

## Need Help?
If you run into issues:
1. Verify your API key is valid
2. Check that G-Assist is running
3. Ensure all plugin files are in the correct location
4. Try restarting G-Assist
