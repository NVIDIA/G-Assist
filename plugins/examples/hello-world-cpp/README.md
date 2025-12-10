# Hello World G-Assist Plugin (C++)

A simple example plugin demonstrating the **G-Assist C++ SDK** and **JSON-RPC V2 protocol**.

## Features Demonstrated

| Feature | Command | Description |
|---------|---------|-------------|
| **Basic Command** | `say_hello` | Simple function that takes a parameter and returns a greeting |
| **Streaming Output** | `count_with_streaming` | Shows how to send partial results using `plugin.stream()` |
| **Passthrough Mode** | `start_conversation` | Multi-turn conversation with `set_keep_session(true)` |
| **Input Handling** | `on_input` | Handles follow-up messages in passthrough mode |

## Quick Start

### 1. Build with CMake

```batch
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022" -A x64
cmake --build . --config Release
```

The executable and manifest.json will be in `build/Release/`.

**Note:** CMake will automatically download nlohmann/json during configuration.

### Alternative: Command Line (MSVC)

```batch
cl /EHsc /std:c++17 /O2 /I..\..\sdk\cpp /I<path-to-nlohmann> plugin.cpp /Fe:g-assist-plugin-hello-world-cpp.exe
```

### 2. Deploy

Copy to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-cpp\
```

Files needed:
- `g-assist-plugin-hello-world-cpp.exe`
- `manifest.json`

## Project Structure

```
hello-world-cpp/
├── plugin.cpp           # Main plugin code
├── manifest.json        # Function definitions for LLM
├── CMakeLists.txt       # CMake build configuration
└── README.md            # This file

# SDK location (referenced by CMake):
plugins/sdk/cpp/
├── gassist_sdk.hpp      # G-Assist C++ SDK
└── README.md            # SDK documentation
```

**Note:** nlohmann/json is automatically downloaded by CMake during build.

## How It Works

### The C++ SDK Pattern

```cpp
#include <nlohmann/json.hpp>
#include "gassist_sdk.hpp"

using json = nlohmann::json;

int main() {
    gassist::Plugin plugin("my-plugin", "1.0.0", "Description");
    
    plugin.command("my_function", [&](const json& args) -> json {
        std::string param = args.value("param", "default");
        return "Result: " + param;
    });
    
    plugin.run();
    return 0;
}
```

### Streaming Responses

```cpp
plugin.command("long_operation", [&](const json& args) -> json {
    plugin.stream("Starting...\n");
    // do work
    plugin.stream("Done!\n");
    return "";  // All output was streamed
});
```

### Passthrough Mode

```cpp
plugin.command("start_chat", [&](const json& args) -> json {
    plugin.set_keep_session(true);
    return "Chat started!";
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

## Dependencies

- **nlohmann/json**: Download from https://github.com/nlohmann/json/releases
- **C++17**: Required for `std::filesystem` and structured bindings

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-cpp\hello-world-cpp.log
```

## License

Apache License 2.0

