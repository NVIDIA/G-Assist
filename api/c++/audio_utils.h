/*
 * Audio Utilities Header
 * 
 * This header provides example utility functions for working with audio data
 * in the context of ASR (Automatic Speech Recognition) streaming.
 * 
 * NOTE: These are example/placeholder implementations to demonstrate the concepts.
 * For production use, you would integrate with actual audio libraries like:
 * - PortAudio (cross-platform)
 * - RtAudio (real-time audio)
 * - Windows WASAPI (native Windows)
 * - DirectSound (legacy Windows)
 */

#pragma once

#include <vector>
#include <string>
#include <cstdint>
#include <algorithm>

namespace AudioUtils {

// ============================================================================
// Audio Format Constants
// ============================================================================

constexpr int DEFAULT_SAMPLE_RATE = 16000;      // 16 kHz (common for ASR)
constexpr int DEFAULT_CHANNELS = 1;              // Mono
constexpr int DEFAULT_BITS_PER_SAMPLE = 16;     // 16-bit PCM
constexpr int DEFAULT_CHUNK_SIZE_MS = 1000;     // 1 second chunks

// ============================================================================
// Audio Data Structures
// ============================================================================

/**
 * Represents audio format specifications
 */
struct AudioFormat {
    int sampleRate;       // Samples per second (Hz)
    int channels;         // Number of channels (1=mono, 2=stereo)
    int bitsPerSample;    // Bits per sample (8, 16, 24, 32)
    
    AudioFormat(int rate = DEFAULT_SAMPLE_RATE,
                int chan = DEFAULT_CHANNELS,
                int bits = DEFAULT_BITS_PER_SAMPLE)
        : sampleRate(rate), channels(chan), bitsPerSample(bits) {}
    
    // Calculate bytes per second
    int BytesPerSecond() const {
        return sampleRate * channels * (bitsPerSample / 8);
    }
    
    // Calculate bytes for a duration in milliseconds
    int BytesForDuration(int milliseconds) const {
        return (BytesPerSecond() * milliseconds) / 1000;
    }
};

/**
 * Represents a chunk of audio data
 */
struct AudioChunk {
    std::vector<int16_t> samples;  // PCM samples (16-bit)
    AudioFormat format;
    int chunkId;
    
    AudioChunk(int id = 0) : chunkId(id), format() {}
    
    size_t SizeInBytes() const {
        return samples.size() * sizeof(int16_t);
    }
    
    int DurationMs() const {
        if (format.sampleRate == 0) return 0;
        return (samples.size() * 1000) / (format.sampleRate * format.channels);
    }
};

// ============================================================================
// Base64 Encoding (for API transmission)
// ============================================================================

/**
 * Base64 encoding table
 */
static const char base64_chars[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+/";

/**
 * Encode binary data to Base64 string
 * This is required for sending audio data over the RISE API
 */
inline std::string Base64Encode(const uint8_t* data, size_t length) {
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
 * Encode audio chunk to Base64 for API transmission
 */
inline std::string EncodeAudioChunk(const AudioChunk& chunk) {
    const uint8_t* data = reinterpret_cast<const uint8_t*>(chunk.samples.data());
    size_t size = chunk.SizeInBytes();
    return Base64Encode(data, size);
}

// ============================================================================
// Audio Processing Utilities
// ============================================================================

/**
 * Normalize audio samples to prevent clipping
 */
inline void NormalizeSamples(std::vector<int16_t>& samples) {
    if (samples.empty()) return;
    
    // Find max absolute value
    int16_t maxVal = 0;
    for (int16_t sample : samples) {
        maxVal = std::max(maxVal, static_cast<int16_t>(std::abs(sample)));
    }
    
    // Normalize if needed
    if (maxVal > 0 && maxVal < INT16_MAX) {
        float scale = static_cast<float>(INT16_MAX) / maxVal;
        for (int16_t& sample : samples) {
            sample = static_cast<int16_t>(sample * scale);
        }
    }
}

/**
 * Apply simple low-pass filter to reduce high-frequency noise
 */
inline void ApplyLowPassFilter(std::vector<int16_t>& samples, float alpha = 0.3f) {
    if (samples.size() < 2) return;
    
    for (size_t i = 1; i < samples.size(); i++) {
        samples[i] = static_cast<int16_t>(
            alpha * samples[i] + (1.0f - alpha) * samples[i - 1]
        );
    }
}

/**
 * Detect voice activity (simple energy-based)
 * Returns true if the chunk likely contains speech
 */
inline bool DetectVoiceActivity(const AudioChunk& chunk, int16_t threshold = 1000) {
    if (chunk.samples.empty()) return false;
    
    // Calculate RMS energy
    int64_t sumSquares = 0;
    for (int16_t sample : chunk.samples) {
        sumSquares += static_cast<int64_t>(sample) * sample;
    }
    
    int16_t rms = static_cast<int16_t>(
        std::sqrt(sumSquares / chunk.samples.size())
    );
    
    return rms > threshold;
}

/**
 * Resample audio to target sample rate (simple linear interpolation)
 * NOTE: For production, use a proper resampling library (libsamplerate, etc.)
 */
inline std::vector<int16_t> ResampleAudio(
    const std::vector<int16_t>& input,
    int inputRate,
    int outputRate)
{
    if (inputRate == outputRate) return input;
    if (input.empty()) return {};
    
    size_t outputSize = (input.size() * outputRate) / inputRate;
    std::vector<int16_t> output(outputSize);
    
    float ratio = static_cast<float>(inputRate) / outputRate;
    for (size_t i = 0; i < outputSize; i++) {
        float srcIdx = i * ratio;
        size_t idx0 = static_cast<size_t>(srcIdx);
        size_t idx1 = std::min(idx0 + 1, input.size() - 1);
        float frac = srcIdx - idx0;
        
        output[i] = static_cast<int16_t>(
            input[idx0] * (1.0f - frac) + input[idx1] * frac
        );
    }
    
    return output;
}

/**
 * Convert stereo to mono by averaging channels
 */
inline std::vector<int16_t> StereoToMono(const std::vector<int16_t>& stereo) {
    std::vector<int16_t> mono;
    mono.reserve(stereo.size() / 2);
    
    for (size_t i = 0; i + 1 < stereo.size(); i += 2) {
        int32_t avg = (static_cast<int32_t>(stereo[i]) + stereo[i + 1]) / 2;
        mono.push_back(static_cast<int16_t>(avg));
    }
    
    return mono;
}

// ============================================================================
// Audio Capture Helpers (Stub Implementations)
// ============================================================================

/**
 * Audio capture interface (abstract)
 * In production, this would interface with PortAudio, WASAPI, etc.
 */
class IAudioCapture {
public:
    virtual ~IAudioCapture() = default;
    
    virtual bool Initialize(const AudioFormat& format) = 0;
    virtual bool Start() = 0;
    virtual bool Stop() = 0;
    virtual bool IsCapturing() const = 0;
    virtual AudioChunk GetNextChunk(int durationMs) = 0;
};

/**
 * Simulated audio capture (for testing)
 * Generates sine wave audio data
 */
class SimulatedAudioCapture : public IAudioCapture {
private:
    AudioFormat format_;
    bool capturing_;
    int chunkCounter_;
    double phase_;
    
public:
    SimulatedAudioCapture() 
        : capturing_(false), chunkCounter_(0), phase_(0.0) {}
    
    bool Initialize(const AudioFormat& format) override {
        format_ = format;
        return true;
    }
    
    bool Start() override {
        capturing_ = true;
        chunkCounter_ = 0;
        return true;
    }
    
    bool Stop() override {
        capturing_ = false;
        return true;
    }
    
    bool IsCapturing() const override {
        return capturing_;
    }
    
    AudioChunk GetNextChunk(int durationMs) override {
        AudioChunk chunk(chunkCounter_++);
        chunk.format = format_;
        
        // Calculate number of samples
        int numSamples = (format_.sampleRate * durationMs) / 1000;
        chunk.samples.reserve(numSamples);
        
        // Generate sine wave (440 Hz "A" note)
        double frequency = 440.0;
        double increment = (2.0 * 3.14159265358979323846 * frequency) / format_.sampleRate;
        
        for (int i = 0; i < numSamples; i++) {
            int16_t sample = static_cast<int16_t>(
                std::sin(phase_) * 10000.0  // Amplitude
            );
            chunk.samples.push_back(sample);
            phase_ += increment;
            
            // Keep phase in range [0, 2*PI]
            if (phase_ >= 2.0 * 3.14159265358979323846) {
                phase_ -= 2.0 * 3.14159265358979323846;
            }
        }
        
        return chunk;
    }
};

// ============================================================================
// File I/O Helpers
// ============================================================================

/**
 * Simple WAV file header structure
 */
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
 * Load PCM data from a WAV file
 * NOTE: Simplified implementation, assumes 16-bit PCM WAV
 */
inline bool LoadWavFile(const std::string& filename, AudioChunk& chunk) {
    // In production, use a proper WAV library
    // This is a simplified example
    
    // TODO: Implement actual file reading
    // For now, return false to indicate not implemented
    return false;
}

/**
 * Save audio chunk to WAV file (for debugging)
 */
inline bool SaveWavFile(const std::string& filename, const AudioChunk& chunk) {
    // In production, use a proper WAV library
    // This is a simplified example
    
    // TODO: Implement actual file writing
    // For now, return false to indicate not implemented
    return false;
}

// ============================================================================
// Example Usage Comments
// ============================================================================

/*
EXAMPLE 1: Capture and send audio to ASR

    // Initialize audio capture
    SimulatedAudioCapture capture;
    AudioFormat format(16000, 1, 16);  // 16kHz mono 16-bit
    capture.Initialize(format);
    capture.Start();
    
    // Capture and send chunks
    for (int i = 0; i < 5; i++) {
        AudioChunk chunk = capture.GetNextChunk(1000);  // 1 second
        
        // Optional: Apply voice activity detection
        if (DetectVoiceActivity(chunk)) {
            // Encode to base64
            std::string encoded = EncodeAudioChunk(chunk);
            
            // Send to RISE ASR
            SendASRChunk(i, encoded, format.sampleRate, false);
        }
    }
    
    capture.Stop();
    SendASRStop();  // Get final transcription

EXAMPLE 2: Process audio before sending

    AudioChunk chunk = capture.GetNextChunk(1000);
    
    // Normalize audio levels
    NormalizeSamples(chunk.samples);
    
    // Apply noise reduction
    ApplyLowPassFilter(chunk.samples);
    
    // Resample if needed (e.g., from 48kHz to 16kHz)
    chunk.samples = ResampleAudio(chunk.samples, 48000, 16000);
    chunk.format.sampleRate = 16000;
    
    // Encode and send
    std::string encoded = EncodeAudioChunk(chunk);
    SendASRChunk(chunkId, encoded, chunk.format.sampleRate, false);

EXAMPLE 3: Convert stereo file to mono for ASR

    AudioChunk stereoChunk = LoadFromFile("input.wav");
    std::vector<int16_t> mono = StereoToMono(stereoChunk.samples);
    
    AudioChunk monoChunk;
    monoChunk.samples = mono;
    monoChunk.format.channels = 1;
    
    std::string encoded = EncodeAudioChunk(monoChunk);
    SendASRChunk(0, encoded, monoChunk.format.sampleRate, false);
*/

} // namespace AudioUtils

