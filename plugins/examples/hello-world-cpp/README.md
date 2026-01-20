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

### 1. Setup

From the `plugins/examples` directory, run:
```bash
setup.bat hello-world-cpp
```

This copies the C++ SDK header to `libs/include/`.

### 2. Build with CMake

```bash
cd hello-world-cpp
mkdir build
cd build
cmake .. -G "Visual Studio 17 2022" -A x64
cmake --build . --config Release
```

The executable and manifest.json will be in `build/Release/`.

**Note:** CMake will automatically download nlohmann/json during configuration.

### Alternative: Command Line (MSVC)

```bash
cl /EHsc /std:c++17 /O2 /Ilibs/include plugin.cpp /Fe:g-assist-plugin-hello-world-cpp.exe
```

### 3. Deploy

Deploy using the setup script:
```bash
setup.bat hello-world-cpp -deploy
```

Or manually copy the following files to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-cpp`:
- `g-assist-plugin-hello-world-cpp.exe` (from `build/Release/`)
- `manifest.json`

### 4. Test with Plugin Emulator

Test your deployed plugin using the emulator:
```bash
cd plugins/plugin_emulator
pip install -r requirements.txt
python -m plugin_emulator -d "C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins"
```
Select the hello-world-cpp plugin from the interactive menu to test the commands.

## Project Structure

```
hello-world-cpp/
├── plugin.cpp           # Main plugin code
├── manifest.json        # Function definitions for LLM
├── CMakeLists.txt       # CMake build configuration
├── libs/                # Dependencies (created by setup.bat)
│   └── include/
│       └── gassist_sdk.hpp
└── README.md            # This file

# SDK location (referenced by CMake):
plugins/sdk/cpp/
├── gassist_sdk.hpp      # G-Assist C++ SDK (includes nlohmann/json)
└── README.md            # SDK documentation
```

## How It Works

### The C++ SDK Pattern

```cpp
#include "gassist_sdk.hpp"

using gassist::json;

int main() {
    gassist::Plugin plugin("my-plugin", "1.0.0", "Description");
    
    plugin.command("my_function", [&](const json& args) -> json {
        std::string param = args.value("param", "default");
        return json("Result: " + param);
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
    return json("");  // All output was streamed
});
```

### Passthrough Mode

```cpp
plugin.command("start_chat", [&](const json& args) -> json {
    plugin.set_keep_session(true);
    return json("Chat started!");
});

plugin.command("on_input", [&](const json& args) -> json {
    std::string content = args.value("content", "");
    
    if (content == "exit") {
        plugin.set_keep_session(false);
        return json("Goodbye!");
    }
    
    plugin.set_keep_session(true);
    return json("You said: " + content);
});
```

## Dependencies

- **nlohmann/json**: Automatically downloaded by CMake during build (no manual download needed)
- **C++17**: Required for structured bindings and modern features

## Logs

Plugin logs are written to:
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\hello-world-cpp\hello-world-cpp.log
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Cannot find gassist_sdk.hpp" | Run `setup.bat hello-world-cpp` from examples folder |
| CMake errors about nlohmann/json | Ensure internet connection for FetchContent download |
| Commands not recognized | Ensure `manifest.json` function names match command registrations |
| Plugin not responding | Check the log file for errors |

## License

Apache License 2.0
