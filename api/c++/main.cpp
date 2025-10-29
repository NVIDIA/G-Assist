/*
 * RISE C++ Demo Client
 * 
 * This application demonstrates how to use the RISE (Runtime Inference System Engine) API
 * to send both LLM (Large Language Model) and ASR (Automatic Speech Recognition) requests
 * to the backend, handle streaming responses, and manage different content types.
 * 
 * Features demonstrated:
 * - Registering callbacks for asynchronous responses
 * - Sending LLM text requests with streaming
 * - Sending ASR audio chunks with streaming
 * - Handling multiple content types (TEXT, READY, PROGRESS_UPDATE, etc.)
 * - Proper synchronization between requests and responses
 */

#include <iostream>
#include <string>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <chrono>
#include <vector>
#include <cstring>
#include <iomanip>
#include <atomic>
#include <fstream>
#include <algorithm>
#include <cmath>
#include "nvapi.h"

// ============================================================================
// Synchronization Primitives
// ============================================================================

/**
 * Simple semaphore implementation for synchronizing async callbacks
 */
class Semaphore {
private:
    std::mutex mutex_;
    std::condition_variable condition_;
    unsigned long count_ = 0;

public:
    void release() {
        std::lock_guard<decltype(mutex_)> lock(mutex_);
        ++count_;
        condition_.notify_one();
    }

    void acquire() {
        std::unique_lock<decltype(mutex_)> lock(mutex_);
        while (!count_) {
            condition_.wait(lock);
        }
        --count_;
    }

    bool try_acquire() {
        std::lock_guard<decltype(mutex_)> lock(mutex_);
        if (count_) {
            --count_;
            return true;
        }
        return false;
    }
};

// ============================================================================
// Global State Management
// ============================================================================

Semaphore responseCompleteSemaphore;
std::mutex responseMutex;
std::string currentResponse;
std::string currentChart;
bool systemReady = false;
bool responseCompleted = false;
bool firstTokenReceived = false;
bool callbackFinished = false;
std::atomic<bool> spinnerActive(false);
std::chrono::steady_clock::time_point requestStartTime;
std::chrono::steady_clock::time_point firstTokenTime;

// ============================================================================
// Content Type Constants
// ============================================================================
// Note: NV_RISE_CONTENT_TYPE enum is defined in nvapi.h (values 0-9)
// We define RESERVED separately as it's not in the official enum yet

// Reserved type for experimental features (streaming ASR PoC)
constexpr int NV_RISE_CONTENT_TYPE_RESERVED = 10;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Get human-readable name for content type
 */
const char* GetContentTypeName(int contentType) {
    switch (contentType) {
        case NV_RISE_CONTENT_TYPE_TEXT: return "TEXT";
        case NV_RISE_CONTENT_TYPE_GRAPH: return "GRAPH";
        case NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR: return "CUSTOM_BEHAVIOR";
        case NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR_RESULT: return "CUSTOM_BEHAVIOR_RESULT";
        case NV_RISE_CONTENT_TYPE_INSTALLING: return "INSTALLING";
        case NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE: return "PROGRESS_UPDATE";
        case NV_RISE_CONTENT_TYPE_READY: return "READY";
        case NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST: return "DOWNLOAD_REQUEST";
        case NV_RISE_CONTENT_TYPE_UPDATE_INFO: return "UPDATE_INFO";
        default:
            if (contentType == NV_RISE_CONTENT_TYPE_RESERVED) {
                return "RESERVED (ASR)";
            }
            return "INVALID/UNKNOWN";
    }
}

/**
 * Print colored output to console
 */
void PrintColored(const std::string& text, const std::string& color) {
    // Windows console color codes (for future enhancement)
    std::cout << text;
}

// ============================================================================
// Callback Handler
// ============================================================================

/**
 * Main callback function that handles all RISE responses
 * This function is called asynchronously by the RISE engine
 */
void RiseCallbackHandler(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (!pData) return;

    std::lock_guard<std::mutex> lock(responseMutex);

    // Uncomment for debugging:
    // std::string contentStr(pData->content);
    // std::cout << "[DEBUG] Callback received: Type=" << GetContentTypeName(pData->contentType)
    //           << " Completed=" << pData->completed
    //           << " Content='" << contentStr.substr(0, 50) << "'"
    //           << " firstTokenReceived=" << firstTokenReceived << std::endl;

    switch (pData->contentType) {
        case NV_RISE_CONTENT_TYPE_READY:
            if (pData->completed == 1) {
                systemReady = true;
                std::cout << "[RISE] System is READY!" << std::endl;
            }
            break;

        case NV_RISE_CONTENT_TYPE_TEXT: {
            // Handle text responses (both LLM and ASR)
            std::string chunk(pData->content);

            if (!chunk.empty()) {
                // Track first token arrival time
                if (!firstTokenReceived) {
                    firstTokenReceived = true;
                    firstTokenTime = std::chrono::steady_clock::now();

                    // Give spinner thread time to clear itself before we start printing
                    std::this_thread::sleep_for(std::chrono::milliseconds(150));
                }

                // Check if this is an ASR response
                if (chunk.find("ASR_") == 0) {
                    // ASR responses - display immediately
                    currentResponse = chunk;
                    
                    // Stop any active spinner immediately
                    if (spinnerActive.load(std::memory_order_acquire)) {
                        spinnerActive.store(false, std::memory_order_release);
                        std::this_thread::sleep_for(std::chrono::milliseconds(20)); // Let spinner clear
                    }
                    
                    // Extract and display transcription text immediately
                    if (chunk.find("ASR_INTERIM:") == 0) {
                        std::string transcript = chunk.substr(12);
                        if (!transcript.empty()) {
                            // Clear spinner line and display transcription
                            std::cout << "\r\033[K";  // Clear current line
                            std::cout << "Transcription: " << transcript << std::endl;
                            std::cout.flush();
                        }
                    } else if (chunk.find("ASR_FINAL:") == 0) {
                        // Final transcription will be handled separately
                        std::cout << "\r\033[K";  // Clear spinner line
                        std::cout.flush();
                    }
                } else {
                    // LLM responses - print immediately as they arrive
                    std::cout << chunk;
                    std::cout.flush();
                    currentResponse += chunk;
                }
            }

            if (pData->completed == 1) {
                responseCompleted = true;
                // Signal that callback has completely finished
                callbackFinished = true;
                responseCompleteSemaphore.release();
            }
            break;
        }

        case NV_RISE_CONTENT_TYPE_GRAPH:
            currentChart += std::string(pData->content);
            if (pData->completed == 1) {
                std::cout << "[GRAPH DATA] " << currentChart << std::endl;
                responseCompleted = true;
                responseCompleteSemaphore.release();
            }
            break;

        case NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR:
        case NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR_RESULT:
        {
            // Handle custom behavior responses (show JSON content)
            std::string customContent(pData->content);
            if (!customContent.empty()) {
                // Track first token if not already set
                if (!firstTokenReceived) {
                    firstTokenReceived = true;
                    firstTokenTime = std::chrono::steady_clock::now();
                    std::this_thread::sleep_for(std::chrono::milliseconds(150));
                }

                // Print custom behavior content
                std::cout << customContent;
                std::cout.flush();
                currentResponse += customContent;
            }

            if (pData->completed == 1) {
                responseCompleted = true;
                // Signal that callback has completely finished
                callbackFinished = true;
                responseCompleteSemaphore.release();
            }
            break;
        }

        case NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE: {
            std::string progress(pData->content);
            std::cout << "[PROGRESS] " << progress << "%" << std::endl;
            break;
        }

        case NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST:
            std::cout << "[DOWNLOAD REQUESTED] RISE requires installation" << std::endl;
            break;

        case NV_RISE_CONTENT_TYPE_INSTALLING:
            std::cout << "[INSTALLING] RISE is being installed..." << std::endl;
            break;

        default:
            std::cout << "[UNKNOWN] Content type: " << pData->contentType << std::endl;
            break;
    }
}

// ============================================================================
// RISE API Wrapper Functions
// ============================================================================

/**
 * Initialize RISE client and register callback
 */
bool InitializeRiseClient() {
    std::cout << "=== Initializing RISE Client ===" << std::endl;

    // Initialize NVAPI
    NvAPI_Status status = NvAPI_Initialize();
    if (status != NVAPI_OK) {
        std::cerr << "[ERROR] NvAPI_Initialize failed with status: " << status << std::endl;
        return false;
    }
    std::cout << "[OK] NVAPI Initialized" << std::endl;

    // Setup callback settings
    NV_RISE_CALLBACK_SETTINGS_V1 callbackSettings = { 0 };
    callbackSettings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
    callbackSettings.callback = RiseCallbackHandler;

    // Register callback
    status = NvAPI_RegisterRiseCallback(&callbackSettings);
    if (status != NVAPI_OK) {
        std::cerr << "[ERROR] NvAPI_RegisterRiseCallback failed with status: " << status << std::endl;
        return false;
    }
    std::cout << "[OK] Callback Registered" << std::endl;

        // Wait for system ready signal
        std::cout << "[WAITING] For RISE to become ready..." << std::endl;
        while (!systemReady) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }

    std::cout << "[OK] RISE Client Initialized Successfully!" << std::endl;
    return true;
}

/**
 * Send LLM text request to RISE
 * This demonstrates streaming text-based AI responses
 */
bool SendLLMRequest(const std::string& prompt) {
    // Reset response state and start timing
    {
        std::lock_guard<std::mutex> lock(responseMutex);
        currentResponse.clear();
        currentChart.clear();
        responseCompleted = false;
        firstTokenReceived = false;  // Reset for each new request
        callbackFinished = false;
        requestStartTime = std::chrono::steady_clock::now();
    }

    // CRITICAL: Drain any leftover semaphore releases from previous requests
    while (responseCompleteSemaphore.try_acquire()) {
        // Drain silently
    }

    // Build JSON request
    // Format: {"prompt": "...", "context_assist": {}, "client_config": {}}
    std::string jsonRequest = "{\"prompt\":\"" + prompt + "\",\"context_assist\":{},\"client_config\":{}}";

    // Setup request settings
    NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
    requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(requestSettings.content, sizeof(requestSettings.content), 
              jsonRequest.c_str(), jsonRequest.length());
    requestSettings.completed = 1;  // Single request, not chunked

    // Send request
    NvAPI_Status status = NvAPI_RequestRise(&requestSettings);
    if (status != NVAPI_OK) {
        std::cerr << "\n[ERROR] NvAPI_RequestRise failed with status: " << status << std::endl;
        return false;
    }

    // Show spinner while waiting for first token
    spinnerActive.store(true, std::memory_order_release);
    
    std::thread spinnerThread([]() {
        const char spinChars[] = { '|', '/', '-', '\\' };
        int idx = 0;
        
        // Small delay to ensure we see the initialized value
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
        
        // firstTokenReceived is a global, access it directly
        while (spinnerActive.load(std::memory_order_acquire) && !firstTokenReceived) {
            std::cout << "\r" << spinChars[idx % 4] << " ";
            std::cout.flush();
            idx++;
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
        
        // Clear spinner when done
        std::cout << "\r   \r";
        std::cout.flush();
    });

    // Wait for response completion (streaming prints in callback)
    responseCompleteSemaphore.acquire();

    // Stop spinner (it should have already stopped when first token arrived)
    spinnerActive.store(false, std::memory_order_release);
    spinnerThread.join();

    // Wait for callback to signal it has completely finished printing
    {
        std::unique_lock<std::mutex> lock(responseMutex);
        while (!callbackFinished) {
            lock.unlock();
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            lock.lock();
        }
    }

    // Calculate TTFT - this should now be available since callback has finished
    double ttft = 0.0;
    {
        std::lock_guard<std::mutex> lock(responseMutex);
        if (firstTokenReceived) {
            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(
                firstTokenTime - requestStartTime
            );
            ttft = duration.count() / 1000.0;
        } else {
            // This shouldn't happen, but handle gracefully
            ttft = 0.0;
        }
    }

    // Display TTFT metric (callback has finished printing all text)
    std::cout << "\n\n[TTFT: " << std::fixed << std::setprecision(3)
              << ttft << "s]" << std::endl;

    return true;
}


// ============================================================================
// Demo Functions
// ============================================================================

/**
 * Demo: Interactive LLM Chat
 */
void DemoLLMChat() {
    std::cout << "\n\n";
    std::cout << "===============================================================" << std::endl;
    std::cout << "              RISE LLM CHAT DEMO (Streaming)                  " << std::endl;
    std::cout << "===============================================================" << std::endl;
    std::cout << "Type your questions and see streaming responses in real-time!" << std::endl;
    std::cout << "Type 'exit' to return to main menu\n" << std::endl;

    while (true) {
        std::cout << "\n[YOU]: ";
        std::string userInput;
        std::getline(std::cin, userInput);

        if (userInput == "exit" || userInput == "quit") {
            break;
        }

        if (userInput.empty()) {
            continue;
        }

        std::cout << "\n";  // Add blank line before response
        SendLLMRequest(userInput);
    }
}

// ============================================================================
// WAV File Utilities
// ============================================================================

#pragma pack(push, 1)
struct WavHeader {
    char riff[4];           // "RIFF"
    uint32_t fileSize;      // File size - 8
    char wave[4];           // "WAVE"
    char fmt[4];            // "fmt "
    uint32_t fmtSize;       // 16 for PCM
    uint16_t audioFormat;   // 1 for PCM
    uint16_t channels;
    uint32_t sampleRate;
    uint32_t byteRate;
    uint16_t blockAlign;
    uint16_t bitsPerSample;
    char data[4];           // "data"
    uint32_t dataSize;      // Size of audio data
};
#pragma pack(pop)

/**
 * Load PCM data from WAV file
 */
bool LoadWavFile(const std::string& filename, std::vector<int16_t>& samples, int& sampleRate, int& channels) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "[ERROR] Could not open file: " << filename << std::endl;
        return false;
    }

    // Read WAV header
    WavHeader header;
    file.read(reinterpret_cast<char*>(&header), sizeof(WavHeader));

    // Validate WAV header
    if (std::strncmp(header.riff, "RIFF", 4) != 0 || std::strncmp(header.wave, "WAVE", 4) != 0) {
        std::cerr << "[ERROR] Invalid WAV file format" << std::endl;
        return false;
    }

    if (header.audioFormat != 1) {
        std::cerr << "[ERROR] Only PCM audio format supported" << std::endl;
        return false;
    }

    if (header.bitsPerSample != 16) {
        std::cerr << "[ERROR] Only 16-bit audio supported" << std::endl;
        return false;
    }

    sampleRate = header.sampleRate;
    channels = header.channels;

    // Read audio data
    size_t numSamples = header.dataSize / sizeof(int16_t);
    samples.resize(numSamples);
    file.read(reinterpret_cast<char*>(samples.data()), header.dataSize);

    file.close();

    std::cout << "[INFO] Loaded WAV file:" << std::endl;
    std::cout << "  Sample Rate: " << sampleRate << " Hz" << std::endl;
    std::cout << "  Channels: " << channels << std::endl;
    std::cout << "  Samples: " << numSamples << std::endl;
    std::cout << "  Duration: " << std::fixed << std::setprecision(2) 
              << (numSamples / (double)(sampleRate * channels)) << " seconds" << std::endl;

    return true;
}

/**
 * Base64 encode audio data
 */
std::string Base64Encode(const uint8_t* data, size_t length) {
    static const char base64_chars[] =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz"
        "0123456789+/";

    std::string result;
    result.reserve(((length + 2) / 3) * 4);

    for (size_t i = 0; i < length; i += 3) {
        uint32_t val = data[i] << 16;
        if (i + 1 < length) val |= data[i + 1] << 8;
        if (i + 2 < length) val |= data[i + 2];

        result += base64_chars[(val >> 18) & 0x3F];
        result += base64_chars[(val >> 12) & 0x3F];
        result += (i + 1 < length) ? base64_chars[(val >> 6) & 0x3F] : '=';
        result += (i + 2 < length) ? base64_chars[val & 0x3F] : '=';
    }

    return result;
}

/**
 * Demo: ASR Streaming with real WAV file
 */
void DemoASRStreaming() {
    std::cout << "\n\n";
    std::cout << "===============================================================" << std::endl;
    std::cout << "           RISE ASR STREAMING DEMO (WAV File)                 " << std::endl;
    std::cout << "===============================================================" << std::endl;
    std::cout << "Stream audio from a WAV file and get speech-to-text transcription\n" << std::endl;

    // Prompt for WAV file path
    std::cout << "Enter path to WAV file (16-bit PCM): ";
    std::string wavPath;
    std::getline(std::cin, wavPath);

    if (wavPath.empty()) {
        std::cout << "\n[CANCELLED] No file specified" << std::endl;
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }

    // Load WAV file
    std::vector<int16_t> audioSamples;
    int sampleRate = 0;
    int channels = 0;

    if (!LoadWavFile(wavPath, audioSamples, sampleRate, channels)) {
        std::cout << "\n[ERROR] Failed to load WAV file" << std::endl;
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }

    // Convert stereo to mono if needed
    if (channels == 2) {
        std::cout << "[INFO] Converting stereo to mono..." << std::endl;
        std::vector<int16_t> mono;
        mono.reserve(audioSamples.size() / 2);
        for (size_t i = 0; i + 1 < audioSamples.size(); i += 2) {
            int32_t avg = (static_cast<int32_t>(audioSamples[i]) + audioSamples[i + 1]) / 2;
            mono.push_back(static_cast<int16_t>(avg));
        }
        audioSamples = mono;
        channels = 1;
    }

    // NOTE: Resampling is NOT needed - the engine handles resampling to 16kHz automatically
    // Client can send audio at any sample rate (e.g. 44.1kHz, 48kHz, etc.)
    std::cout << "[INFO] Audio will be sent at " << sampleRate << " Hz (engine will resample if needed)" << std::endl;

    // Calculate chunk size - must account for base64 encoding AND payload overhead
    // Python uses float32 (4 bytes per sample), not int16 (2 bytes)
    // API has 4096 byte limit. Base64 encoding increases size by 4/3.
    // Format: "CHUNK:ID:16000:base64data" adds ~20 bytes overhead
    // Working backwards: 4096 - 20 = 4076 max base64 bytes
    // 4076 / (4/3) = 3057 max raw bytes = 764 float32 samples
    // Python uses 700 samples per chunk - let's match that
    const int SAFE_SAMPLES_PER_CHUNK = 700;  // Match Python's chunk size
    const int NUM_CHUNKS = (audioSamples.size() + SAFE_SAMPLES_PER_CHUNK - 1) / SAFE_SAMPLES_PER_CHUNK;
    const int chunkBytes = SAFE_SAMPLES_PER_CHUNK * sizeof(float);  // 2800 bytes (float32)
    const int base64Bytes = ((chunkBytes + 2) / 3) * 4;  // ~3734 bytes
    const int totalPayload = base64Bytes + 20;  // ~3754 bytes (well under 4096)
    
    std::cout << "[INFO] Using " << SAFE_SAMPLES_PER_CHUNK << " samples per chunk (~" 
              << (SAFE_SAMPLES_PER_CHUNK * 1000 / 16000) << " ms)" << std::endl;
    std::cout << "[INFO] Estimated payload size: ~" << totalPayload << " bytes (limit: 4096)" << std::endl;

    std::cout << "\n[INFO] Streaming audio for transcription..." << std::endl;
    std::cout << "========================================\n" << std::endl;

    // Drain semaphore before starting
    while (responseCompleteSemaphore.try_acquire()) {}

    // Send audio chunks
    for (int chunkId = 0; chunkId < NUM_CHUNKS; chunkId++) {
        size_t startSample = chunkId * SAFE_SAMPLES_PER_CHUNK;
        size_t endSample = std::min(startSample + SAFE_SAMPLES_PER_CHUNK, audioSamples.size());
        size_t chunkSize = endSample - startSample;

        // Convert int16 samples to float32 (normalized -1.0 to +1.0)
        // This matches Python: pcm_float = [float(s) / 32768.0 for s in pcm_data]
        std::vector<float> floatSamples(chunkSize, 0.0f);  // Initialize to zero
        for (size_t i = 0; i < chunkSize; i++) {
            int16_t sample = audioSamples[startSample + i];
            float floatSample = static_cast<float>(sample) / 32768.0f;
            
            // Validate and clamp the result
            if (std::isnan(floatSample) || std::isinf(floatSample)) {
                std::cerr << "\n[ERROR] Invalid float at index " << i << " from int16 " << sample << std::endl;
                floatSample = 0.0f;  // Replace with silence
            }
            
            // Clamp to valid range
            if (floatSample > 1.0f) floatSample = 1.0f;
            if (floatSample < -1.0f) floatSample = -1.0f;
            
            floatSamples[i] = floatSample;
        }

        // Get float32 bytes
        const uint8_t* chunkData = reinterpret_cast<const uint8_t*>(floatSamples.data());
        size_t chunkBytes = chunkSize * sizeof(float);

        // Encode to base64
        std::string base64Audio = Base64Encode(chunkData, chunkBytes);

        // Reset for this chunk
        {
            std::lock_guard<std::mutex> lock(responseMutex);
            currentResponse.clear();
            responseCompleted = false;
            firstTokenReceived = false;
            callbackFinished = false;
        }

        // Format: "CHUNK:<id>:<sample_rate>:<base64_data>"
        // Note: Sample rate can be anything - engine will resample to 16kHz if needed
        std::string payload = "CHUNK:" + std::to_string(chunkId) + ":" + std::to_string(sampleRate) + ":" + base64Audio;

        // Validate payload size (silent check)
        if (payload.length() >= sizeof(NV_REQUEST_RISE_SETTINGS_V1::content)) {
            std::cerr << "\n[ERROR] Payload too large: " << payload.length() 
                      << " bytes (max: " << sizeof(NV_REQUEST_RISE_SETTINGS_V1::content) << ")" << std::endl;
            break;
        }

        // Setup request
        NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
        requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
        requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
        strncpy_s(requestSettings.content, sizeof(requestSettings.content), 
                  payload.c_str(), payload.length());
        requestSettings.completed = 0;  // More chunks coming

        // Send chunk (silent)
        NvAPI_Status status = NvAPI_RequestRise(&requestSettings);
        if (status != NVAPI_OK) {
            std::cerr << "\n[ERROR] Failed to send audio chunk" << std::endl;
            break;
        }

        // Show spinner while waiting for response (callback will stop it and display text)
        spinnerActive.store(true, std::memory_order_release);
        std::thread spinnerThread([chunkId, NUM_CHUNKS]() {
            const char spinChars[] = { '|', '/', '-', '\\' };
            int idx = 0;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            
            while (spinnerActive.load(std::memory_order_acquire)) {
                // Show progress with spinner
                std::cout << "\r" << spinChars[idx % 4] << " Processing chunk " 
                          << (chunkId + 1) << "/" << NUM_CHUNKS << "...   ";
                std::cout.flush();
                idx++;
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
            
            // Clear spinner when done
            std::cout << "\r\033[K";
            std::cout.flush();
        });

        // Wait for interim response (callback displays it immediately)
        responseCompleteSemaphore.acquire();

        // Stop spinner and wait for it to clean up
        spinnerActive.store(false, std::memory_order_release);
        spinnerThread.join();

        // Small delay between chunks
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    // Send STOP to get final transcription
    std::cout << "\n[INFO] Finalizing transcription..." << std::endl;

    // Drain semaphore
    while (responseCompleteSemaphore.try_acquire()) {}

    {
        std::lock_guard<std::mutex> lock(responseMutex);
        currentResponse.clear();
        responseCompleted = false;
        firstTokenReceived = false;
        callbackFinished = false;
    }

    NV_REQUEST_RISE_SETTINGS_V1 stopSettings = { 0 };
    stopSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    stopSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(stopSettings.content, sizeof(stopSettings.content), "STOP:", 5);
    stopSettings.completed = 0;

    NvAPI_Status status = NvAPI_RequestRise(&stopSettings);
    if (status == NVAPI_OK) {
        // Show spinner while waiting for final transcription
        spinnerActive.store(true, std::memory_order_release);
        std::thread finalSpinnerThread([]() {
            const char spinChars[] = { '|', '/', '-', '\\' };
            int idx = 0;
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            
            while (spinnerActive.load(std::memory_order_acquire)) {
                std::cout << "\r" << spinChars[idx % 4] << " Generating final transcription...   ";
                std::cout.flush();
                idx++;
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
            
            std::cout << "\r" << std::string(60, ' ') << "\r";
            std::cout.flush();
        });

        responseCompleteSemaphore.acquire();

        // Stop spinner
        spinnerActive.store(false, std::memory_order_release);
        finalSpinnerThread.join();

        std::lock_guard<std::mutex> lock(responseMutex);
        if (currentResponse.find("ASR_FINAL:") == 0) {
            std::string finalTranscript = currentResponse.substr(10);
            std::cout << "\n========================================" << std::endl;
            std::cout << "FINAL TRANSCRIPTION:" << std::endl;
            std::cout << "========================================" << std::endl;
            std::cout << finalTranscript << std::endl;
            std::cout << "========================================\n" << std::endl;
        } else if (!currentResponse.empty()) {
            std::cout << "\nFinal: " << currentResponse << std::endl;
        }
    } else {
        std::cerr << "\n[ERROR] Failed to send STOP signal" << std::endl;
    }

    std::cout << "\nPress Enter to continue...";
    std::cin.get();
}


// ============================================================================
// Main Menu
// ============================================================================

void ShowMenu() {
    std::cout << "\n\n";
    std::cout << "===============================================================" << std::endl;
    std::cout << "              RISE C++ Demo Client - Main Menu                " << std::endl;
    std::cout << "===============================================================" << std::endl;
    std::cout << "\n1. LLM Chat Demo (Interactive Streaming)" << std::endl;
    std::cout << "2. ASR Streaming Demo (WAV File)" << std::endl;
    std::cout << "3. Exit" << std::endl;
    std::cout << "\nChoice: ";
}

// ============================================================================
// Main Entry Point
// ============================================================================

int main(int argc, char* argv[]) {
    std::cout << "\n";
    std::cout << "===============================================================" << std::endl;
    std::cout << "           RISE C++ Demo Client v1.0                          " << std::endl;
    std::cout << "     Demonstrating LLM and ASR Streaming Capabilities         " << std::endl;
    std::cout << "===============================================================" << std::endl;

    // Initialize RISE client
    if (!InitializeRiseClient()) {
        std::cerr << "\n[FATAL] Failed to initialize RISE client" << std::endl;
        std::cerr << "Press Enter to exit...";
        std::cin.get();
        return EXIT_FAILURE;
    }

    // Main menu loop
    while (true) {
        ShowMenu();
        
        std::string choice;
        std::getline(std::cin, choice);

        if (choice == "1") {
            DemoLLMChat();
        }
        else if (choice == "2") {
            DemoASRStreaming();
        }
        else if (choice == "3" || choice == "exit" || choice == "quit") {
            std::cout << "\n[GOODBYE] Thank you for using RISE Demo Client!" << std::endl;
            break;
        }
        else {
            std::cout << "\n[ERROR] Invalid choice. Please try again." << std::endl;
            std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        }
    }

    return EXIT_SUCCESS;
}

