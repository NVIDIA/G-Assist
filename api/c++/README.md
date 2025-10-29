# RISE C++ Demo Client

A comprehensive C++ console application demonstrating how to use the RISE (Runtime Inference System Engine) API for **LLM (Large Language Model)** and **ASR (Automatic Speech Recognition)** streaming.

## 🎯 What This Demo Shows

- ✅ Registering RISE callbacks for asynchronous response handling
- ✅ Sending LLM text requests with real-time streaming responses
- ✅ Sending ASR audio chunks for speech recognition
- ✅ Thread-safe synchronization between requests and callbacks
- ✅ Interactive chat interface with streaming output
- ✅ Audio streaming for ASR demonstrations

## 📋 Prerequisites

### 1. Development Environment
- **Visual Studio 2022** (or Visual Studio 2019)
  - Desktop development with C++ workload
  - Windows 10 SDK
- **C++17 or later** compiler support

### 2. NVAPI Files

Download from the **official NVIDIA GitHub repository**: https://github.com/NVIDIA/nvapi

**Automated Download (Recommended):**
```powershell
cd G-Assist\api\c++
.\download_nvapi_files.ps1
```

This downloads all required files (8 headers + library) automatically.

**Manual Download:**
```powershell
cd G-Assist\api\c++
$base = "https://raw.githubusercontent.com/NVIDIA/nvapi/main"

# Download all 8 header files
Invoke-WebRequest -Uri "$base/nvapi.h" -OutFile "nvapi.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_common.h" -OutFile "nvapi_lite_common.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_salstart.h" -OutFile "nvapi_lite_salstart.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_salend.h" -OutFile "nvapi_lite_salend.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_sli.h" -OutFile "nvapi_lite_sli.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_d3dext.h" -OutFile "nvapi_lite_d3dext.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_stereo.h" -OutFile "nvapi_lite_stereo.h"
Invoke-WebRequest -Uri "$base/nvapi_lite_surround.h" -OutFile "nvapi_lite_surround.h"

# Download x64 library
Invoke-WebRequest -Uri "$base/amd64/nvapi64.lib" -OutFile "nvapi64.lib"
```

### 3. RISE Engine
- G-Assist / RISE engine must be installed and running on your system

## 🔧 Building the Project

### Visual Studio GUI

1. Open `rise_demo_client.sln` in Visual Studio
2. Ensure you're building for **x64** platform (not x86)
3. Select **Debug** or **Release** configuration
4. Press **F5** to build and run

### Command Line (MSBuild)

```batch
# Open Developer Command Prompt for VS 2022
cd G-Assist\api\c++

# Build Debug version
msbuild rise_demo_client.sln /p:Configuration=Debug /p:Platform=x64

# Build Release version
msbuild rise_demo_client.sln /p:Configuration=Release /p:Platform=x64
```

**Build Output:**
- Debug: `x64\Debug\rise_demo_client.exe`
- Release: `x64\Release\rise_demo_client.exe`

## 🚀 Running the Application

```batch
cd x64\Debug
rise_demo_client.exe
```

### Expected Output

```
╔═══════════════════════════════════════════════════════════════╗
║           RISE C++ Demo Client v1.0                           ║
║     Demonstrating LLM and ASR Streaming Capabilities          ║
╚═══════════════════════════════════════════════════════════════╝

=== Initializing RISE Client ===
[OK] NVAPI Initialized
[OK] Callback Registered
[WAITING] For RISE to become ready...
[RISE] System is READY!
[OK] RISE Client Initialized Successfully!

╔═══════════════════════════════════════════════════════════════╗
║              RISE C++ Demo Client - Main Menu                 ║
╚═══════════════════════════════════════════════════════════════╝

1. LLM Chat Demo (Interactive Streaming)
2. ASR Streaming Demo (Simulated Audio)
3. Show API Capabilities
4. Exit

Choice:
```

## 📖 Feature Demonstrations

### 1. LLM Chat Demo

Interactive chat with streaming AI responses. Type your questions and receive real-time token-by-token responses.

**Example:**
```
[YOU]: What is my GPU?

=== Sending LLM Request ===
Your GPU is an NVIDIA GeForce RTX 5090 with Driver version 572.83.

[COMPLETE] Response finished
```

Type "exit" to return to main menu.

### 2. ASR Streaming Demo

Streams audio chunks for speech recognition, showing interim transcriptions in real-time with a progress spinner.

**Features:**
- Real-time transcription display
- Progress spinner during processing
- Clean in-place updates
- Final transcription after all chunks

### 3. API Capabilities

Displays a comprehensive overview of RISE API features and content types.

## 🔑 Key API Functions

### Initialize RISE Client

```cpp
// Initialize NVAPI
NvAPI_Initialize();

// Register callback
NV_RISE_CALLBACK_SETTINGS_V1 callbackSettings = { 0 };
callbackSettings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
callbackSettings.callback = RiseCallbackHandler;
NvAPI_RegisterRiseCallback(&callbackSettings);

// Wait for READY signal
```

### Send LLM Request

```cpp
// Build JSON: {"prompt": "...", "context_assist": {}, "client_config": {}}
NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(requestSettings.content, jsonRequest.c_str(), jsonRequest.length());
requestSettings.completed = 1;  // Single request

NvAPI_RequestRise(&requestSettings);
```

### Send ASR Audio Chunk

```cpp
// Format: "CHUNK:<id>:<sample_rate>:<base64_data>"
std::string payload = "CHUNK:" + std::to_string(chunkId) + ":16000:" + audioBase64;

NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(requestSettings.content, payload.c_str(), payload.length());
requestSettings.completed = 0;  // More chunks coming

NvAPI_RequestRise(&requestSettings);
```

### Handle Callback

```cpp
void RiseCallbackHandler(NV_RISE_CALLBACK_DATA_V1* pData) {
    switch (pData->contentType) {
        case NV_RISE_CONTENT_TYPE_TEXT:
            // Handle LLM/ASR text response
            std::cout << pData->content << std::flush;
            if (pData->completed) {
                responseCompleteSemaphore.release();
            }
            break;
            
        case NV_RISE_CONTENT_TYPE_READY:
            systemReady = true;
            break;
    }
}
```

## 📊 Content Types

| Content Type | Value | Description |
|--------------|-------|-------------|
| `TEXT` | 1 | LLM chat, ASR transcriptions |
| `GRAPH` | 2 | Graphical/chart data |
| `PROGRESS_UPDATE` | 6 | Progress percentage |
| `READY` | 7 | System ready signal |

## 🎤 Real-World ASR Integration

For production use with actual audio:

1. **Capture Audio** from microphone using Windows Audio APIs (WASAPI, DirectSound)
2. **Convert to PCM** format (16-bit, 16kHz is common)
3. **Encode to Base64** for transmission
4. **Send Chunks** every 500ms - 1 second of audio
5. **Handle Interim Results** for real-time feedback
6. **Finalize with STOP** when user stops speaking

Example libraries for audio capture:
- **PortAudio** - Cross-platform audio I/O
- **RtAudio** - Real-time audio I/O
- **Windows WASAPI** - Native Windows audio

## 🐛 Troubleshooting

### Build Errors

**"Cannot open include file 'nvapi.h'"**
- Run `.\download_nvapi_files.ps1` to download all required files
- Verify files are in the project directory

**"Cannot open file 'nvapi64.lib'"**
- Ensure you're building for **x64** (not x86)
- Run the download script if library is missing

**"Unresolved external symbol NvAPI_..."**
- Verify you're linking against `nvapi64.lib`
- Check that the library architecture matches (x64)

### Runtime Errors

**"RISE is not ready" or hangs during initialization**
- Ensure G-Assist / RISE engine is installed and running
- Check Windows Services for NVIDIA services
- Restart the RISE service if needed

**Callbacks not firing**
- Ensure callback function signature matches exactly
- Check that the callback is registered before sending requests
- Verify thread-safety of callback code

## 📁 Project Structure

```
api/c++/
│
├── main.cpp                    # Main application with all demos
├── audio_utils.h               # Audio processing utilities
│
├── nvapi.h                     # NVAPI header (download via script)
├── nvapi_lite_*.h              # NVAPI supporting headers
├── nvapi64.lib                 # NVAPI library (download via script)
│
├── download_nvapi_files.ps1    # Automated NVAPI download script
│
├── rise_demo_client.sln        # Visual Studio solution
├── rise_demo_client.vcxproj    # Visual Studio project
│
├── README.md                   # This file
│
└── x64/
    ├── Debug/
    │   └── rise_demo_client.exe
    └── Release/
        └── rise_demo_client.exe
```

## 🔗 Related Projects

- **Python Binding** (`G-Assist/api/bindings/python/`): Python wrapper for RISE API
- **Plugin Examples** (`G-Assist/plugins/examples/`): Example plugins for G-Assist

## 💡 Development Tips

1. **Start Simple**: Run the LLM demo first to verify basic connectivity
2. **Check Callbacks**: Add logging to callback handler to see all events
3. **Use Debug Build**: Easier to step through and understand flow
4. **Monitor Threads**: Use Visual Studio's thread window to track async behavior
5. **Test Incrementally**: Build one feature at a time

## 🚀 Next Steps

After running this demo, you can:

1. **Integrate Real Audio**: Replace simulated chunks with actual microphone input
2. **Add GUI**: Create a Windows Forms or Qt-based interface
3. **Add Configuration**: Support custom prompts, assistant identifiers
4. **Add Error Recovery**: Retry logic, timeout handling
5. **Profile Performance**: Measure latency, throughput

## 📄 License

This project follows the same license as the parent G-Assist project.

---

**Happy Coding!** 🎉

For questions or issues, please refer to the main G-Assist documentation.
