# RISE API Integration Guide

This guide provides architectural guidance and implementation patterns for integrating the RISE API into your own C++ applications.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Integration Steps](#integration-steps)
- [Request/Response Patterns](#requestresponse-patterns)
- [Common Integration Scenarios](#common-integration-scenarios)
- [Thread Safety](#thread-safety)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)
- [Testing Strategy](#testing-strategy)
- [Example Architectures](#example-architectures)
- [Reference Implementation](#reference-implementation)

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

## Integration Steps

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
        // Handle error
        return false;
    }
    
    // 2. Register callback
    NV_RISE_CALLBACK_SETTINGS_V1 settings = { 0 };
    settings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
    settings.callback = MyRiseCallback;
    
    status = NvAPI_RegisterRiseCallback(&settings);
    if (status != NVAPI_OK) {
        // Handle error
        return false;
    }
    
    // 3. Wait for READY signal
    std::cout << "[WAITING] For RISE to become ready...\n";
    while (!systemReady) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    
    std::cout << "[OK] RISE Client Initialized Successfully!\n";
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

## Request/Response Patterns

### LLM Text Requests

**Format**: JSON string with `prompt`, `context_assist`, and `client_config` fields

**Example:**
```cpp
std::string jsonRequest = R"({
    "prompt": "What is my GPU?",
    "context_assist": {},
    "client_config": {
        "assistant_identifier": "my_app",
        "enable_streaming": true
    }
})";

NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(requestSettings.content, jsonRequest.c_str(), jsonRequest.length());
requestSettings.completed = 1;  // Single-shot request

NvAPI_RequestRise(&requestSettings);
```

**Response Characteristics:**
- Responses arrive token-by-token via callback (streaming)
- Final callback has `pData->completed = 1`
- Streaming can be disabled in `client_config`

### ASR Audio Requests

**Format**: `"CHUNK:<id>:<sample_rate>:<base64_audio>"`

**Example:**
```cpp
// Encode audio to Base64
std::string audioBase64 = Base64Encode(audioData);

// Build payload
std::string payload = "CHUNK:" + 
                     std::to_string(chunkId) + ":" + 
                     std::to_string(16000) + ":" + 
                     audioBase64;

NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(requestSettings.content, payload.c_str(), payload.length());
requestSettings.completed = 0;  // More chunks coming

NvAPI_RequestRise(&requestSettings);
```

**To Finalize:**
```cpp
// Send STOP: signal (note the colon)
NV_REQUEST_RISE_SETTINGS_V1 stopSettings = { 0 };
stopSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
stopSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
strncpy_s(stopSettings.content, sizeof(stopSettings.content), "STOP:", 5);
stopSettings.completed = 0;  // Not 1!
NvAPI_RequestRise(&stopSettings);
```

**Best Practices:**
- Send audio in ~500ms intervals for real-time feel
- Set `completed = 0` for ongoing chunks, `1` for final chunk
- Sample rate can be any value (engine resamples to 16kHz if needed)
- Use 16-bit PCM format for audio data

## Common Integration Scenarios

### Scenario 1: Chatbot/Assistant UI

**Use Case**: Interactive chat interface with streaming responses

**Implementation Pattern:**
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

**Key Points:**
- Register callback that updates UI text widget
- Send LLM requests on user input
- Display streaming responses in real-time
- Handle conversation history in your application

### Scenario 2: Voice Command System

**Use Case**: Capture microphone audio and execute commands

**Implementation Pattern:**
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

**Key Points:**
- Capture microphone audio using WASAPI/PortAudio
- Convert to 16-bit PCM at 16kHz
- Base64 encode and send as CHUNK messages
- Display interim ASR results for user feedback
- Execute commands on final transcription

### Scenario 3: Background AI Assistant

**Use Case**: Monitor system events and provide contextual AI assistance

**Implementation Pattern:**
```cpp
class BackgroundAssistant {
    void OnSystemEvent(const Event& event) {
        std::string context = BuildContextFromEvent(event);
        std::string prompt = "Analyze: " + context;
        SendLLMRequest(prompt);
    }
    
    void OnRiseResponse(const std::string& response) {
        // Show notification or silent processing
        ShowNotification(response);
    }
};
```

**Key Points:**
- Monitor system events (clipboard, window changes)
- Trigger LLM requests based on context
- Process responses silently or via notifications
- Maintain persistent RISE connection

## Thread Safety

### Threading Model

**What Runs Where:**
- **Your callback**: RISE-managed thread (not your control)
- **`NvAPI_RequestRise()`**: Your thread (typically main)
- **UI updates**: Must marshal to UI thread (platform-specific)

### Shared State Protection

**Required Synchronization:**

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

```cpp
void SendAndWait() {
    responseSemaphore.acquire();  // Wait for completion
}
```

**Non-Blocking Pattern** (More Flexible):
- Callback updates UI or queues data structures
- Main thread polls or reacts to state changes
- Good for GUI apps or concurrent request handling

```cpp
void SendAsync() {
    // Fire and forget - callback handles everything
}
```

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

```cpp
while (!systemReady) {
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
}
```

3. **Handle Null Callbacks**: Always verify `pData != nullptr`

```cpp
void MyCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (!pData) return;  // Safety check
    // Process data...
}
```

4. **Validate JSON**: Malformed JSON will cause request failures

```cpp
if (!IsValidJSON(jsonRequest)) {
    LogError("Invalid JSON");
    return;
}
```

5. **Monitor Completion**: Track `pData->completed` to know when responses finish

```cpp
if (pData->completed) {
    responseCompleteSemaphore.release();
}
```

## Performance Optimization

### Tips for High-Performance Integration

1. **Callback Speed**: Keep callback handler under 1ms
   - Queue data for processing elsewhere
   - Avoid heavy computation in callbacks
   - Use lock-free structures when possible

2. **Audio Chunk Size**: 500ms - 1s of audio per chunk
   - Balance latency vs overhead
   - Smaller chunks = lower latency, more overhead
   - Larger chunks = higher latency, less overhead

3. **JSON Efficiency**: Pre-build JSON templates

```cpp
// Bad: Build JSON every request
std::string json = BuildJSON(prompt);

// Good: Use template
const std::string jsonTemplate = R"({"prompt":"{}","context_assist":{},"client_config":{}})";
std::string json = Format(jsonTemplate, prompt);
```

4. **Connection Reuse**: Initialize once, send many requests
   - No per-request initialization overhead
   - Maintain persistent connection to RISE
   - Amortize setup cost across many requests

5. **Memory Management**: Reuse buffers

```cpp
// Reuse audio buffer across chunks
std::vector<uint8_t> audioBuffer(chunkSize);
while (capturing) {
    captureAudio(audioBuffer);
    sendChunk(audioBuffer);
}
```

## Testing Strategy

### Progressive Testing Approach

1. **Start Simple**: Test LLM with hardcoded "Hello" prompt
   - Verify initialization works
   - Confirm callback fires
   - Check basic connectivity

2. **Verify Streaming**: Confirm you see token-by-token responses
   - Log each callback invocation
   - Check `completed` flag
   - Measure streaming latency

3. **Test Error Cases**: Disconnect RISE service, send malformed JSON
   - Verify timeout handling
   - Check error recovery
   - Test edge cases

4. **Load Test**: Send rapid-fire requests to check thread safety
   - Concurrent requests
   - Race condition detection
   - Memory leak checking

5. **Audio Pipeline**: Test ASR with pre-recorded audio before live microphone
   - Validate chunk formatting
   - Check Base64 encoding
   - Verify transcription accuracy

### Debugging Tips

- Add detailed logging to callback handler
- Use Visual Studio's thread window to track async behavior
- Monitor memory usage for leaks
- Profile callback execution time
- Test with Debug build for better diagnostics

## Example Architectures

### Simple Console Application

```
main()
  ├─ InitializeRise()
  ├─ WaitForReady()
  └─ MainLoop:
      ├─ Get user input
      ├─ SendRequest()
      ├─ WaitForCompletion()
      └─ Display result
```

**Good for**: Quick prototypes, command-line tools, testing

### GUI Application

```
main()
  ├─ CreateUI()
  ├─ InitializeRise()
  └─ RunEventLoop()

Callback Thread:
  ├─ Receive response
  ├─ Queue UI update
  └─ Signal UI thread

UI Thread:
  ├─ Process queued updates
  └─ Refresh display
```

**Good for**: Desktop applications, interactive tools

### Service/Daemon

```
main()
  ├─ InitializeRise()
  └─ BackgroundThread:
      ├─ Monitor events
      ├─ Build context
      ├─ SendRequest()
      └─ ProcessResponse()

Callback Thread:
  ├─ Parse response
  ├─ Execute action
  └─ Log result
```

**Good for**: Background services, system integrations, automation

## Reference Implementation

See **`main.cpp`** for production-ready code demonstrating:

- Complete initialization with error handling
- Thread-safe callback implementation
- Both blocking and streaming patterns
- LLM and ASR request formatting
- Synchronization primitives usage
- Clean shutdown procedures

See **`audio_utils.h`** for:

- Base64 encoding/decoding functions
- Audio format conversion utilities
- PCM audio generation (for testing)

### Key Functions to Study

| Function | Line Range | Purpose |
|----------|-----------|---------|
| `RiseCallbackHandler()` | 136-180 | Complete callback implementation |
| `InitializeRiseClient()` | 270-310 | Full initialization with error handling |
| `SendLLMRequest()` | 320-360 | LLM request with JSON formatting |
| `RunASRDemo()` | 580-780 | ASR streaming with chunking |

---

## Additional Resources

- **[API_REFERENCE.md](API_REFERENCE.md)** - Complete API function and structure reference
- **[README.md](README.md)** - Demo build and run instructions
- **NVIDIA NVAPI**: https://github.com/NVIDIA/nvapi

**Questions?** Check the troubleshooting section in [README.md](README.md) or refer to the main G-Assist documentation.

