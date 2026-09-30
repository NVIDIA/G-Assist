/*
 * G-Assist CLI Tool
 * 
 * A minimal command-line tool that performs:
 * 1. ASR (Automatic Speech Recognition) from a WAV file
 * 2. LLM (Large Language Model) prompt/response
 * 
 * Usage:
 *   gassist_cli.exe --asr <wav_file>
 *   gassist_cli.exe --llm "<prompt>"
 * 
 * Output: Only the final text result is printed to stdout.
 */

#define NOMINMAX

#include <iostream>
#include <string>
#include <mutex>
#include <thread>
#include <condition_variable>
#include <chrono>
#include <vector>
#include <cstring>
#include <atomic>
#include <fstream>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include "nvapi.h"

// ============================================================================
// Synchronization
// ============================================================================

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
// Global State
// ============================================================================

static Semaphore g_responseSemaphore;
static std::mutex g_responseMutex;
static std::string g_finalResult;
static std::string g_chartData;  // Store GRAPH content separately
static bool g_systemReady = false;
static bool g_responseCompleted = false;
static std::atomic<bool> g_waitingForAsrFinal(false);

// Per-content-type completion tracking (bitmask).
// A type becomes "expected" when we first receive data for it and
// "completed" when its callback reports completed==1.  The semaphore
// is only released once every expected type has completed.
static constexpr unsigned CT_TEXT                    = 1u << 0;
static constexpr unsigned CT_CUSTOM_BEHAVIOR         = 1u << 1;
static constexpr unsigned CT_CUSTOM_BEHAVIOR_RESULT  = 1u << 2;
static constexpr unsigned CT_GRAPH                   = 1u << 3;

static unsigned g_expectedTypes  = 0;
static unsigned g_completedTypes = 0;

static bool AllExpectedTypesComplete() {
    return g_expectedTypes != 0 &&
           (g_completedTypes & g_expectedTypes) == g_expectedTypes;
}

// ============================================================================
// WAV File Handling
// ============================================================================

static bool ReadExact(std::ifstream& file, void* buffer, size_t size) {
    file.read(reinterpret_cast<char*>(buffer), static_cast<std::streamsize>(size));
    return static_cast<size_t>(file.gcount()) == size;
}

bool LoadWavFile(const std::string& filename, std::vector<int16_t>& samples, int& sampleRate, int& channels) {
    std::ifstream file(filename, std::ios::binary);
    if (!file.is_open()) {
        return false;
    }

    char riff[4];
    uint32_t chunkSize = 0;
    char wave[4];
    if (!ReadExact(file, riff, 4) || !ReadExact(file, &chunkSize, 4) || !ReadExact(file, wave, 4)) {
        return false;
    }
    if (std::strncmp(riff, "RIFF", 4) != 0 || std::strncmp(wave, "WAVE", 4) != 0) {
        return false;
    }
    (void)chunkSize;
    uint16_t audioFormat = 0;
    uint16_t channelCount = 0;
    uint16_t bitsPerSample = 0;
    uint32_t sampleRateValue = 0;
    uint32_t dataSize = 0;
    std::streampos dataPos = 0;
    bool foundFmt = false;
    bool foundData = false;

    while (file && !(foundFmt && foundData)) {
        char chunkId[4];
        uint32_t subchunkSize = 0;
        if (!ReadExact(file, chunkId, 4) || !ReadExact(file, &subchunkSize, 4)) {
            return false;
        }

        if (std::strncmp(chunkId, "fmt ", 4) == 0) {
            if (subchunkSize < 16) {
                return false;
            }
            if (!ReadExact(file, &audioFormat, 2) ||
                !ReadExact(file, &channelCount, 2) ||
                !ReadExact(file, &sampleRateValue, 4)) {
                return false;
            }
            uint32_t byteRate = 0;
            uint16_t blockAlign = 0;
            if (!ReadExact(file, &byteRate, 4) ||
                !ReadExact(file, &blockAlign, 2) ||
                !ReadExact(file, &bitsPerSample, 2)) {
                return false;
            }
            if (subchunkSize > 16) {
                file.seekg(static_cast<std::streamoff>(subchunkSize - 16), std::ios::cur);
            }
            foundFmt = true;
        } else if (std::strncmp(chunkId, "data", 4) == 0) {
            dataSize = subchunkSize;
            dataPos = file.tellg();
            file.seekg(static_cast<std::streamoff>(subchunkSize), std::ios::cur);
            foundData = true;
        } else {
            file.seekg(static_cast<std::streamoff>(subchunkSize), std::ios::cur);
        }

        if (subchunkSize % 2 == 1) {
            file.seekg(1, std::ios::cur);
        }
    }

    if (!foundFmt || !foundData || audioFormat != 1 || bitsPerSample != 16 || dataSize == 0) {
        return false;
    }
    if (dataSize % sizeof(int16_t) != 0) {
        return false;
    }

    sampleRate = static_cast<int>(sampleRateValue);
    channels = static_cast<int>(channelCount);

    file.clear();
    file.seekg(dataPos);
    if (!file) {
        return false;
    }
    size_t numSamples = dataSize / sizeof(int16_t);
    samples.resize(numSamples);
    if (!ReadExact(file, samples.data(), dataSize)) {
        return false;
    }

    return true;
}

// ============================================================================
// JSON Helpers
// ============================================================================

static std::string EscapeJsonString(const std::string& value) {
    std::string escaped;
    escaped.reserve(value.size() + 8);
    for (unsigned char ch : value) {
        switch (ch) {
            case '"': escaped += "\\\""; break;
            case '\\': escaped += "\\\\"; break;
            case '\b': escaped += "\\b"; break;
            case '\f': escaped += "\\f"; break;
            case '\n': escaped += "\\n"; break;
            case '\r': escaped += "\\r"; break;
            case '\t': escaped += "\\t"; break;
            default:
                if (ch < 0x20) {
                    char buffer[7];
                    std::snprintf(buffer, sizeof(buffer), "\\u%04x", ch);
                    escaped += buffer;
                } else {
                    escaped += static_cast<char>(ch);
                }
                break;
        }
    }
    return escaped;
}

// ============================================================================
// Base64 Encoding
// ============================================================================

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

// ============================================================================
// RISE Callback Handler
// ============================================================================

void RiseCallback(NV_RISE_CALLBACK_DATA_V1* pData) {
    if (!pData) return;

    std::lock_guard<std::mutex> lock(g_responseMutex);

    switch (pData->contentType) {
        case NV_RISE_CONTENT_TYPE_READY:
            if (pData->completed == 1) {
                g_systemReady = true;
            }
            break;

        case NV_RISE_CONTENT_TYPE_TEXT: {
            std::string chunk(pData->content);
            
            if (!chunk.empty()) {
                // Check for ASR responses
                if (chunk.find("ASR_INTERIM:") == 0) {
                    // Ignore interim results
                } else if (chunk.find("ASR_FINAL:") == 0) {
                    // Extract final transcription
                    g_finalResult = chunk.substr(10);
                    if (g_waitingForAsrFinal.load()) {
                        g_responseCompleted = true;
                        g_responseSemaphore.release();
                    }
                } else {
                    // LLM response - accumulate
                    g_finalResult += chunk;
                    g_expectedTypes |= CT_TEXT;
                }
            }

            if (pData->completed == 1) {
                g_completedTypes |= CT_TEXT;
                if (!g_waitingForAsrFinal.load() && AllExpectedTypesComplete()) {
                    g_responseCompleted = true;
                    g_responseSemaphore.release();
                }
            }
            break;
        }

        // Handle CUSTOM_BEHAVIOR - contains JSON tool calls
        case NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR: {
            std::string chunk(pData->content);
            if (!chunk.empty()) {
                g_finalResult += chunk;
                g_expectedTypes |= CT_CUSTOM_BEHAVIOR;
            }
            if (pData->completed == 1) {
                g_completedTypes |= CT_CUSTOM_BEHAVIOR;
                if (AllExpectedTypesComplete()) {
                    g_responseCompleted = true;
                    g_responseSemaphore.release();
                }
            }
            break;
        }

        // Handle CUSTOM_BEHAVIOR_RESULT - contains JSON tool call results
        case NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR_RESULT: {
            std::string chunk(pData->content);
            if (!chunk.empty()) {
                g_finalResult += chunk;
                g_expectedTypes |= CT_CUSTOM_BEHAVIOR_RESULT;
            }
            if (pData->completed == 1) {
                g_completedTypes |= CT_CUSTOM_BEHAVIOR_RESULT;
                if (AllExpectedTypesComplete()) {
                    g_responseCompleted = true;
                    g_responseSemaphore.release();
                }
            }
            break;
        }

        // Handle GRAPH - contains chart/graph data
        case NV_RISE_CONTENT_TYPE_GRAPH: {
            std::string chunk(pData->content);
            if (!chunk.empty()) {
                g_chartData += chunk;
                g_expectedTypes |= CT_GRAPH;
            }
            if (pData->completed == 1) {
                g_completedTypes |= CT_GRAPH;
                if (AllExpectedTypesComplete()) {
                    g_responseCompleted = true;
                    g_responseSemaphore.release();
                }
            }
            break;
        }

        default:
            break;
    }
}

// ============================================================================
// RISE Initialization
// ============================================================================

bool InitializeRise() {
    NvAPI_Status status = NvAPI_Initialize();
    if (status != NVAPI_OK) {
        return false;
    }

    NV_RISE_CALLBACK_SETTINGS_V1 callbackSettings = { 0 };
    callbackSettings.version = NV_RISE_CALLBACK_SETTINGS_VER1;
    callbackSettings.callback = RiseCallback;

    status = NvAPI_RegisterRiseCallback(&callbackSettings);
    if (status != NVAPI_OK) {
        return false;
    }

    // Wait for system ready
    auto startTime = std::chrono::steady_clock::now();
    while (!g_systemReady) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(
            std::chrono::steady_clock::now() - startTime).count();
        if (elapsed > 30) {
            return false;
        }
    }

    return true;
}

// ============================================================================
// ASR Function
// ============================================================================

std::string DoASR(const std::string& wavFilePath) {
    // Load WAV file
    std::vector<int16_t> audioSamples;
    int sampleRate = 0;
    int channels = 0;

    if (!LoadWavFile(wavFilePath, audioSamples, sampleRate, channels)) {
        return "ERROR: Failed to load WAV file";
    }

    // Convert stereo to mono if needed
    if (channels == 2) {
        std::vector<int16_t> mono;
        mono.reserve(audioSamples.size() / 2);
        for (size_t i = 0; i + 1 < audioSamples.size(); i += 2) {
            int32_t avg = (static_cast<int32_t>(audioSamples[i]) + audioSamples[i + 1]) / 2;
            mono.push_back(static_cast<int16_t>(avg));
        }
        audioSamples = mono;
    }

    // Reset state
    {
        std::lock_guard<std::mutex> lock(g_responseMutex);
        g_finalResult.clear();
        g_responseCompleted = false;
        g_expectedTypes  = 0;
        g_completedTypes = 0;
    }
    while (g_responseSemaphore.try_acquire()) {}

    // Send audio chunks
    const int SAMPLES_PER_CHUNK = 700;
    const int NUM_CHUNKS = (audioSamples.size() + SAMPLES_PER_CHUNK - 1) / SAMPLES_PER_CHUNK;

    for (int chunkId = 0; chunkId < NUM_CHUNKS; chunkId++) {
        size_t startSample = chunkId * SAMPLES_PER_CHUNK;
        size_t endSample = std::min(startSample + SAMPLES_PER_CHUNK, audioSamples.size());
        size_t chunkSize = endSample - startSample;

        // Convert to float32
        std::vector<float> floatSamples(chunkSize);
        for (size_t i = 0; i < chunkSize; i++) {
            floatSamples[i] = static_cast<float>(audioSamples[startSample + i]) / 32768.0f;
        }

        // Encode to base64
        const uint8_t* chunkData = reinterpret_cast<const uint8_t*>(floatSamples.data());
        size_t chunkBytes = chunkSize * sizeof(float);
        std::string base64Audio = Base64Encode(chunkData, chunkBytes);

        // Format payload
        std::string payload = "CHUNK:" + std::to_string(chunkId) + ":" + 
                              std::to_string(sampleRate) + ":" + base64Audio;

        // Send chunk
        NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
        requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
        requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
        strncpy_s(requestSettings.content, sizeof(requestSettings.content),
                  payload.c_str(), payload.length());
        requestSettings.completed = 0;

        NvAPI_Status status = NvAPI_RequestRise(&requestSettings);
        if (status != NVAPI_OK) {
            return "ERROR: Failed to send audio chunk";
        }

        // Wait for acknowledgment
        g_responseSemaphore.acquire();
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }

    // Send STOP and wait for final transcription
    g_waitingForAsrFinal.store(true);
    
    {
        std::lock_guard<std::mutex> lock(g_responseMutex);
        g_finalResult.clear();
        g_responseCompleted = false;
        g_expectedTypes  = 0;
        g_completedTypes = 0;
    }
    while (g_responseSemaphore.try_acquire()) {}

    NV_REQUEST_RISE_SETTINGS_V1 stopSettings = { 0 };
    stopSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    stopSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(stopSettings.content, sizeof(stopSettings.content), "STOP:", 5);
    stopSettings.completed = 0;

    NvAPI_Status status = NvAPI_RequestRise(&stopSettings);
    if (status != NVAPI_OK) {
        g_waitingForAsrFinal.store(false);
        return "ERROR: Failed to send STOP command";
    }

    // Wait for ASR_FINAL with timeout
    auto waitStart = std::chrono::steady_clock::now();
    const int TIMEOUT_MS = 15000;
    
    while (true) {
        if (g_responseSemaphore.try_acquire()) {
            break;
        }
        
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - waitStart).count();
        
        if (elapsed >= TIMEOUT_MS) {
            g_waitingForAsrFinal.store(false);
            return "ERROR: Timeout waiting for transcription";
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    g_waitingForAsrFinal.store(false);

    std::lock_guard<std::mutex> lock(g_responseMutex);
    return g_finalResult;
}

// ============================================================================
// LLM Function
// ============================================================================

std::string DoLLM(const std::string& prompt) {
    // Reset state
    {
        std::lock_guard<std::mutex> lock(g_responseMutex);
        g_finalResult.clear();
        g_chartData.clear();
        g_responseCompleted = false;
        g_expectedTypes  = 0;
        g_completedTypes = 0;
    }
    while (g_responseSemaphore.try_acquire()) {}

    // Build JSON request
    std::string jsonRequest = "{\"prompt\":\"" + EscapeJsonString(prompt) +
                              "\",\"context_assist\":{},\"client_config\":{}}";

    if (jsonRequest.length() >= sizeof(NV_REQUEST_RISE_SETTINGS_V1::content)) {
        return "ERROR: LLM prompt too long";
    }

    // Send request
    NV_REQUEST_RISE_SETTINGS_V1 requestSettings = { 0 };
    requestSettings.version = NV_REQUEST_RISE_SETTINGS_VER1;
    requestSettings.contentType = NV_RISE_CONTENT_TYPE_TEXT;
    strncpy_s(requestSettings.content, sizeof(requestSettings.content),
              jsonRequest.c_str(), jsonRequest.length());
    requestSettings.completed = 1;

    NvAPI_Status status = NvAPI_RequestRise(&requestSettings);
    if (status != NVAPI_OK) {
        return "ERROR: Failed to send LLM request";
    }

    // Wait for response with timeout
    auto waitStart = std::chrono::steady_clock::now();
    const int TIMEOUT_MS = 60000;
    
    while (true) {
        if (g_responseSemaphore.try_acquire()) {
            break;
        }
        
        auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - waitStart).count();
        
        if (elapsed >= TIMEOUT_MS) {
            return "ERROR: Timeout waiting for LLM response";
        }
        
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }

    std::lock_guard<std::mutex> lock(g_responseMutex);
    return g_finalResult;
}

// ============================================================================
// Main
// ============================================================================

void PrintUsage(const char* programName) {
    std::cerr << "Usage:" << std::endl;
    std::cerr << "  " << programName << " --asr <wav_file>   Transcribe WAV file to text" << std::endl;
    std::cerr << "  " << programName << " --llm \"<prompt>\"   Send prompt to LLM and get response" << std::endl;
}

int main(int argc, char* argv[]) {
    if (argc < 3) {
        PrintUsage(argv[0]);
        return 1;
    }

    std::string mode = argv[1];
    std::string input = argv[2];

    // Initialize RISE
    if (!InitializeRise()) {
        std::cerr << "ERROR: Failed to initialize RISE" << std::endl;
        return 1;
    }

    std::string result;

    if (mode == "--asr") {
        result = DoASR(input);
    } else if (mode == "--llm") {
        result = DoLLM(input);
    } else {
        PrintUsage(argv[0]);
        return 1;
    }

    // Output the result
    std::cout << result << std::endl;

    // Output chart data if present (on stderr to separate from main result)
    {
        std::lock_guard<std::mutex> lock(g_responseMutex);
        if (!g_chartData.empty()) {
            std::cerr << "[CHART_DATA]" << std::endl;
            std::cerr << g_chartData << std::endl;
        }
    }

    return 0;
}

