# RISE API Reference

Complete API reference for the RISE C++ interface.

## Table of Contents

- [Core Functions](#core-functions)
- [Structures](#structures)
- [Content Types](#content-types)
- [Request Formats](#request-formats)
- [Response Formats](#response-formats)
- [Error Codes](#error-codes)
- [Constants and Limits](#constants-and-limits)
- [Code Examples](#code-examples)
  - [Live Microphone Capture for ASR](#live-microphone-capture-for-asr)
  - [Complete LLM Request Example](#complete-llm-request-example)

## Core Functions

### NvAPI_Initialize()

Initializes the NVAPI library. Must be called before any other NVAPI functions.

**Signature:**
```cpp
NvAPI_Status NvAPI_Initialize();
```

**Returns:**
- `NVAPI_OK` - Success
- `NVAPI_ERROR` - Initialization failed

**Usage:**
```cpp
NvAPI_Status status = NvAPI_Initialize();
if (status != NVAPI_OK) {
    // Handle error
}
```

**Notes:**
- Call once at application startup
- Must be called before registering callbacks or sending requests
- Thread-safe

---

### NvAPI_RegisterRiseCallback()

Registers a callback function to receive asynchronous responses from the RISE engine.

**Signature:**
```cpp
NvAPI_Status NvAPI_RegisterRiseCallback(NV_RISE_CALLBACK_SETTINGS_V1* pCallbackSettings);
```

**Parameters:**
- `pCallbackSettings` - Pointer to callback settings structure

**Returns:**
- `NVAPI_OK` - Callback registered successfully
- `NVAPI_INVALID_ARGUMENT` - NULL or invalid settings
- `NVAPI_ERROR` - Registration failed

**Usage:**
```cpp
NV_RISE_CALLBACK_SETTINGS_V1 settings = { 0 };
settings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
settings.callback = MyCallbackFunction;

NvAPI_Status status = NvAPI_RegisterRiseCallback(&settings);
if (status != NVAPI_OK) {
    // Handle error
}
```

**Notes:**
- Must be called after `NvAPI_Initialize()`
- Callback runs on RISE-managed thread
- Only one callback can be registered per application
- Wait for `NV_RISE_CONTENT_TYPE_READY` before sending requests

---

### NvAPI_RequestRise()

Sends a request to the RISE engine (LLM text or ASR audio).

**Signature:**
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

**Usage:**
```cpp
NV_REQUEST_RISE_SETTINGS_V1 request = { 0 };
request.version = NV_REQUEST_RISE_SETTINGS_VER1;
request.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(request.content, jsonPayload.c_str(), jsonPayload.length());
request.completed = 1;

NvAPI_Status status = NvAPI_RequestRise(&request);
if (status != NVAPI_OK) {
    // Handle error
}
```

**Notes:**
- Can only be called after receiving `READY` signal
- Non-blocking - responses arrive via callback
- Thread-safe
- Maximum content size: 4096 bytes

---

### NvAPI_Unload()

Unloads the NVAPI library and cleans up resources.

**Signature:**
```cpp
NvAPI_Status NvAPI_Unload();
```

**Returns:**
- `NVAPI_OK` - Successfully unloaded

**Usage:**
```cpp
NvAPI_Unload();
```

**Notes:**
- Call at application shutdown
- Ensure no requests are in-flight
- Callback will no longer be invoked after this call
- Thread-safe

---

## Structures

### NV_RISE_CALLBACK_SETTINGS_V1

Settings structure for registering a callback handler.

**Definition:**
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

**Note:** When you initialize the structure with `{ 0 }`, all fields including `super` and `reserved` are automatically zeroed. You only need to set `version` and `callback` explicitly

**Example:**
```cpp
void __cdecl MyRiseCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    // Handle callback
}

NV_RISE_CALLBACK_SETTINGS_V1 settings = { 0 };
settings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
settings.callback = MyRiseCallback;
```

---

### NV_RISE_CALLBACK_DATA_V1

Data structure passed to callback function containing response information.

**Definition:**
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

**Note:** The `super` field is managed internally by NVAPI. In your callback, focus on `contentType`, `content`, and `completed`

**Example:**
```cpp
void MyCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (!pData) return;
    
    switch (pData->contentType) {
        case NV_RISE_CONTENT_TYPE_TEXT:
            std::cout << pData->content;
            if (pData->completed) {
                std::cout << "\n[COMPLETE]\n";
            }
            break;
    }
}
```

---

### NV_REQUEST_RISE_SETTINGS_V1

Settings structure for sending requests to RISE.

**Definition:**
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

**Note:** When you initialize the structure with `{ 0 }`, the `reserved` field is automatically zeroed. You only need to set the key fields explicitly

**Example:**
```cpp
NV_REQUEST_RISE_SETTINGS_V1 request = { 0 };
request.version = NV_REQUEST_RISE_SETTINGS_VER1;
request.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(request.content, "JSON or ASR payload", 19);
request.completed = 1;
```

---

## Content Types

### NV_RISE_CONTENT_TYPE Enumeration

Defines the type of content being sent or received.

**Values:**

| Type | Value | Direction | Description |
|------|-------|-----------|-------------|
| `NV_RISE_CONTENT_TYPE_TEXT` | 1 | Both | LLM responses, ASR transcriptions, text requests |
| `NV_RISE_CONTENT_TYPE_GRAPH` | 2 | Callback | Graphical or chart data |
| `NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE` | 6 | Callback | Progress percentage (0-100) |
| `NV_RISE_CONTENT_TYPE_READY` | 7 | Callback | System ready signal |

### Type Details

#### TEXT (1)
- **Request**: JSON for LLM, `CHUNK:` format for ASR
- **Response**: Streaming text tokens or transcription
- **Streaming**: Yes (check `completed` field)
- **When to Expect**: After every LLM/ASR request

#### GRAPH (2)
- **Request**: Not used
- **Response**: Structured data for charts/graphs
- **Streaming**: No
- **When to Expect**: Application-specific features

#### PROGRESS_UPDATE (6)
- **Request**: Not used
- **Response**: Integer percentage (0-100) as string
- **Streaming**: Yes (multiple updates possible)
- **When to Expect**: During long-running operations

#### READY (7)
- **Request**: Not used
- **Response**: Empty or status message
- **Streaming**: No
- **When to Expect**: Once at startup, after callback registration

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
- **Encoding:** 16-bit PCM
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

To finalize ASR transcription before sending all audio:

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
- This matches the ASR streaming protocol expectations

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
**Format:** Transcribed text  
**Streaming:** Yes (interim results)

**Characteristics:**
- Interim transcriptions may arrive during streaming
- Final transcription arrives when all audio processed
- Each callback may contain partial or complete transcription
- Final callback has `completed = 1`

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

## Error Codes

### NvAPI_Status Values

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

### Common Error Scenarios

**NVAPI_ERROR during RequestRise:**
- RISE service not running
- Request payload too large (>4096 bytes)
- Malformed request format

**NVAPI_NOT_SUPPORTED:**
- RISE features not available on this system
- Missing NVIDIA driver components

**NVAPI_INVALID_ARGUMENT:**
- NULL pointer passed
- Invalid structure version
- Empty content field

---

## Constants and Limits

### Version Constants

```cpp
#define NV_RISE_CALLBACK_SETTINGS_VER1  MAKE_NVAPI_VERSION(NV_RISE_CALLBACK_SETTINGS_V1, 1)
#define NV_REQUEST_RISE_SETTINGS_VER1   MAKE_NVAPI_VERSION(NV_REQUEST_RISE_SETTINGS_V1, 1)
```

Always use these constants for the `version` field in structures.

### Size Limits

| Limit | Value | Notes |
|-------|-------|-------|
| Max Request Content | 4096 bytes | Total size including format strings |
| Max Response Content | 4096 bytes | Per callback invocation |
| Max Callback Count | Unlimited | Responses can span multiple callbacks |

### Timing Recommendations

| Operation | Typical Duration |
|-----------|-----------------|
| Wait for READY | Immediate (waits until ready) |
| LLM Request Response | Varies (streaming) |
| ASR Chunk Processing | ~100-500ms per chunk |
| Callback Execution | <1 millisecond |

### Audio Specifications

| Parameter | Recommended | Supported Range |
|-----------|------------|-----------------|
| Sample Rate | 16 kHz | Any (engine resamples) |
| Bit Depth | 16-bit | 16-bit only |
| Channels | Mono | Mono only |
| Chunk Duration | 500ms - 1s | Any |
| Audio Format | PCM | PCM only |

---

## Code Examples

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

Set up a thread-safe buffer for the audio callback:

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

#### ASR Response Types

| Response Prefix | Description |
|-----------------|-------------|
| `ASR_INTERIM:` | Partial transcription during streaming |
| `ASR_FINAL:` | Complete transcription after STOP signal |

---

### Complete LLM Request Example

```cpp
#include "nvapi.h"
#include <iostream>
#include <atomic>

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

## Related Documentation

- **[INTEGRATION.md](INTEGRATION.md)** - Integration patterns and architecture guide
- **[README.md](README.md)** - Demo build and run instructions
- **NVIDIA NVAPI**: https://github.com/NVIDIA/nvapi

---

**Last Updated:** December 2025  
**API Version:** V1  
**Compatible With:** RISE/G-Assist 1.x

