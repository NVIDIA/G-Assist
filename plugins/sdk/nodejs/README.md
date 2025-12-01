# G-Assist Plugin SDK for Node.js

A simple SDK for building G-Assist plugins in Node.js.

## Requirements

- Node.js 14.0 or later

## Installation

Copy `gassist-sdk.js` to your plugin folder, or:

```bash
npm install ./path/to/sdk/nodejs
```

## Quick Start

```javascript
const { Plugin } = require('./gassist-sdk');

const plugin = new Plugin('my-plugin', '1.0.0', 'My awesome plugin');

// Register a command
plugin.command('greet', (args) => {
    const name = args.name || 'World';
    return `Hello, ${name}!`;
});

// Run the plugin
plugin.run();
```

## Features

### Command Registration

```javascript
plugin.command('function_name', (args) => {
    // Access arguments
    const param = args.param || 'default';
    
    // Return result (string, object, etc.)
    return { result: 'value' };
});
```

### Async Commands

```javascript
plugin.command('fetch_data', async (args) => {
    const response = await fetch(args.url);
    const data = await response.json();
    return data;
});
```

### Streaming Output

```javascript
plugin.command('long_operation', (args) => {
    plugin.stream('Starting...\n');
    // do work
    plugin.stream('50% complete...\n');
    // do more work
    plugin.stream('Done!\n');
    return '';  // All output was streamed
});
```

### Passthrough Mode

```javascript
plugin.command('start_chat', (args) => {
    plugin.setKeepSession(true);
    return 'Chat started! Type "exit" to leave.';
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

## Running Your Plugin

```bash
node plugin.js
```

## Manifest File

Create `manifest.json` alongside your plugin:

```json
{
    "manifestVersion": 1,
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "My Node.js plugin",
    "executable": "node plugin.js",
    "persistent": true,
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "greet",
            "description": "Greet the user",
            "tags": ["hello", "greet"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name to greet"
                }
            }
        }
    ]
}
```

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\<plugin-name>\<plugin-name>.log
```

## API Reference

### Plugin Class

```javascript
const plugin = new Plugin(name, version, description);
```

#### Methods

- `plugin.command(name, handler)` - Register a command handler
- `plugin.stream(data)` - Send streaming data
- `plugin.setKeepSession(keep)` - Set passthrough mode
- `plugin.log(message)` - Write to log file
- `plugin.run()` - Start the plugin main loop

## Protocol

This SDK implements Protocol V2 (JSON-RPC 2.0) with length-prefixed framing.
See `PROTOCOL_V2.md` in the Python SDK for full protocol documentation.

