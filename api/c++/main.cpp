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

// Prevent Windows min/max macros from conflicting with std::min/std::max
#define NOMINMAX

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
#include <queue>
#include "nvapi.h"

// ============================================================================
// Miniaudio - Single-header audio library for microphone capture
// ============================================================================
#define MINIAUDIO_IMPLEMENTATION
#define MA_NO_DECODING      // We don't need file decoding
#define MA_NO_ENCODING      // We don't need file encoding
#define MA_NO_GENERATION    // We don't need waveform generation
#include "miniaudio.h"

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

// ASR-specific state
std::atomic<bool> waitingForAsrFinal(false);  // When true, only release semaphore on ASR_FINAL
std::string lastAsrFinalResponse;             // Store the ASR_FINAL response

// ============================================================================
// Microphone Capture State (Thread-Safe Audio Buffer)
// ============================================================================

std::mutex micBufferMutex;
std::vector<float> micBuffer;              // Accumulated audio samples from microphone
std::atomic<bool> micCaptureActive(false); // Flag to control capture loop
const int MIC_SAMPLE_RATE = 16000;         // 16kHz for ASR
const int MIC_CHANNELS = 1;                // Mono

// Debug logging flag - set to true to enable detailed mic debug output
static bool g_micDebugLogging = false;
static std::atomic<int> g_callbackCount(0);
static std::chrono::steady_clock::time_point g_micStartTime;
static std::atomic<float> g_lastRms(0.0f);  // Track audio level for warm-up detection

/**
 * Miniaudio callback - called from audio thread when samples are available
 * We copy samples into our buffer for the main thread to consume
 */
void MicrophoneDataCallback(ma_device* pDevice, void* pOutput, const void* pInput, ma_uint32 frameCount) {
    (void)pOutput; // Capture-only, no playback

    int callbackNum = g_callbackCount.fetch_add(1);
    
    if (pInput == nullptr) {
        if (g_micDebugLogging && callbackNum < 10) {
            std::cerr << "[MIC_DEBUG] Callback #" << callbackNum << ": pInput is NULL" << std::endl;
        }
        return;
    }
    
    if (!micCaptureActive.load(std::memory_order_acquire)) {
        if (g_micDebugLogging && callbackNum < 10) {
            std::cerr << "[MIC_DEBUG] Callback #" << callbackNum << ": micCaptureActive is false" << std::endl;
        }
        return;
    }

    const float* inputSamples = static_cast<const float*>(pInput);
    
    // Calculate RMS to check if we have actual audio
    float rms = 0.0f;
    for (ma_uint32 i = 0; i < frameCount; i++) {
        rms += inputSamples[i] * inputSamples[i];
    }
    rms = std::sqrt(rms / frameCount);

    // Store RMS for warm-up detection (atomic for thread safety)
    g_lastRms.store(rms, std::memory_order_release);
    
    std::lock_guard<std::mutex> lock(micBufferMutex);
    size_t bufferSizeBefore = micBuffer.size();
    micBuffer.insert(micBuffer.end(), inputSamples, inputSamples + frameCount);
    
    // Log first few callbacks and periodically after
    if (g_micDebugLogging && (callbackNum < 10 || callbackNum % 100 == 0)) {
        auto now = std::chrono::steady_clock::now();
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - g_micStartTime).count();
        std::cerr << "[MIC_DEBUG] Callback #" << callbackNum 
                  << " @ " << elapsed << "ms"
                  << ": frames=" << frameCount 
                  << ", bufferBefore=" << bufferSizeBefore
                  << ", bufferAfter=" << micBuffer.size()
                  << ", RMS=" << std::fixed << std::setprecision(6) << rms
                  << "\n" << std::flush;
    }
}

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

    // Debug logging for callbacks
    if (g_micDebugLogging) {
        std::string contentStr(pData->content);
        std::string contentPreview = contentStr.length() > 80 ? contentStr.substr(0, 80) + "..." : contentStr;
        // Use \n at end and flush to prevent interleaving with other threads
        std::cerr << "[CALLBACK_DEBUG] Type=" << GetContentTypeName(pData->contentType)
                  << ", Completed=" << (int)pData->completed
                  << ", Content='" << contentPreview << "'"
                  << "\n" << std::flush;
    }

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
            bool isAsrFinal = false;

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
                        isAsrFinal = true;
                        lastAsrFinalResponse = chunk;
                        // Final transcription will be handled separately
                        std::cout << "\r\033[K";  // Clear spinner line
                        std::cout.flush();
                        
                        if (g_micDebugLogging) {
                            std::cerr << "[CALLBACK_DEBUG] *** ASR_FINAL received! ***\n" << std::flush;
                        }
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
                callbackFinished = true;
                
                // If we're waiting for ASR_FINAL, only release semaphore when we get it
                if (waitingForAsrFinal.load(std::memory_order_acquire)) {
                    if (isAsrFinal) {
                        if (g_micDebugLogging) {
                            std::cerr << "[CALLBACK_DEBUG] Releasing semaphore (ASR_FINAL received)\n" << std::flush;
                        }
                        responseCompleteSemaphore.release();
                    } else {
                        if (g_micDebugLogging) {
                            std::cerr << "[CALLBACK_DEBUG] Waiting for ASR_FINAL, NOT releasing semaphore\n" << std::flush;
                        }
                    }
                } else {
                    // Normal mode - release on any completed response
                    responseCompleteSemaphore.release();
                }
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

/**
 * Demo: ASR Streaming with LIVE Microphone
 * Uses miniaudio to capture audio from a user-selected recording device
 */
void DemoASRMicrophone() {
    std::cout << "\n\n";
    std::cout << "===============================================================" << std::endl;
    std::cout << "           RISE ASR STREAMING DEMO (Live Microphone)           " << std::endl;
    std::cout << "===============================================================" << std::endl;

    // -------------------------------------------------------------------------
    // Step 1: Enumerate available microphones
    // -------------------------------------------------------------------------
    ma_context context;
    if (ma_context_init(NULL, 0, NULL, &context) != MA_SUCCESS) {
        std::cerr << "[ERROR] Failed to initialize audio context." << std::endl;
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }

    ma_device_info* pCaptureDevices;
    ma_uint32 captureDeviceCount;
    ma_device_info* pPlaybackDevices;
    ma_uint32 playbackDeviceCount;

    if (ma_context_get_devices(&context, &pPlaybackDevices, &playbackDeviceCount,
                               &pCaptureDevices, &captureDeviceCount) != MA_SUCCESS) {
        std::cerr << "[ERROR] Failed to enumerate audio devices." << std::endl;
        ma_context_uninit(&context);
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }

    if (captureDeviceCount == 0) {
        std::cerr << "[ERROR] No microphones found on this system." << std::endl;
        ma_context_uninit(&context);
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }

    std::cout << "\nAvailable Microphones:" << std::endl;
    std::cout << "----------------------------------------" << std::endl;
    for (ma_uint32 i = 0; i < captureDeviceCount; i++) {
        std::cout << "  [" << i << "] " << pCaptureDevices[i].name;
        if (pCaptureDevices[i].isDefault) {
            std::cout << " (default)";
        }
        std::cout << std::endl;
    }
    std::cout << "----------------------------------------" << std::endl;

    // -------------------------------------------------------------------------
    // Step 2: Let user select a microphone
    // -------------------------------------------------------------------------
    std::cout << "\nEnter microphone number (or press Enter for default): ";
    std::string micChoice;
    std::getline(std::cin, micChoice);

    ma_device_id* pSelectedDeviceId = nullptr;
    std::string selectedDeviceName = "(default)";

    if (!micChoice.empty()) {
        int micIndex = -1;
        try {
            micIndex = std::stoi(micChoice);
        } catch (...) {
            micIndex = -1;
        }

        if (micIndex >= 0 && micIndex < (int)captureDeviceCount) {
            pSelectedDeviceId = &pCaptureDevices[micIndex].id;
            selectedDeviceName = pCaptureDevices[micIndex].name;
        } else {
            std::cout << "[WARN] Invalid selection, using default microphone." << std::endl;
        }
    }

    // -------------------------------------------------------------------------
    // Step 3: Initialize the selected microphone
    // -------------------------------------------------------------------------
    std::cout << "\nStarting real-time transcription..." << std::endl;

    ma_device_config deviceConfig;
    ma_device device;

    deviceConfig = ma_device_config_init(ma_device_type_capture);
    deviceConfig.capture.pDeviceID = pSelectedDeviceId;  // NULL = default, or specific device
    deviceConfig.capture.format    = ma_format_f32;      // Float32 samples
    deviceConfig.capture.channels  = MIC_CHANNELS;       // Mono
    deviceConfig.sampleRate        = MIC_SAMPLE_RATE;    // 16kHz
    deviceConfig.dataCallback      = MicrophoneDataCallback;
    deviceConfig.pUserData         = nullptr;

    if (ma_device_init(&context, &deviceConfig, &device) != MA_SUCCESS) {
        std::cerr << "[ERROR] Failed to initialize microphone device." << std::endl;
        ma_context_uninit(&context);
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }

    std::cout << "[INFO] Microphone: " << device.capture.name << std::endl;
    std::cout << "[INFO] Requested Sample Rate: " << MIC_SAMPLE_RATE << " Hz, Channels: " << MIC_CHANNELS << std::endl;
    std::cout << "[INFO] Actual Device Sample Rate: " << device.sampleRate << " Hz" << std::endl;
    std::cout << "[INFO] Actual Device Format: " << device.capture.format << " (1=u8, 2=s16, 3=s24, 4=s32, 5=f32)" << std::endl;
    
    if (device.sampleRate != MIC_SAMPLE_RATE) {
        std::cout << "[WARN] Sample rate mismatch! Device uses " << device.sampleRate 
                  << " Hz but we requested " << MIC_SAMPLE_RATE << " Hz" << std::endl;
        std::cout << "[WARN] Miniaudio will resample, but quality may be affected" << std::endl;
    }

    // Clear buffer and start capture
    {
        std::lock_guard<std::mutex> lock(micBufferMutex);
        micBuffer.clear();
    }
    
    // Reset counters and RMS tracking
    g_callbackCount.store(0, std::memory_order_release);
    g_lastRms.store(0.0f, std::memory_order_release);
    g_micStartTime = std::chrono::steady_clock::now();
    
    micCaptureActive.store(true, std::memory_order_release);
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] micCaptureActive set to TRUE\n" << std::flush;
    }

    // -------------------------------------------------------------------------
    // Quick mic check: ACTUAL AUDIO must start flowing within 500ms
    // This includes the time for ma_device_start() which can block on Bluetooth
    // -------------------------------------------------------------------------
    const int MIC_READY_TIMEOUT_MS = 500;
    const int CHECK_INTERVAL_MS = 10;
    const float RMS_THRESHOLD = 0.0005f;  // Very low threshold - just needs to be non-silent
    
    // Start timer BEFORE device start (Bluetooth init can take seconds)
    auto checkStart = std::chrono::steady_clock::now();
    
    if (ma_device_start(&device) != MA_SUCCESS) {
        std::cerr << "[ERROR] Failed to start microphone." << std::endl;
        ma_device_uninit(&device);
        std::cout << "Press Enter to continue...";
        std::cin.get();
        return;
    }
    
    auto deviceStartTime = std::chrono::steady_clock::now();
    auto deviceStartMs = std::chrono::duration_cast<std::chrono::milliseconds>(deviceStartTime - checkStart).count();
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] ma_device_start() took " << deviceStartMs << "ms\n" << std::flush;
    }
    
    // If device start already took longer than timeout, reject immediately
    if (deviceStartMs >= MIC_READY_TIMEOUT_MS) {
        std::cout << "\n[ERROR] Microphone did not respond within " << MIC_READY_TIMEOUT_MS << "ms" << std::endl;
        std::cout << "[INFO] Please select a different microphone." << std::endl;
        
        micCaptureActive.store(false, std::memory_order_release);
        ma_device_stop(&device);
        ma_device_uninit(&device);
        ma_context_uninit(&context);
        
        std::cout << "\nPress Enter to continue...";
        std::cin.get();
        return;
    }
    
    // Wait for actual audio (non-silence) to arrive
    int checkIterations = 0;
    while (true) {
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - checkStart).count();
        
        float currentRms = g_lastRms.load(std::memory_order_acquire);
        int callbacks = g_callbackCount.load(std::memory_order_acquire);
        
        // Debug: log every 100ms
        if (g_micDebugLogging && checkIterations % 10 == 0) {
            std::cerr << "[MIC_DEBUG] Check @ " << elapsed << "ms: callbacks=" << callbacks 
                      << ", RMS=" << std::fixed << std::setprecision(6) << currentRms 
                      << ", threshold=" << RMS_THRESHOLD << "\n" << std::flush;
        }
        checkIterations++;
        
        // Check if we have actual audio
        if (currentRms > RMS_THRESHOLD) {
            if (g_micDebugLogging) {
                std::cerr << "[MIC_DEBUG] Audio detected at " << elapsed << "ms with RMS=" << currentRms << "\n" << std::flush;
            }
            break;  // Got real audio!
        }
        
        if (elapsed >= MIC_READY_TIMEOUT_MS) {
            std::cout << "\n[ERROR] Microphone did not respond within " << MIC_READY_TIMEOUT_MS << "ms" << std::endl;
            std::cout << "[INFO] Please select a different microphone." << std::endl;
            
            if (g_micDebugLogging) {
                std::cerr << "[MIC_DEBUG] Final state: callbacks=" << callbacks << ", RMS=" << currentRms << "\n" << std::flush;
            }
            
            micCaptureActive.store(false, std::memory_order_release);
            ma_device_stop(&device);
            ma_device_uninit(&device);
            ma_context_uninit(&context);
            
            std::cout << "\nPress Enter to continue...";
            std::cin.get();
            return;
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(CHECK_INTERVAL_MS));
    }
    
    auto readyTime = std::chrono::steady_clock::now();
    auto readyMs = std::chrono::duration_cast<std::chrono::milliseconds>(readyTime - checkStart).count();
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] Microphone ready in " << readyMs << "ms (RMS=" << g_lastRms.load() << ")\n" << std::flush;
    }

    // Drain semaphore before starting
    while (responseCompleteSemaphore.try_acquire()) {}
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] Semaphore drained, entering main loop\n" << std::flush;
    }
    
    std::cout << "\n========================================" << std::endl;
    std::cout << "Recording... (Press ENTER to stop)" << std::endl;
    std::cout << "========================================\n" << std::endl;

    const int SAMPLES_PER_CHUNK = 700;  // Match WAV demo chunk size (~44ms at 16kHz)
    int chunkId = 0;

    // Thread to check for Enter key press
    std::atomic<bool> stopRequested(false);
    std::thread inputThread([&stopRequested]() {
        std::cin.get();
        stopRequested.store(true, std::memory_order_release);
    });

    // Main loop: pull samples from buffer, send to API
    int loopIteration = 0;
    int waitCount = 0;
    auto loopStartTime = std::chrono::steady_clock::now();
    
    while (!stopRequested.load(std::memory_order_acquire)) {
        std::vector<float> chunkSamples;
        size_t currentBufferSize = 0;

        // Try to get a chunk of samples
        {
            std::lock_guard<std::mutex> lock(micBufferMutex);
            currentBufferSize = micBuffer.size();
            if (micBuffer.size() >= SAMPLES_PER_CHUNK) {
                chunkSamples.assign(micBuffer.begin(), micBuffer.begin() + SAMPLES_PER_CHUNK);
                micBuffer.erase(micBuffer.begin(), micBuffer.begin() + SAMPLES_PER_CHUNK);
            }
        }

        if (chunkSamples.empty()) {
            // Not enough samples yet, wait a bit
            waitCount++;
            if (g_micDebugLogging && (waitCount <= 10 || waitCount % 50 == 0)) {
                auto now = std::chrono::steady_clock::now();
                auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - loopStartTime).count();
                std::cerr << "[MIC_DEBUG] Loop wait #" << waitCount 
                          << " @ " << elapsed << "ms"
                          << ": bufferSize=" << currentBufferSize 
                          << ", need=" << SAMPLES_PER_CHUNK 
                          << ", callbacks=" << g_callbackCount.load()
                          << std::endl;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
            continue;
        }

        loopIteration++;
        
        // Calculate RMS of chunk being sent
        float chunkRms = 0.0f;
        for (const auto& sample : chunkSamples) {
            chunkRms += sample * sample;
        }
        chunkRms = std::sqrt(chunkRms / chunkSamples.size());
        
        if (g_micDebugLogging && (loopIteration <= 5 || loopIteration % 20 == 0)) {
            auto now = std::chrono::steady_clock::now();
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - loopStartTime).count();
            std::cerr << "[MIC_DEBUG] Sending chunk #" << chunkId 
                      << " (loop #" << loopIteration << ")"
                      << " @ " << elapsed << "ms"
                      << ": samples=" << chunkSamples.size()
                      << ", RMS=" << std::fixed << std::setprecision(6) << chunkRms
                      << ", remainingBuffer=" << currentBufferSize - SAMPLES_PER_CHUNK
                      << std::endl;
        }

        // Reset for this chunk
        {
            std::lock_guard<std::mutex> lock(responseMutex);
            currentResponse.clear();
            responseCompleted = false;
            firstTokenReceived = false;
            callbackFinished = false;
        }

        // Encode to base64
        const uint8_t* chunkData = reinterpret_cast<const uint8_t*>(chunkSamples.data());
        size_t chunkBytes = chunkSamples.size() * sizeof(float);
        std::string base64Audio = Base64Encode(chunkData, chunkBytes);

        // Format payload: "CHUNK:<id>:<sample_rate>:<base64_data>"
        std::string payload = "CHUNK:" + std::to_string(chunkId) + ":" + 
                              std::to_string(MIC_SAMPLE_RATE) + ":" + base64Audio;

        // Validate payload size
        if (payload.length() >= sizeof(NV_REQUEST_RISE_SETTINGS_V1::content)) {
            std::cerr << "\n[ERROR] Payload too large: " << payload.length() << " bytes" << std::endl;
            break;
        }

        // Setup and send request
        NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
        requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
        requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
        strncpy_s(requestSettings.content, sizeof(requestSettings.content),
                  payload.c_str(), payload.length());
        requestSettings.completed = 0;  // More chunks coming

        NvAPI_Status status = NvAPI_RequestRise(&requestSettings);
        if (status != NVAPI_OK) {
            std::cerr << "\n[ERROR] Failed to send audio chunk" << std::endl;
            break;
        }

        // Wait for response
        auto waitStart = std::chrono::steady_clock::now();
        responseCompleteSemaphore.acquire();
        auto waitEnd = std::chrono::steady_clock::now();
        
        if (g_micDebugLogging && (loopIteration <= 5 || loopIteration % 20 == 0)) {
            auto waitMs = std::chrono::duration_cast<std::chrono::milliseconds>(waitEnd - waitStart).count();
            std::lock_guard<std::mutex> lock(responseMutex);
            std::cerr << "[MIC_DEBUG] Chunk #" << chunkId << " response received in " << waitMs << "ms"
                      << ", response='" << (currentResponse.length() > 60 ? currentResponse.substr(0, 60) + "..." : currentResponse) << "'"
                      << std::endl;
        }

        chunkId++;
    }
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] Main loop exited: totalChunks=" << chunkId 
                  << ", totalCallbacks=" << g_callbackCount.load() 
                  << std::endl;
    }

    // Stop microphone and clean up
    micCaptureActive.store(false, std::memory_order_release);
    ma_device_stop(&device);
    ma_device_uninit(&device);
    ma_context_uninit(&context);

    // Wait for input thread
    if (inputThread.joinable()) {
        inputThread.detach();  // Don't block if user already pressed Enter
    }

    // Send STOP to get final transcription
    std::cout << "\n[INFO] Finalizing transcription..." << std::endl;

    // IMPORTANT: Set waiting mode FIRST to prevent race conditions with in-flight callbacks
    // Any callbacks that arrive after this will NOT release the semaphore unless they're ASR_FINAL
    waitingForAsrFinal.store(true, std::memory_order_release);
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] STOP phase: waitingForAsrFinal set to TRUE\n" << std::flush;
    }
    
    // Give in-flight callbacks time to complete before draining
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    // Drain semaphore - now safe because new callbacks won't release unless ASR_FINAL
    int drainCount = 0;
    while (responseCompleteSemaphore.try_acquire()) { drainCount++; }
    
    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] STOP phase: drained " << drainCount << " semaphore tokens\n" << std::flush;
    }

    {
        std::lock_guard<std::mutex> lock(responseMutex);
        if (g_micDebugLogging) {
            std::cerr << "[MIC_DEBUG] STOP phase: currentResponse before clear = '" 
                      << (currentResponse.length() > 60 ? currentResponse.substr(0, 60) + "..." : currentResponse)
                      << "'\n" << std::flush;
        }
        currentResponse.clear();
        lastAsrFinalResponse.clear();
        responseCompleted = false;
        firstTokenReceived = false;
        callbackFinished = false;
    }

    NV_REQUEST_RISE_SETTINGS_V1 stopSettings = { 0 };
    stopSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    stopSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(stopSettings.content, sizeof(stopSettings.content), "STOP:", 5);
    stopSettings.completed = 0;

    if (g_micDebugLogging) {
        std::cerr << "[MIC_DEBUG] Sending STOP command (waitingForAsrFinal=true)...\n" << std::flush;
    }
    
    NvAPI_Status status = NvAPI_RequestRise(&stopSettings);
    if (status == NVAPI_OK) {
        if (g_micDebugLogging) {
            std::cerr << "[MIC_DEBUG] STOP sent successfully, waiting for ASR_FINAL (timeout: 10s)...\n" << std::flush;
        }
        
        // Wait for ASR_FINAL with timeout
        auto waitStart = std::chrono::steady_clock::now();
        const int TIMEOUT_MS = 10000;  // 10 second timeout
        bool gotResponse = false;
        
        // Poll with timeout since our semaphore doesn't support timed wait
        while (!gotResponse) {
            // Try to acquire with small sleep intervals
            if (responseCompleteSemaphore.try_acquire()) {
                gotResponse = true;
                break;
            }
            
            auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - waitStart).count();
            
            if (elapsed >= TIMEOUT_MS) {
                if (g_micDebugLogging) {
                    std::cerr << "[MIC_DEBUG] Timeout waiting for ASR_FINAL after " << elapsed << "ms\n" << std::flush;
                }
                break;
            }
            
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
        }
        
        auto waitEnd = std::chrono::steady_clock::now();
        auto waitMs = std::chrono::duration_cast<std::chrono::milliseconds>(waitEnd - waitStart).count();
        
        // Disable ASR_FINAL waiting mode
        waitingForAsrFinal.store(false, std::memory_order_release);
        
        if (g_micDebugLogging) {
            std::cerr << "[MIC_DEBUG] Wait completed in " << waitMs << "ms, gotResponse=" << gotResponse << "\n" << std::flush;
        }

        std::lock_guard<std::mutex> lock(responseMutex);
        
        // Use lastAsrFinalResponse if available, otherwise check currentResponse
        std::string finalResponse = !lastAsrFinalResponse.empty() ? lastAsrFinalResponse : currentResponse;
        
        if (g_micDebugLogging) {
            std::cerr << "[MIC_DEBUG] lastAsrFinalResponse = '" << lastAsrFinalResponse << "'\n" << std::flush;
            std::cerr << "[MIC_DEBUG] currentResponse = '" << currentResponse << "'\n" << std::flush;
            std::cerr << "[MIC_DEBUG] Using finalResponse = '" << finalResponse << "'\n" << std::flush;
        }
        
        if (finalResponse.find("ASR_FINAL:") == 0) {
            std::string finalTranscript = finalResponse.substr(10);
            std::cout << "\n========================================" << std::endl;
            std::cout << "FINAL TRANSCRIPTION:" << std::endl;
            std::cout << "========================================" << std::endl;
            std::cout << finalTranscript << std::endl;
            std::cout << "========================================\n" << std::endl;
        } else if (!finalResponse.empty()) {
            std::cout << "\nFinal: " << finalResponse << std::endl;
        } else {
            std::cout << "\n[WARN] No transcription received (timeout or no speech detected)" << std::endl;
            if (g_micDebugLogging) {
                std::cerr << "[MIC_DEBUG] WARNING: Final response was empty!\n" << std::flush;
            }
        }
    } else {
        std::cerr << "\n[ERROR] Failed to send STOP signal (status=" << status << ")" << std::endl;
    }
    
    // Ensure flag is reset
    waitingForAsrFinal.store(false, std::memory_order_release);

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
    std::cout << "3. ASR Streaming Demo (Live Microphone)" << std::endl;
    std::cout << "4. Exit" << std::endl;
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
        else if (choice == "3") {
            DemoASRMicrophone();
        }
        else if (choice == "4" || choice == "exit" || choice == "quit") {
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

