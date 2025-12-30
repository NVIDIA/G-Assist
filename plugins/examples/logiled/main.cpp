/*
 * SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 * http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

// LogiLED Plugin - Protocol V2 (JSON-RPC 2.0)
// Uses G-Assist SDK for simplified implementation

#include <nlohmann/json.hpp>
#include "gassist_sdk.hpp"
#include "LogitechLEDLib.h"

#include <Windows.h>
#include <TlHelp32.h>
#include <chrono>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <format>
#include <map>
#include <string>

using json = nlohmann::json;
namespace fs = std::filesystem;

// ============================================================================
// Configuration Structures
// ============================================================================

struct PluginConfig {
    bool useSetupWizard = false;
    bool setupComplete = true;
    bool restoreOnShutdown = true;
    bool allowKeyboard = true;
    bool allowMouse = true;
    bool allowHeadset = true;
};

struct Color {
    int red;
    int green;
    int blue;
};

struct PluginState {
    bool initialized = false;
    bool wizardActive = false;
    PluginConfig config;
};

// ============================================================================
// File Path Helpers
// ============================================================================

fs::path GetPluginDirectory() {
    wchar_t buffer[MAX_PATH];
    DWORD length = GetEnvironmentVariableW(L"PROGRAMDATA", buffer, MAX_PATH);
    fs::path base = length ? fs::path(std::wstring(buffer, buffer + length)) : fs::path(L".");
    return base / L"NVIDIA Corporation" / L"nvtopps" / L"rise" / L"plugins" / L"logiled";
}

fs::path GetConfigPath() {
    return GetPluginDirectory() / "config.json";
}

// ============================================================================
// G Hub Diagnostics
// ============================================================================

bool CheckLogiDllAvailable() {
    HMODULE hModule = LoadLibraryA("LogitechLED.dll");
    if (hModule) {
        FreeLibrary(hModule);
        return true;
    }
    return false;
}

bool IsGHubRunning() {
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE) return false;
    
    PROCESSENTRY32W entry;
    entry.dwSize = sizeof(entry);
    
    bool found = false;
    if (Process32FirstW(snapshot, &entry)) {
        do {
            if (_wcsicmp(entry.szExeFile, L"lghub.exe") == 0 ||
                _wcsicmp(entry.szExeFile, L"lghub_agent.exe") == 0) {
                found = true;
                break;
            }
        } while (Process32NextW(snapshot, &entry));
    }
    
    CloseHandle(snapshot);
    return found;
}

// ============================================================================
// Configuration Management
// ============================================================================

json BuildConfigJson(const PluginConfig& config) {
    return json{
        { "features", {
            { "use_setup_wizard", config.useSetupWizard },
            { "setup_complete", config.setupComplete },
            { "restore_on_shutdown", config.restoreOnShutdown },
            { "allow_keyboard", config.allowKeyboard },
            { "allow_mouse", config.allowMouse },
            { "allow_headset", config.allowHeadset }
        }}
    };
}

void SaveDefaultConfig() {
    PluginConfig defaults;
    fs::create_directories(GetPluginDirectory());
    std::ofstream stream(GetConfigPath());
    stream << BuildConfigJson(defaults).dump(2);
}

PluginConfig LoadConfig() {
    PluginConfig config;
    fs::path path = GetConfigPath();
    
    if (!fs::exists(path)) {
        SaveDefaultConfig();
        return config;
    }

    try {
        std::ifstream stream(path);
        json data = json::parse(stream, nullptr, true, true);
        json features = data.value("features", json::object());
        
        config.useSetupWizard = features.value("use_setup_wizard", false);
        config.setupComplete = features.value("setup_complete", true);
        config.restoreOnShutdown = features.value("restore_on_shutdown", true);
        config.allowKeyboard = features.value("allow_keyboard", true);
        config.allowMouse = features.value("allow_mouse", true);
        config.allowHeadset = features.value("allow_headset", true);
    }
    catch (const std::exception&) {
        SaveDefaultConfig();
        config = PluginConfig{};
    }

    return config;
}

// ============================================================================
// Color Conversion Helpers
// ============================================================================

std::string ToLower(std::string str) {
    std::transform(str.begin(), str.end(), str.begin(),
        [](unsigned char c) { return std::tolower(c); });
    return str;
}

Color GetRgbValue(const std::string& color) {
    static const std::map<std::string, Color> colorMap {
        { "red", Color{ 255, 0, 0 }},
        { "green", Color{ 0, 255, 0 }},
        { "blue", Color{ 0, 0, 255 }},
        { "cyan", Color{ 0, 255, 255 }},
        { "magenta", Color{ 255, 0, 255 }},
        { "yellow", Color{ 255, 255, 0 }},
        { "black", Color{ 0, 0, 0 }},
        { "white", Color{ 255, 255, 255 }},
        { "grey", Color{ 128, 128, 128 }},
        { "gray", Color{ 128, 128, 128 }},
        { "orange", Color{ 255, 165, 0 }},
        { "purple", Color{ 128, 0, 128 }},
        { "violet", Color{ 128, 0, 128 }},
        { "pink", Color{ 255, 192, 203 }},
        { "teal", Color{ 0, 128, 128 }},
        { "brown", Color{ 165, 42, 42 }},
        { "ice_blue", Color{ 173, 216, 230 }},
        { "crimson", Color{ 220, 20, 60 }},
        { "gold", Color{ 255, 215, 0 }},
        { "neon_green", Color{ 57, 255, 20 }}
    };

    std::string key = ToLower(color);
    auto it = colorMap.find(key);
    if (it == colorMap.end()) {
        throw std::runtime_error("Unknown color: " + color);
    }
    return it->second;
}

Color ToSdkColor(const Color& color) {
    auto toPercentage = [](int value) {
        return static_cast<int>(std::round(static_cast<double>(value) * 100.0 / 255.0));
    };

    return Color{
        toPercentage(color.red),
        toPercentage(color.green),
        toPercentage(color.blue)
    };
}

// ============================================================================
// LED Control Functions
// ============================================================================

// Pre-flight check helper - throws descriptive error if G Hub is not running
void EnsureGHubAvailable() {
    if (!IsGHubRunning()) {
        throw std::runtime_error(
            "Logitech G Hub is not running. Ensure G Hub is running and try again.");
    }
    // Note: We don't check DLL availability here - LogiLedInit() is the definitive check
    // The DLL check was unreliable because it could fail even when G Hub was starting up
}

bool SetDeviceLighting(LogiLed::DeviceType device, const Color& color) {
    const int MAX_ZONES = 10;
    for (int zone = 0; zone < MAX_ZONES; ++zone) {
        if (!LogiLedSetLightingForTargetZone(device, zone, color.red, color.green, color.blue)) {
            if (zone == 0) {
                return false; // First zone failed
            }
            break; // No more zones
        }
    }
    return true;
}

Color ParseColorParameter(const std::string& colorParam) {
    std::string color = ToLower(colorParam);
    
    // Handle "off" command
    if (color == "off") {
        return Color{ 0, 0, 0 };
    }
    
    // Get RGB value and convert to SDK percentages
    Color rawRgb = GetRgbValue(color);
    return ToSdkColor(rawRgb);
}

// ============================================================================
// Setup Wizard
// ============================================================================

bool ConfigRequiresSetup(const PluginConfig& config) {
    return config.useSetupWizard && !config.setupComplete;
}

std::string BuildSetupInstructions(const std::string& reason = "") {
    std::string instructions = "LOGITECH LIGHTING SETUP\n=======================\n";
    if (!reason.empty()) {
        instructions += reason + "\n\n";
    }
    instructions += std::format(
        "1. Open the configuration file:\n   {}\n"
        "2. Ensure Logitech G Hub is installed and 'Game lighting control' is enabled in Settings.\n"
        "3. Set \"features.setup_complete\" to true and save the file.\n"
        "4. Type 'done' here once finished.\n",
        GetConfigPath().string());
    return instructions;
}

// ============================================================================
// Main Entry Point
// ============================================================================

int main() {
    // Early startup logging to confirm plugin started (before any SDK calls)
    try {
        fs::create_directories(GetPluginDirectory());
        std::ofstream startup_log(GetPluginDirectory() / "startup.log", std::ios::app);
        auto now = std::chrono::system_clock::now();
        auto time_t_now = std::chrono::system_clock::to_time_t(now);
        char time_buffer[26];
        ctime_s(time_buffer, sizeof(time_buffer), &time_t_now);
        startup_log << "Plugin starting at " << time_buffer;
        startup_log << "  DLL available: " << (CheckLogiDllAvailable() ? "yes" : "no") << std::endl;
        startup_log << "  G Hub running: " << (IsGHubRunning() ? "yes" : "no") << std::endl;
        startup_log.flush();
    } catch (...) {
        // Ignore logging errors - don't let logging prevent plugin from starting
    }

    // Create plugin with Protocol V2 SDK
    gassist::Plugin plugin("logiled", "2.0.0",
        "Control Logitech RGB lighting devices including keyboards, mice, and headsets.");

    // Plugin state
    PluginState state;
    state.config = LoadConfig();

    // ========================================================================
    // Initialize Command
    // ========================================================================
    plugin.command("initialize", [&](const json& args) -> json {
        state.config = LoadConfig();

        // Check if setup wizard is required
        if (ConfigRequiresSetup(state.config)) {
            state.wizardActive = true;
            plugin.set_keep_session(true);
            return BuildSetupInstructions();
        }

        // Pre-flight check: ensure G Hub is available
        EnsureGHubAvailable();

        // Initialize Logitech LED SDK
        state.initialized = LogiLedInit();
        if (!state.initialized) {
            throw std::runtime_error(
                "Oops! The Logitech Illumination Plugin for G-Assist couldn't update your lighting. To fix this:\n"
                "1. Ensure Logitech G Hub is installed and running.\n"
                "2. In G Hub, go to Settings > General Settings and enable 'Game lighting control'.\n"
                "3. In Windows, go to Settings > Personalization > Dynamic Lighting and disable 'Use Dynamic Lighting on my devices.'\n"
                "4. Close and reopen G-Assist.\n");
        }

        return "Logitech illumination ready.";
    });

    // ========================================================================
    // Shutdown Command (called automatically by SDK)
    // ========================================================================
    plugin.command("shutdown", [&](const json& args) -> json {
        if (state.initialized && state.config.restoreOnShutdown) {
            LogiLedRestoreLighting();
        }
        LogiLedShutdown();
        state.initialized = false;
        return "LogiLed plugin shutdown complete.";
    });

    // ========================================================================
    // Keyboard Lighting Command
    // ========================================================================
    plugin.command("logi_change_keyboard_lights", [&](const json& args) -> json {
        // Check if keyboard control is allowed
        if (!state.config.allowKeyboard) {
            return "Keyboard control is disabled in the configuration.";
        }

        // Pre-flight check: ensure G Hub is available
        EnsureGHubAvailable();

        // Ensure SDK is initialized
        if (!state.initialized) {
            state.initialized = LogiLedInit();
            if (!state.initialized) {
                throw std::runtime_error("Failed to initialize Logitech LED SDK. Ensure 'Game lighting control' is enabled in G Hub, or restart G Hub.");
            }
        }

        // Parse color parameter
        std::string colorParam = args.value("color", "white");
        Color sdkColor = ParseColorParameter(colorParam);

        // Set lighting
        if (SetDeviceLighting(LogiLed::DeviceType::Keyboard, sdkColor)) {
            return "Logitech keyboard lighting updated.";
        } else {
            throw std::runtime_error("Failed to update lighting for the Logitech keyboard.");
        }
    });

    // ========================================================================
    // Mouse Lighting Command
    // ========================================================================
    plugin.command("logi_change_mouse_lights", [&](const json& args) -> json {
        // Check if mouse control is allowed
        if (!state.config.allowMouse) {
            return "Mouse control is disabled in the configuration.";
        }

        // Pre-flight check: ensure G Hub is available
        EnsureGHubAvailable();

        // Ensure SDK is initialized
        if (!state.initialized) {
            state.initialized = LogiLedInit();
            if (!state.initialized) {
                throw std::runtime_error("Failed to initialize Logitech LED SDK. Ensure 'Game lighting control' is enabled in G Hub, or restart G Hub.");
            }
        }

        // Parse color parameter
        std::string colorParam = args.value("color", "white");
        Color sdkColor = ParseColorParameter(colorParam);

        // Set lighting
        if (SetDeviceLighting(LogiLed::DeviceType::Mouse, sdkColor)) {
            return "Logitech mouse lighting updated.";
        } else {
            throw std::runtime_error("Failed to update lighting for the Logitech mouse.");
        }
    });

    // ========================================================================
    // Headphone/Headset Lighting Command
    // ========================================================================
    plugin.command("logi_change_headphone_lights", [&](const json& args) -> json {
        // Check if headset control is allowed
        if (!state.config.allowHeadset) {
            return "Headset control is disabled in the configuration.";
        }

        // Pre-flight check: ensure G Hub is available
        EnsureGHubAvailable();

        // Ensure SDK is initialized
        if (!state.initialized) {
            state.initialized = LogiLedInit();
            if (!state.initialized) {
                throw std::runtime_error("Failed to initialize Logitech LED SDK. Ensure 'Game lighting control' is enabled in G Hub, or restart G Hub.");
            }
        }

        // Parse color parameter
        std::string colorParam = args.value("color", "white");
        Color sdkColor = ParseColorParameter(colorParam);

        // Set lighting
        if (SetDeviceLighting(LogiLed::DeviceType::Headset, sdkColor)) {
            return "Logitech headset lighting updated.";
        } else {
            throw std::runtime_error("Failed to update lighting for the Logitech headset.");
        }
    });

    // ========================================================================
    // User Input Handler (for setup wizard)
    // ========================================================================
    plugin.command("on_input", [&](const json& args) -> json {
        if (!state.wizardActive) {
            return "No setup is currently in progress.";
        }

        // Reload configuration
        state.config = LoadConfig();

        // Check if setup is complete
        if (ConfigRequiresSetup(state.config)) {
            plugin.set_keep_session(true);
            return BuildSetupInstructions("Configuration still incomplete.");
        }

        // Setup complete, initialize SDK
        state.initialized = LogiLedInit();
        if (!state.initialized) {
            throw std::runtime_error("Failed to initialize Logitech LED SDK. Ensure 'Game lighting control' is enabled in G Hub, or restart G Hub.");
        }

        state.wizardActive = false;
        plugin.set_keep_session(false);
        return "Setup complete! Logitech lighting control is now active.";
    });

    // ========================================================================
    // Run the plugin (SDK handles ping/pong automatically!)
    // ========================================================================
    plugin.run();

    // Cleanup on exit
    if (state.initialized && state.config.restoreOnShutdown) {
        LogiLedRestoreLighting();
    }
    LogiLedShutdown();

    return 0;
}
