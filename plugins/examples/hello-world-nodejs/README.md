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

Copy the SDK from the central location:
```batch
copy ..\..\sdk\nodejs\gassist-sdk.js .
```

### 2. Deploy

Copy this folder to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-nodejs\
```

Files needed:
- `plugin.js`
- `manifest.json`
- `launch.bat`
- `gassist-sdk.js` (copy from `plugins/sdk/nodejs/`)

## Project Structure

```
hello-world-nodejs/
├── plugin.js           # Main plugin code
├── manifest.json       # Function definitions for LLM
├── launch.bat          # Wrapper script to launch Node.js plugin
├── package.json        # npm package info
└── README.md           # This file

# SDK location (copy to plugin folder for deployment):
plugins/sdk/nodejs/
├── gassist-sdk.js      # G-Assist Node.js SDK
└── README.md           # SDK documentation
```

**Note:** The `launch.bat` wrapper is required because the engine launches plugins as executables. The batch file calls `node plugin.js` to run the Node.js plugin.

For deployment, copy `gassist-sdk.js` from `plugins/sdk/nodejs/` to your plugin folder.

## How It Works

### The Node.js SDK Pattern

```javascript
const { Plugin } = require('./gassist-sdk');

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

## License

Apache License 2.0

