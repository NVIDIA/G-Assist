# RISE C++ API Documentation

Complete documentation for the RISE (Runtime Inference System Engine) C++ interface, including LLM (Large Language Model) and ASR (Automatic Speech Recognition) streaming capabilities.

---

## Table of Contents

- [Quick Start](#quick-start)
  - [What This Demo Shows](#what-this-demo-shows)
  - [Prerequisites](#prerequisites)
  - [Building the Project](#building-the-project)
  - [Running the Application](#running-the-application)
- [Architecture Overview](#architecture-overview)
  - [Core Principles](#core-principles)
  - [Threading Model](#threading-model)
- [Integration Guide](#integration-guide)
  - [Step 1: Project Setup](#step-1-project-setup)
  - [Step 2: Implement Callback Architecture](#step-2-implement-callback-architecture)
  - [Step 3: Initialization Flow](#step-3-initialization-flow)
  - [Step 4: Cleanup](#step-4-cleanup)
- [API Reference](#api-reference)
  - [Core Functions](#core-functions)
  - [Structures](#structures)
  - [Content Types](#content-types)
  - [Error Codes](#error-codes)
  - [Constants and Limits](#constants-and-limits)
- [Request Formats](#request-formats)
  - [LLM Request Format](#llm-request-format)
  - [ASR Audio Chunk Format](#asr-audio-chunk-format)
  - [ASR Stop Signal](#asr-stop-signal)
- [Response Formats](#response-formats)
  - [LLM Text Response](#llm-text-response)
  - [ASR Transcription Response](#asr-transcription-response)
  - [Progress Update Response](#progress-update-response)
- [Code Examples](#code-examples)
  - [Complete LLM Request Example](#complete-llm-request-example)
  - [Live Microphone Capture for ASR](#live-microphone-capture-for-asr)
- [Common Integration Scenarios](#common-integration-scenarios)
- [Thread Safety](#thread-safety)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)
- [Troubleshooting](#troubleshooting)
- [Project Structure](#project-structure)

---

## Quick Start

### What This Demo Shows

- Registering RISE callbacks for asynchronous response handling
- Sending LLM text requests with real-time streaming responses
- Sending ASR audio chunks for speech recognition (WAV file and live microphone)
- Thread-safe synchronization between requests and callbacks
- Interactive chat interface with streaming output

### Prerequisites

#### 1. Development Environment
- **Visual Studio 2022** (or Visual Studio 2019)
  - Desktop development with C++ workload
  - Windows 10 SDK
- **C++17 or later** compiler support

#### 2. NVAPI Files

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

#### 3. RISE Engine
- G-Assist / RISE engine must be installed and running on your system

### Building the Project

#### Visual Studio GUI

1. Open `rise_demo_client.sln` in Visual Studio
2. Ensure you're building for **x64** platform (not x86)
3. Select **Debug** or **Release** configuration
4. Press **F5** to build and run

#### Command Line (MSBuild)

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

### Running the Application

```batch
cd x64\Debug
rise_demo_client.exe
```

**Expected Output:**

```
===============================================================
           RISE C++ Demo Client v1.0                          
     Demonstrating LLM and ASR Streaming Capabilities         
===============================================================

=== Initializing RISE Client ===
[OK] NVAPI Initialized
[OK] Callback Registered
[WAITING] For RISE to become ready...
[RISE] System is READY!
[OK] RISE Client Initialized Successfully!

===============================================================
              RISE C++ Demo Client - Main Menu                
===============================================================

1. LLM Chat Demo (Interactive Streaming)
2. ASR Streaming Demo (WAV File)
3. ASR Streaming Demo (Live Microphone)
4. Exit

Choice:
```

---

## Architecture Overview

RISE uses an **asynchronous callback-based architecture**:

```
Your Application          RISE Engine
     │                         │
     ├─ Initialize ────────────>│
     │                         │
     │<────── READY Signal ─────┤
     │                         │
     ├─ Send Request ──────────>│
     │                         │
     │<────── Stream Token 1 ───┤
     │<────── Stream Token 2 ───┤
     │<────── Stream Token N ───┤
     │<────── COMPLETE ─────────┤
     │                         │
```

**Key Concept**: You send requests via function calls, but receive responses asynchronously through callbacks that run on a separate thread.

### Core Principles

1. **Asynchronous Communication**: Requests are non-blocking; responses arrive via callbacks
2. **Streaming Support**: Both LLM and ASR support real-time streaming of partial results
3. **Thread Safety Required**: Callbacks run on RISE-managed threads; you must protect shared state
4. **Single Initialization**: Initialize once, send many requests (connection pooling)

### Threading Model

**What Runs Where:**
- **Your callback**: RISE-managed thread (not your control)
- **`NvAPI_RequestRise()`**: Your thread (typically main)
- **UI updates**: Must marshal to UI thread (platform-specific)

---

## Integration Guide

### Step 1: Project Setup

**Requirements:**
- Add `nvapi.h` header and link against `nvapi64.lib`
- Build for **x64** platform only (x86 not supported)
- Requires C++17 or later (C++20 recommended for `std::semaphore`)

**Visual Studio Project Settings:**
- Platform: x64
- Additional Include Directories: Path to `nvapi.h`
- Additional Library Directories: Path to `nvapi64.lib`
- Linker Input: Add `nvapi64.lib`

### Step 2: Implement Callback Architecture

Your callback handler is the **central communication hub**:

**Key Characteristics:**
- Runs on a **separate thread** managed by RISE
- Must handle multiple content types: `READY`, `TEXT`, `PROGRESS_UPDATE`, `GRAPH`
- Requires **thread-safe** access to shared state (use mutexes/atomics)
- Should be **lightweight** - defer heavy processing to your main thread

**Critical**: The callback signature must be `void __cdecl FunctionName(NV_RISE_CALLBACK_DATA_V1* pData)`

**Example Callback Structure:**

```cpp
void MyRiseCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (!pData) return;
    
    switch (pData->contentType) {
        case NV_RISE_CONTENT_TYPE_READY:
            // RISE system is ready
            systemReady = true;
            break;
            
        case NV_RISE_CONTENT_TYPE_TEXT:
            // LLM response or ASR transcription
            ProcessTextResponse(pData->content, pData->completed);
            break;
            
        case NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE:
            // Progress percentage (0-100)
            UpdateProgress(std::stoi(pData->content));
            break;
            
        case NV_RISE_CONTENT_TYPE_GRAPH:
            // Structured data for charts
            ProcessGraphData(pData->content);
            break;
    }
}
```

### Step 3: Initialization Flow

**Initialization Sequence:**

```
1. NvAPI_Initialize()
2. NvAPI_RegisterRiseCallback() 
3. Wait for NV_RISE_CONTENT_TYPE_READY signal
4. Begin accepting user input/requests
```

**Implementation Pattern:**

```cpp
bool InitializeRise() {
    // 1. Initialize NVAPI
    NvAPI_Status status = NvAPI_Initialize();
    if (status != NVAPI_OK) {
        return false;
    }
    
    // 2. Register callback
    NV_RISE_CALLBACK_SETTINGS_V1 settings = { 0 };
    settings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
    settings.callback = MyRiseCallback;
    
    status = NvAPI_RegisterRiseCallback(&settings);
    if (status != NVAPI_OK) {
        return false;
    }
    
    // 3. Wait for READY signal
    while (!systemReady) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    
    return true;
}
```

**Important**: You must wait for the `READY` signal before sending any requests.

### Step 4: Cleanup

Always clean up before exiting:

```cpp
void ShutdownRise() {
    NvAPI_Unload();
}
```

Ensure no requests are in-flight during shutdown.

---

## API Reference

### Core Functions

#### NvAPI_Initialize()

Initializes the NVAPI library. Must be called before any other NVAPI functions.

```cpp
NvAPI_Status NvAPI_Initialize();
```

**Returns:**
- `NVAPI_OK` - Success
- `NVAPI_ERROR` - Initialization failed

**Notes:**
- Call once at application startup
- Must be called before registering callbacks or sending requests
- Thread-safe

---

#### NvAPI_RegisterRiseCallback()

Registers a callback function to receive asynchronous responses from the RISE engine.

```cpp
NvAPI_Status NvAPI_RegisterRiseCallback(NV_RISE_CALLBACK_SETTINGS_V1* pCallbackSettings);
```

**Parameters:**
- `pCallbackSettings` - Pointer to callback settings structure

**Returns:**
- `NVAPI_OK` - Callback registered successfully
- `NVAPI_INVALID_ARGUMENT` - NULL or invalid settings
- `NVAPI_ERROR` - Registration failed

**Notes:**
- Must be called after `NvAPI_Initialize()`
- Callback runs on RISE-managed thread
- Only one callback can be registered per application
- Wait for `NV_RISE_CONTENT_TYPE_READY` before sending requests

---

#### NvAPI_RequestRise()

Sends a request to the RISE engine (LLM text or ASR audio).

```cpp
NvAPI_Status NvAPI_RequestRise(NV_REQUEST_RISE_SETTINGS_V1* pRequestSettings);
```

**Parameters:**
- `pRequestSettings` - Pointer to request settings structure

**Returns:**
- `NVAPI_OK` - Request sent successfully
- `NVAPI_INVALID_ARGUMENT` - NULL or invalid settings
- `NVAPI_NOT_SUPPORTED` - RISE not available
- `NVAPI_ERROR` - Request failed

**Notes:**
- Can only be called after receiving `READY` signal
- Non-blocking - responses arrive via callback
- Thread-safe
- Maximum content size: 4096 bytes

---

#### NvAPI_Unload()

Unloads the NVAPI library and cleans up resources.

```cpp
NvAPI_Status NvAPI_Unload();
```

**Notes:**
- Call at application shutdown
- Ensure no requests are in-flight
- Callback will no longer be invoked after this call
- Thread-safe

---

### Structures

#### NV_RISE_CALLBACK_SETTINGS_V1

Settings structure for registering a callback handler.

```cpp
typedef struct _NV_RISE_CALLBACK_SETTINGS_V1 {
    NvU32 version;                                  // Structure version
    NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1 super;    // Callback parameter (internal)
    NV_RISE_CALLBACK_V1 callback;                   // Callback function pointer
    NvU8 reserved[32];                              // Reserved (set to zero)
} NV_RISE_CALLBACK_SETTINGS_V1;
```

**Key Fields:**
- `version` - Must be `NV_RISE_CALLBACK_SETTINGS_VER1`
- `callback` - Function pointer matching signature: `void __cdecl MyCallback(NV_RISE_CALLBACK_DATA_V1* pData)`

**Note:** When you initialize the structure with `{ 0 }`, all fields including `super` and `reserved` are automatically zeroed.

---

#### NV_RISE_CALLBACK_DATA_V1

Data structure passed to callback function containing response information.

```cpp
typedef struct _NV_RISE_CALLBACK_DATA_V1 {
    NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1 super;    // Parent structure (internal)
    NV_RISE_CONTENT_TYPE contentType;              // Type of content
    NvAPI_String content;                          // Response data (char[4096])
    NvBool completed;                              // Is this the final chunk?
} NV_RISE_CALLBACK_DATA_V1;
```

**Key Fields:**
- `contentType` - Type of response (see [Content Types](#content-types))
- `content` - Response data as null-terminated string (4096 bytes max)
- `completed` - `1` if final response, `0` if more data coming

---

#### NV_REQUEST_RISE_SETTINGS_V1

Settings structure for sending requests to RISE.

```cpp
typedef struct _NV_REQUEST_RISE_SETTINGS_V1 {
    NvU32 version;                      // Structure version
    NV_RISE_CONTENT_TYPE contentType;   // Type of request
    NvAPI_String content;               // Request data (char[4096])
    NvBool completed;                   // Is this the final chunk?
    NvU8 reserved[32];                  // Reserved (set to zero)
} NV_REQUEST_RISE_SETTINGS_V1;
```

**Key Fields:**
- `version` - Must be `NV_REQUEST_RISE_SETTINGS_VER1`
- `contentType` - Type of content being sent (typically `NV_RISE_CONTENT_TYPE_TEXT`)
- `content` - Request payload (JSON for LLM, formatted string for ASR, max 4096 bytes)
- `completed` - `1` for single request or final chunk, `0` for ongoing streaming

---

### Content Types

#### NV_RISE_CONTENT_TYPE Enumeration

| Type | Value | Direction | Description |
|------|-------|-----------|-------------|
| `NV_RISE_CONTENT_TYPE_TEXT` | 1 | Both | LLM responses, ASR transcriptions, text requests |
| `NV_RISE_CONTENT_TYPE_GRAPH` | 2 | Callback | Graphical or chart data |
| `NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE` | 6 | Callback | Progress percentage (0-100) |
| `NV_RISE_CONTENT_TYPE_READY` | 7 | Callback | System ready signal |

---

### Error Codes

#### NvAPI_Status Values

| Code | Value | Meaning |
|------|-------|---------|
| `NVAPI_OK` | 0 | Success |
| `NVAPI_ERROR` | -1 | Generic error |
| `NVAPI_LIBRARY_NOT_FOUND` | -2 | NVAPI library not found |
| `NVAPI_NO_IMPLEMENTATION` | -3 | Function not implemented |
| `NVAPI_API_NOT_INITIALIZED` | -4 | `NvAPI_Initialize()` not called |
| `NVAPI_INVALID_ARGUMENT` | -5 | Invalid parameter passed |
| `NVAPI_NVIDIA_DEVICE_NOT_FOUND` | -6 | No NVIDIA GPU found |
| `NVAPI_END_ENUMERATION` | -7 | No more items to enumerate |
| `NVAPI_INVALID_HANDLE` | -8 | Invalid handle |
| `NVAPI_INCOMPATIBLE_STRUCT_VERSION` | -9 | Struct version mismatch |
| `NVAPI_HANDLE_INVALIDATED` | -10 | Handle no longer valid |
| `NVAPI_NOT_SUPPORTED` | -11 | Feature not supported |

---

### Constants and Limits

#### Version Constants

```cpp
#define NV_RISE_CALLBACK_SETTINGS_VER1  MAKE_NVAPI_VERSION(NV_RISE_CALLBACK_SETTINGS_V1, 1)
#define NV_REQUEST_RISE_SETTINGS_VER1   MAKE_NVAPI_VERSION(NV_REQUEST_RISE_SETTINGS_V1, 1)
```

#### Size Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Max Request Content | 4096 bytes | Total size including format strings |
| Max Response Content | 4096 bytes | Per callback invocation |
| Max Callback Count | Unlimited | Responses can span multiple callbacks |

#### Timing Recommendations

| Operation | Typical Duration |
|-----------|-----------------|
| Wait for READY | Immediate (waits until ready) |
| LLM Request Response | Varies (streaming) |
| ASR Chunk Processing | ~100-500ms per chunk |
| Callback Execution | <1 millisecond |

#### Audio Specifications

| Parameter | Recommended | Supported Range |
|-----------|------------|-----------------|
| Sample Rate | 16 kHz | Any (engine resamples) |
| Bit Depth | 16-bit | 16-bit only |
| Channels | Mono | Mono only |
| Chunk Duration | 500ms - 1s | Any |
| Audio Format | PCM | PCM only |

---

## Request Formats

### LLM Request Format

**Content Type:** `NV_RISE_CONTENT_TYPE_TEXT`  
**Format:** JSON string  
**Completed Field:** `1` (single request)

**JSON Structure:**
```json
{
  "prompt": "user question or instruction",
  "context_assist": {},
  "client_config": {
    "assistant_identifier": "your_application_name",
    "enable_streaming": true
  }
}
```

**Field Descriptions:**
- `prompt` - User's input text or question
- `context_assist` - Optional context object (system info, plugins, etc.)
- `client_config.assistant_identifier` - Your application name (for logging/routing)
- `client_config.enable_streaming` - Enable token-by-token streaming (recommended: `true`)

**Example:**
```cpp
std::string json = R"({
    "prompt": "What is my GPU?",
    "context_assist": {},
    "client_config": {
        "assistant_identifier": "my_app",
        "enable_streaming": true
    }
})";

NV_REQUEST_RISE_SETTINGS_V1 request = { 0 };
request.version = NV_REQUEST_RISE_SETTINGS_VER1;
request.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(request.content, json.c_str(), json.length());
request.completed = 1;

NvAPI_RequestRise(&request);
```

---

### ASR Audio Chunk Format

**Content Type:** `NV_RISE_CONTENT_TYPE_TEXT`  
**Format:** `"CHUNK:<id>:<sample_rate>:<base64_audio>"`  
**Completed Field:** `0` (ongoing) or `1` (final chunk)

**Format Breakdown:**
- `CHUNK:` - Literal prefix
- `<id>` - Sequential chunk identifier (0, 1, 2, ...)
- `<sample_rate>` - Audio sample rate in Hz (e.g., 16000)
- `<base64_audio>` - Base64-encoded audio data

**Audio Format:**
- **Encoding:** 16-bit PCM (converted to float32 for transmission)
- **Sample Rate:** Any (16kHz recommended, engine will resample)
- **Channels:** Mono
- **Byte Order:** Little-endian

**Example:**
```cpp
// Encode audio to Base64
std::string audioBase64 = Base64Encode(audioData);

// Build payload
std::string payload = "CHUNK:" + 
                     std::to_string(chunkId) + ":" + 
                     std::to_string(16000) + ":" + 
                     audioBase64;

NV_REQUEST_RISE_SETTINGS_V1 request = { 0 };
request.version = NV_REQUEST_RISE_SETTINGS_VER1;
request.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(request.content, payload.c_str(), payload.length());
request.completed = 0;  // More chunks coming

NvAPI_RequestRise(&request);
```

---

### ASR Stop Signal

To finalize ASR transcription:

**Content Type:** `NV_RISE_CONTENT_TYPE_TEXT`  
**Format:** `"STOP:"` (note the colon)  
**Completed Field:** `0` (not 1!)

**Example:**
```cpp
NV_REQUEST_RISE_SETTINGS_V1 stopSettings = { 0 };
stopSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
stopSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(stopSettings.content, sizeof(stopSettings.content), "STOP:", 5);
stopSettings.completed = 0;  // Must be 0, not 1

NvAPI_RequestRise(&stopSettings);
```

**Important Notes:**
- The format must include the colon: `"STOP:"` (5 bytes)
- The `completed` field must be `0`, not `1`

---

## Response Formats

### LLM Text Response

**Content Type:** `NV_RISE_CONTENT_TYPE_TEXT`  
**Format:** Raw text tokens  
**Streaming:** Yes

**Characteristics:**
- Tokens arrive one or more at a time
- Each callback contains a partial response
- Final callback has `completed = 1`
- Concatenate all tokens for full response

**Example Callback Sequence:**
```
Callback 1: content="Your ", completed=0
Callback 2: content="GPU ", completed=0
Callback 3: content="is an ", completed=0
Callback 4: content="NVIDIA RTX 4090", completed=1
```

---

### ASR Transcription Response

**Content Type:** `NV_RISE_CONTENT_TYPE_TEXT`  
**Format:** Prefixed transcription text  
**Streaming:** Yes (interim results)

**Response Prefixes:**

| Prefix | Description |
|--------|-------------|
| `ASR_INTERIM:` | Partial transcription during streaming |
| `ASR_FINAL:` | Complete transcription after STOP signal |

**Example:**
```cpp
if (chunk.find("ASR_INTERIM:") == 0) {
    std::string transcript = chunk.substr(12);
    std::cout << "Interim: " << transcript << std::endl;
} else if (chunk.find("ASR_FINAL:") == 0) {
    std::string transcript = chunk.substr(10);
    std::cout << "Final: " << transcript << std::endl;
}
```

---

### Progress Update Response

**Content Type:** `NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE`  
**Format:** Integer percentage as string (e.g., "42")  
**Streaming:** Yes

**Example:**
```cpp
void MyCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (pData->contentType == NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE) {
        int progress = std::stoi(pData->content);
        UpdateProgressBar(progress);  // 0-100
    }
}
```

---

## Code Examples

### Complete LLM Request Example

```cpp
#include "nvapi.h"
#include <iostream>
#include <atomic>
#include <thread>
#include <chrono>

std::atomic<bool> systemReady(false);
std::atomic<bool> responseComplete(false);
std::string fullResponse;

void __cdecl MyCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (!pData) return;
    
    if (pData->contentType == NV_RISE_CONTENT_TYPE_READY) {
        systemReady = true;
    }
    else if (pData->contentType == NV_RISE_CONTENT_TYPE_TEXT) {
        fullResponse += pData->content;
        if (pData->completed) {
            responseComplete = true;
        }
    }
}

int main() {
    // Initialize
    if (NvAPI_Initialize() != NVAPI_OK) {
        return 1;
    }
    
    // Register callback
    NV_RISE_CALLBACK_SETTINGS_V1 cbSettings = { 0 };
    cbSettings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
    cbSettings.callback = MyCallback;
    
    if (NvAPI_RegisterRiseCallback(&cbSettings) != NVAPI_OK) {
        return 1;
    }
    
    // Wait for READY
    while (!systemReady) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    
    // Send request
    std::string json = R"({"prompt":"Hello!","context_assist":{},"client_config":{}})";
    NV_REQUEST_RISE_SETTINGS_V1 reqSettings = { 0 };
    reqSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    reqSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(reqSettings.content, json.c_str(), json.length());
    reqSettings.completed = 1;
    
    if (NvAPI_RequestRise(&reqSettings) != NVAPI_OK) {
        return 1;
    }
    
    // Wait for response
    while (!responseComplete) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    
    std::cout << "Response: " << fullResponse << std::endl;
    
    // Cleanup
    NvAPI_Unload();
    return 0;
}
```

---

### Live Microphone Capture for ASR

This example demonstrates real-time speech-to-text using live microphone input with the miniaudio library.

#### Prerequisites

Include the miniaudio single-header library in your project:

```cpp
// Prevent Windows min/max macro conflicts
#define NOMINMAX

// Miniaudio configuration
#define MINIAUDIO_IMPLEMENTATION
#define MA_NO_DECODING      // We don't need file decoding
#define MA_NO_ENCODING      // We don't need file encoding
#define MA_NO_GENERATION    // We don't need waveform generation
#include "miniaudio.h"
```

#### Thread-Safe Audio Buffer

```cpp
#include <mutex>
#include <vector>
#include <atomic>

std::mutex micBufferMutex;
std::vector<float> micBuffer;              // Accumulated audio samples
std::atomic<bool> micCaptureActive(false); // Control flag
const int MIC_SAMPLE_RATE = 16000;         // 16kHz for ASR
const int MIC_CHANNELS = 1;                // Mono

// Miniaudio callback - called from audio thread
void MicrophoneDataCallback(ma_device* pDevice, void* pOutput, 
                            const void* pInput, ma_uint32 frameCount) {
    (void)pOutput; // Capture-only, no playback

    if (pInput == nullptr || !micCaptureActive.load(std::memory_order_acquire)) {
        return;
    }

    const float* inputSamples = static_cast<const float*>(pInput);

    std::lock_guard<std::mutex> lock(micBufferMutex);
    micBuffer.insert(micBuffer.end(), inputSamples, inputSamples + frameCount);
}
```

#### Enumerate and Select Microphone

```cpp
// Initialize audio context
ma_context context;
if (ma_context_init(NULL, 0, NULL, &context) != MA_SUCCESS) {
    std::cerr << "Failed to initialize audio context" << std::endl;
    return;
}

// Get available devices
ma_device_info* pCaptureDevices;
ma_uint32 captureDeviceCount;
ma_device_info* pPlaybackDevices;
ma_uint32 playbackDeviceCount;

ma_context_get_devices(&context, &pPlaybackDevices, &playbackDeviceCount,
                       &pCaptureDevices, &captureDeviceCount);

// List available microphones
for (ma_uint32 i = 0; i < captureDeviceCount; i++) {
    std::cout << "[" << i << "] " << pCaptureDevices[i].name;
    if (pCaptureDevices[i].isDefault) {
        std::cout << " (default)";
    }
    std::cout << std::endl;
}

// Select device (NULL for default, or &pCaptureDevices[index].id for specific)
ma_device_id* pSelectedDeviceId = nullptr;  // Use default
```

#### Initialize and Start Microphone

```cpp
ma_device_config deviceConfig;
ma_device device;

deviceConfig = ma_device_config_init(ma_device_type_capture);
deviceConfig.capture.pDeviceID = pSelectedDeviceId;  // NULL = default
deviceConfig.capture.format    = ma_format_f32;      // Float32 samples
deviceConfig.capture.channels  = MIC_CHANNELS;       // Mono
deviceConfig.sampleRate        = MIC_SAMPLE_RATE;    // 16kHz
deviceConfig.dataCallback      = MicrophoneDataCallback;
deviceConfig.pUserData         = nullptr;

if (ma_device_init(&context, &deviceConfig, &device) != MA_SUCCESS) {
    std::cerr << "Failed to initialize microphone" << std::endl;
    return;
}

// Clear buffer and start capture
{
    std::lock_guard<std::mutex> lock(micBufferMutex);
    micBuffer.clear();
}
micCaptureActive.store(true, std::memory_order_release);

if (ma_device_start(&device) != MA_SUCCESS) {
    std::cerr << "Failed to start microphone" << std::endl;
    ma_device_uninit(&device);
    return;
}
```

#### Stream Audio Chunks to RISE

```cpp
const int SAMPLES_PER_CHUNK = 700;  // ~44ms at 16kHz
int chunkId = 0;

while (!stopRequested) {
    std::vector<float> chunkSamples;

    // Get samples from buffer
    {
        std::lock_guard<std::mutex> lock(micBufferMutex);
        if (micBuffer.size() >= SAMPLES_PER_CHUNK) {
            chunkSamples.assign(micBuffer.begin(), 
                               micBuffer.begin() + SAMPLES_PER_CHUNK);
            micBuffer.erase(micBuffer.begin(), 
                           micBuffer.begin() + SAMPLES_PER_CHUNK);
        }
    }

    if (chunkSamples.empty()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        continue;
    }

    // Encode to base64
    const uint8_t* chunkData = reinterpret_cast<const uint8_t*>(chunkSamples.data());
    size_t chunkBytes = chunkSamples.size() * sizeof(float);
    std::string base64Audio = Base64Encode(chunkData, chunkBytes);

    // Format payload: "CHUNK:<id>:<sample_rate>:<base64_data>"
    std::string payload = "CHUNK:" + std::to_string(chunkId) + ":" + 
                          std::to_string(MIC_SAMPLE_RATE) + ":" + base64Audio;

    // Send to RISE
    NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
    requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(requestSettings.content, sizeof(requestSettings.content),
              payload.c_str(), payload.length());
    requestSettings.completed = 0;  // More chunks coming

    NvAPI_RequestRise(&requestSettings);

    // Wait for interim transcription response
    responseCompleteSemaphore.acquire();

    chunkId++;
}
```

#### Stop Capture and Get Final Transcription

```cpp
// Stop microphone
micCaptureActive.store(false, std::memory_order_release);
ma_device_stop(&device);
ma_device_uninit(&device);
ma_context_uninit(&context);

// Send STOP signal to finalize transcription
NV_REQUEST_RISE_SETTINGS_V1 stopSettings = { 0 };
stopSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
stopSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(stopSettings.content, sizeof(stopSettings.content), "STOP:", 5);
stopSettings.completed = 0;  // Must be 0, not 1

NvAPI_RequestRise(&stopSettings);

// Wait for final transcription (ASR_FINAL:...)
responseCompleteSemaphore.acquire();

// Extract final text
if (currentResponse.find("ASR_FINAL:") == 0) {
    std::string finalTranscript = currentResponse.substr(10);
    std::cout << "Final: " << finalTranscript << std::endl;
}
```

---

## Common Integration Scenarios

### Scenario 1: Chatbot/Assistant UI

**Use Case**: Interactive chat interface with streaming responses

```cpp
class ChatAssistant {
    void OnUserInput(const std::string& prompt) {
        SendLLMRequest(prompt);
    }
    
    void OnRiseCallback(const char* content, bool completed) {
        // Update UI (marshal to UI thread if needed)
        chatWidget->AppendText(content);
        
        if (completed) {
            chatWidget->EnableInput();
        }
    }
};
```

### Scenario 2: Voice Command System

**Use Case**: Capture microphone audio and execute commands

```cpp
class VoiceCommandSystem {
    void StartListening() {
        audioCapture->Start();
        while (listening) {
            auto chunk = audioCapture->GetNextChunk();
            SendASRChunk(chunk);
        }
        FinalizeASR();
    }
    
    void OnTranscription(const std::string& text) {
        if (IsCommand(text)) {
            ExecuteCommand(text);
        }
    }
};
```

### Scenario 3: Background AI Assistant

**Use Case**: Monitor system events and provide contextual AI assistance

```cpp
class BackgroundAssistant {
    void OnSystemEvent(const Event& event) {
        std::string context = BuildContextFromEvent(event);
        std::string prompt = "Analyze: " + context;
        SendLLMRequest(prompt);
    }
    
    void OnRiseResponse(const std::string& response) {
        ShowNotification(response);
    }
};
```

---

## Thread Safety

### Shared State Protection

```cpp
// Use std::mutex for shared data
std::mutex responseMutex;
std::string currentResponse;

void MyCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    std::lock_guard<std::mutex> lock(responseMutex);
    currentResponse += pData->content;
}

// Use std::atomic for flags
std::atomic<bool> systemReady(false);
std::atomic<bool> responseComplete(false);

// Use semaphores for signaling
std::counting_semaphore<1> responseSemaphore(0);
```

### Synchronization Strategies

**Blocking Pattern** (Simpler):
- Use semaphores/condition variables
- Main thread waits for callback to signal completion
- Good for console apps or simple request-response flows

**Non-Blocking Pattern** (More Flexible):
- Callback updates UI or queues data structures
- Main thread polls or reacts to state changes
- Good for GUI apps or concurrent request handling

---

## Error Handling

### Best Practices

1. **Check Return Values**: Every `NvAPI_*` call returns `NvAPI_Status`

```cpp
NvAPI_Status status = NvAPI_RequestRise(&settings);
if (status != NVAPI_OK) {
    LogError("Request failed", status);
}
```

2. **Wait for READY**: Always wait for the READY signal before sending requests

3. **Handle Null Callbacks**: Always verify `pData != nullptr`

4. **Validate JSON**: Malformed JSON will cause request failures

5. **Monitor Completion**: Track `pData->completed` to know when responses finish

---

## Performance Optimization

### Tips for High-Performance Integration

1. **Callback Speed**: Keep callback handler under 1ms
   - Queue data for processing elsewhere
   - Avoid heavy computation in callbacks
   - Use lock-free structures when possible

2. **Audio Chunk Size**: 500ms - 1s of audio per chunk
   - Balance latency vs overhead
   - Smaller chunks = lower latency, more overhead

3. **JSON Efficiency**: Pre-build JSON templates

4. **Connection Reuse**: Initialize once, send many requests

5. **Memory Management**: Reuse buffers across chunks

---

## Troubleshooting

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

**"'(': illegal token on right side of '::'"**
- Add `#define NOMINMAX` before including Windows headers
- This prevents Windows min/max macros from conflicting with std::min/std::max

### Runtime Errors

**"RISE is not ready" or hangs during initialization**
- Ensure G-Assist / RISE engine is installed and running
- Check Windows Services for NVIDIA services
- Restart the RISE service if needed

**Callbacks not firing**
- Ensure callback function signature matches exactly
- Check that the callback is registered before sending requests
- Verify thread-safety of callback code

---

## Project Structure

```
api/c++/
│
├── main.cpp                    # Main application with all demos
├── audio_utils.h               # Audio processing utilities
├── miniaudio.h                 # Single-header audio library for mic capture
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
├── README.md                   # This documentation file
│
└── x64/
    ├── Debug/
    │   └── rise_demo_client.exe
    └── Release/
        └── rise_demo_client.exe
```

---

## Related Resources

- **Python Binding** (`G-Assist/api/bindings/python/`): Python wrapper for RISE API
- **Plugin Examples** (`G-Assist/plugins/examples/`): Example plugins for G-Assist
- **NVIDIA NVAPI**: https://github.com/NVIDIA/nvapi

---

**Last Updated:** December 2025  
**API Version:** V1  
**Compatible With:** RISE/G-Assist 1.x

---

**Happy Coding!**

For questions or issues, please refer to the main G-Assist documentation.
