# Hello World G-Assist Plugin (Node.js)

A simple example plugin demonstrating the **G-Assist Node.js SDK** and **JSON-RPC V2 protocol**.

## Features Demonstrated

| Feature | Command | Description |
|---------|---------|-------------|
| **Basic Command** | `say_hello` | Simple function that takes a parameter and returns a greeting |
| **Streaming Output** | `count_with_streaming` | Shows how to send partial results using `plugin.stream()` |
| **Passthrough Mode** | `start_conversation` | Multi-turn conversation with `setKeepSession(true)` |
| **Input Handling** | `on_input` | Handles follow-up messages in passthrough mode |

## Quick Start

### 1. Setup

From the `plugins/examples` directory, run:
```bash
setup.bat hello-world-nodejs
```

This copies the Node.js SDK to `libs/gassist-sdk.js`.

### 2. Deploy

Deploy using the setup script:
```bash
setup.bat hello-world-nodejs -deploy
```

Or manually copy the following files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-nodejs`:
- `plugin.js`
- `manifest.json`
- `launch.bat`
- `libs/gassist-sdk.js`

### 3. Test with Plugin Emulator

Test your deployed plugin using the emulator:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the hello-world-nodejs plugin from the interactive menu to test the commands.

## Project Structure

```
hello-world-nodejs/
├── plugin.js           # Main plugin code
├── manifest.json       # Function definitions for LLM
├── launch.bat          # Wrapper script to launch Node.js plugin
├── package.json        # npm package info
├── libs/               # Dependencies (created by setup.bat)
│   └── gassist-sdk.js  # G-Assist Node.js SDK
└── README.md           # This file

# SDK location (copied by setup.bat):
plugins/sdk/nodejs/
├── gassist-sdk.js      # G-Assist Node.js SDK
└── README.md           # SDK documentation
```

**Note:** The `launch.bat` wrapper is required because the engine launches plugins as executables. The batch file calls `node plugin.js` to run the Node.js plugin.

## How It Works

### The Node.js SDK Pattern

```javascript
const { Plugin } = require('./libs/gassist-sdk');

const plugin = new Plugin('my-plugin', '1.0.0', 'Description');

plugin.command('my_function', (args) => {
    const param = args.param || 'default';
    return `Result: ${param}`;
});

plugin.run();
```

### Async Commands

```javascript
plugin.command('fetch_data', async (args) => {
    const response = await fetch(args.url);
    return await response.json();
});
```

### Streaming Responses

```javascript
plugin.command('long_operation', async (args) => {
    plugin.stream('Starting...\n');
    await doWork();
    plugin.stream('Done!\n');
    return '';  // All output was streamed
});
```

### Passthrough Mode

```javascript
plugin.command('start_chat', (args) => {
    plugin.setKeepSession(true);
    return 'Chat started!';
});

plugin.command('on_input', (args) => {
    const content = args.content;
    
    if (content.toLowerCase() === 'exit') {
        plugin.setKeepSession(false);
        return 'Goodbye!';
    }
    
    plugin.setKeepSession(true);
    return `You said: ${content}`;
});
```

## Requirements

- Node.js 14.0 or later

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-nodejs\hello-world-nodejs.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot find module './libs/gassist-sdk'" | Run `setup.bat hello-world-nodejs` from examples folder |
| Commands not recognized | Ensure `manifest.json` function names match `plugin.command()` names |
| Plugin not responding | Check the log file for errors |
| Node.js not found | Ensure Node.js is installed and in PATH |

## License

Apache License 2.0
