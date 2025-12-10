# G-Assist Plugin SDK for C++

A single-header SDK for building G-Assist plugins in C++.

## Requirements

- C++17 or later
- [nlohmann/json](https://github.com/nlohmann/json) library

## Installation

1. Copy `gassist_sdk.hpp` to your project
2. Download `nlohmann/json.hpp` from https://github.com/nlohmann/json/releases

## Quick Start

```cpp
#include <nlohmann/json.hpp>
#include "gassist_sdk.hpp"

using json = nlohmann::json;

int main() {
    gassist::Plugin plugin("hello-world", "1.0.0", "A simple example plugin");
    
    // Register a command
    plugin.command("say_hello", [&](const json& args) -> json {
        std::string name = args.value("name", "World");
        return "Hello, " + name + "!";
    });
    
    // Register command with streaming
    plugin.command("count", [&](const json& args) -> json {
        int count_to = args.value("count_to", 5);
        
        for (int i = 1; i <= count_to; i++) {
            plugin.stream("Counting: " + std::to_string(i) + "\n");
        }
        
        return "Done counting!";
    });
    
    // Run the plugin
    plugin.run();
    return 0;
}
```

## Features

### Command Registration

```cpp
plugin.command("function_name", [&](const json& args) -> json {
    // Access arguments
    std::string param = args.value("param", "default");
    
    // Return result (string, number, object, etc.)
    return {{"result", "value"}};
});
```

### Streaming Output

```cpp
plugin.command("long_operation", [&](const json& args) -> json {
    plugin.stream("Starting...\n");
    // do work
    plugin.stream("50% complete...\n");
    // do more work
    plugin.stream("Done!\n");
    return "";
});
```

### Passthrough Mode

```cpp
plugin.command("start_chat", [&](const json& args) -> json {
    plugin.set_keep_session(true);
    return "Chat started! Type 'exit' to leave.";
});

plugin.command("on_input", [&](const json& args) -> json {
    std::string content = args.value("content", "");
    
    if (content == "exit") {
        plugin.set_keep_session(false);
        return "Goodbye!";
    }
    
    plugin.set_keep_session(true);
    return "You said: " + content;
});
```

## Building

### Visual Studio

1. Create a new Console Application project
2. Add `gassist_sdk.hpp` and `nlohmann/json.hpp` to your project
3. Set C++ Language Standard to C++17 or later
4. Build as Release x64

### CMake

```cmake
cmake_minimum_required(VERSION 3.15)
project(my_plugin)

set(CMAKE_CXX_STANDARD 17)

add_executable(my_plugin plugin.cpp)
target_include_directories(my_plugin PRIVATE ${CMAKE_SOURCE_DIR}/include)
```

### Command Line (MSVC)

```batch
cl /EHsc /std:c++17 /O2 plugin.cpp /Fe:g-assist-plugin-myplugin.exe
```

## Manifest File

Create `manifest.json` alongside your executable:

```json
{
    "manifestVersion": 1,
    "name": "my-plugin",
    "version": "1.0.0",
    "description": "My C++ plugin",
    "executable": "g-assist-plugin-myplugin.exe",
    "persistent": true,
    "protocol_version": "2.0",
    "functions": [
        {
            "name": "say_hello",
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

## Protocol

This SDK implements Protocol V2 (JSON-RPC 2.0) with length-prefixed framing.
See `PROTOCOL_V2.md` in the Python SDK for full protocol documentation.

