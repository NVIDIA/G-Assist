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
 *
 * Corsair iCUE Extended Plugin for G-Assist (Protocol V2)
 *
 * Full-featured plugin that controls Corsair devices including lighting, DPI,
 * EQ, cooling presets, profiles, and actions.
 */

#include <algorithm>
#include <cctype>
#include <chrono>
#include <ctime>
#include <format>
#include <fstream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>

#include <Windows.h>

#include "gassist_sdk.hpp"
#include "AutomationSDK/iCUEAutomationSDK.h"
#include "iCUESDK/iCUESDK.h"

using json = nlohmann::json;

// ============================================================================
// Logging
// ============================================================================

static std::ofstream g_logFile;
static std::mutex g_logMutex;

static std::string getExeDirectory() {
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    std::string exePath(path);
    size_t pos = exePath.find_last_of("\\/");
    return (pos != std::string::npos) ? exePath.substr(0, pos) : ".";
}

static void initLogging() {
    std::string logPath = getExeDirectory() + "\\corsair-ext.log";
    g_logFile.open(logPath, std::ios::out | std::ios::app);
    if (g_logFile.is_open()) {
        g_logFile << "\n========== Plugin Started ==========\n";
        g_logFile.flush();
    }
}

static void logMsg(const std::string& msg) {
    std::lock_guard<std::mutex> lock(g_logMutex);
    if (!g_logFile.is_open()) return;
    
    auto now = std::chrono::system_clock::now();
    auto time = std::chrono::system_clock::to_time_t(now);
    char timeBuf[32];
    struct tm tmBuf;
    localtime_s(&tmBuf, &time);
    strftime(timeBuf, sizeof(timeBuf), "%H:%M:%S", &tmBuf);
    
    g_logFile << "[" << timeBuf << "] " << msg << "\n";
    g_logFile.flush();
}

// ============================================================================
// Data Types
// ============================================================================

/**
 * Data structure to hold the RGBA values of a color.
 */
struct Color {
    int red;
    int green;
    int blue;
    int alpha;
};

// ============================================================================
// Global State
// ============================================================================

bool g_isInitialized = false;
CorsairDeviceInfo g_devices[CORSAIR_DEVICE_COUNT_MAX];
int g_numDevices = 0;
gassist::Plugin* g_plugin = nullptr;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Returns the string converted to lower case.
 */
static std::string toLowerCase(const std::string& s)
{
    std::string lower = s;
    std::transform(lower.begin(), lower.end(), lower.begin(),
        [](unsigned char c) { return std::tolower(c); });
    return lower;
}

/**
 * Finds a device by name with fuzzy matching, or returns the first device if no name provided.
 * Returns the index of the matching device, or -1 if not found.
 * If deviceName is empty, returns 0 (first device) if any devices exist.
 */
template<typename T>
static int findDeviceByName(const T* devices, int size, const std::string& deviceName)
{
    if (size <= 0) return -1;
    
    // If no device name specified, auto-detect first device
    if (deviceName.empty()) {
        return 0;
    }
    
    std::string lowerName = toLowerCase(deviceName);
    
    // First try exact match (case-insensitive)
    for (int i = 0; i < size; ++i) {
        if (toLowerCase(devices[i].name) == lowerName) {
            return i;
        }
    }
    
    // Then try partial match (device name contains search term or vice versa)
    for (int i = 0; i < size; ++i) {
        std::string deviceLower = toLowerCase(devices[i].name);
        if (deviceLower.find(lowerName) != std::string::npos ||
            lowerName.find(deviceLower) != std::string::npos) {
            return i;
        }
    }
    
    // If still not found and only one device exists, use it
    if (size == 1) {
        return 0;
    }
    
    return -1;
}

/**
 * Gets the device name from params, or returns empty string for auto-detection.
 */
static std::string getDeviceNameParam(const json& params, const std::string& key = "deviceName")
{
    if (params.contains(key) && params[key].is_string()) {
        return params[key].get<std::string>();
    }
    return "";  // Empty means auto-detect
}

/**
 * Gets the RGB value for a predetermined color string.
 */
static bool getRgbaValue(const std::string& color, Color& rgbaValue)
{
    const std::map<std::string, Color> colorMap
    {
        { "red", Color(255, 0, 0, 255) },
        { "green", Color(0, 255, 0, 255) },
        { "blue", Color(0, 0, 255, 255) },
        { "cyan", Color(0, 255, 255, 255) },
        { "magenta", Color(255, 0, 255, 255) },
        { "yellow", Color(255, 255, 0, 255) },
        { "black", Color(0, 0, 0, 255) },
        { "white", Color(255, 255, 255, 255) },
        { "grey", Color(128, 128, 128, 255) },
        { "gray", Color(128, 128, 128, 255) },
        { "orange", Color(255, 165, 0, 255) },
        { "purple", Color(128, 0, 128, 255) },
        { "violet", Color(128, 0, 128, 255) },
        { "pink", Color(255, 192, 203, 255) },
        { "teal", Color(0, 128, 128, 255) },
        { "brown", Color(165, 42, 42, 255) },
        { "ice_blue", Color(173, 216, 230, 255) },
        { "crimson", Color(220, 20, 60, 255) },
        { "gold", Color(255, 215, 0, 255) },
        { "neon_green", Color(57, 255, 20, 255) }
    };

    try
    {
        std::string key = toLowerCase(color);
        rgbaValue = colorMap.at(key);
        return true;
    }
    catch (const std::out_of_range&)
    {
        return false;
    }
}

/**
 * Extracts the color parameters from the command.
 */
static bool getLedColor(const json& params, Color& rgbaValue)
{
    const std::string COLOR = "color";
    const std::string OFF = "off";
    const std::string BRIGHTEN = "bright_up";
    const std::string DIM = "bright_down";
    const std::string RAINBOW = "rainbow";

    const int BRIGHTNESS_LEVEL = 10;

    auto boundBrightness = [](int value) {
        const int LOWER = 0;
        const int UPPER = 255;
        return std::clamp(value, LOWER, UPPER);
    };

    if (!params.contains(COLOR) || !params[COLOR].is_string())
    {
        return false;
    }

    std::string color = toLowerCase(params[COLOR].get<std::string>());
    if (color == OFF)
    {
        const std::string OFF_COLOR = "black";
        getRgbaValue(OFF_COLOR, rgbaValue);
        return true;
    }
    else if (color == BRIGHTEN)
    {
        rgbaValue.alpha = boundBrightness(rgbaValue.alpha + BRIGHTNESS_LEVEL);
        return true;
    }
    else if (color == DIM)
    {
        rgbaValue.alpha = boundBrightness(rgbaValue.alpha - BRIGHTNESS_LEVEL);
        return true;
    }
    else if (color == RAINBOW)
    {
        // do nothing for now
        return true;
    }
    else
    {
        return getRgbaValue(params[COLOR].get<std::string>(), rgbaValue);
    }
}

/**
 * Searches for the device type and returns the associated ID.
 */
static bool getDeviceId(CorsairDeviceType type, CorsairDeviceId& id)
{
    const int CORSAIR_DEVICE_ID_MAX = 128;
    bool isDeviceFound = false;
    for (auto i = 0; i < g_numDevices; ++i)
    {
        if (g_devices[i].type == type)
        {
            isDeviceFound = true;
            CopyMemory(id, g_devices[i].id, CORSAIR_DEVICE_ID_MAX);
            break;
        }
    }
    return isDeviceFound;
}

/**
 * Changes the color of a device.
 */
static bool doLightingChange(const CorsairDeviceId& id, const Color& color)
{
    CorsairLedPosition leds[CORSAIR_DEVICE_LEDCOUNT_MAX];
    int numLeds = 0;
    auto status = CorsairGetLedPositions(id, CORSAIR_DEVICE_LEDCOUNT_MAX, leds, &numLeds);
    if (status != CE_Success)
    {
        return false;
    }

    CorsairLedColor* colors = new CorsairLedColor[numLeds];
    for (auto i = 0; i < numLeds; ++i)
    {
        CopyMemory(&colors[i].id, &leds[i].id, sizeof(CorsairLedLuid));
        colors[i].r = color.red;
        colors[i].g = color.green;
        colors[i].b = color.blue;
        colors[i].a = color.alpha;
    }
    status = CorsairSetLedColors(id, numLeds, colors);
    delete[] colors;

    return (status == CE_Success);
}

// ============================================================================
// Corsair SDK Initialization
// ============================================================================

static bool ensureInitialized()
{
    logMsg("ensureInitialized called, g_isInitialized=" + std::to_string(g_isInitialized));
    if (g_isInitialized) return true;

    auto callback = [](void* context, const CorsairSessionStateChanged* eventData)
    {
        const int CONNECTION_ATTEMPT_LIMIT = 5;
        static int numTimeouts = 0;
        logMsg(std::format("CorsairConnect callback: state={}", (int)eventData->state));
        switch (eventData->state)
        {
        case CSS_Connected:
        {
            logMsg("CSS_Connected - enumerating devices");
            CorsairDeviceFilter filter;
            filter.deviceTypeMask = CDT_All;
            (void)CorsairGetDevices(&filter, CORSAIR_DEVICE_COUNT_MAX, g_devices, &g_numDevices);
            logMsg(std::format("Found {} Corsair devices", g_numDevices));
            for (int i = 0; i < g_numDevices; ++i) {
                logMsg(std::format("  Device {}: model='{}' type={}", i, g_devices[i].model, (int)g_devices[i].type));
            }
            break;
        }
        case CSS_Timeout:
            ++numTimeouts;
            logMsg(std::format("CSS_Timeout, count={}", numTimeouts));
            if (numTimeouts >= CONNECTION_ATTEMPT_LIMIT)
            {
                logMsg("Connection attempt limit reached, disconnecting");
                g_numDevices = 0;
                g_isInitialized = false;
                CorsairDisconnect();
            }
            break;
        default:
            break;
        }
    };

    logMsg("Calling CorsairConnect...");
    auto status = CorsairConnect(callback, nullptr);
    logMsg(std::format("CorsairConnect returned {}", (int)status));
    
    logMsg("Calling AutomationSdkConnect...");
    auto automationSdkStatus = AutomationSdkConnect("com.corsair.g_assist_plugin");
    logMsg(std::format("AutomationSdkConnect returned {}", (int)automationSdkStatus));
    
    g_isInitialized = (status == CE_Success) && (automationSdkStatus == AutomationSdkErrorCode::Success);
    logMsg("g_isInitialized=" + std::to_string(g_isInitialized));

    // Wait for SDK to enumerate devices
    if (g_isInitialized)
    {
        logMsg("Waiting 2s for device enumeration...");
        Sleep(2000);
        
        // Verify Automation SDK is working
        int dpiSize = 0, eqSize = 0, coolSize = 0, profileSize = 0, actionSize = 0;
        AutomationSdkDevice testDevices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        AutomationSdkProfile testProfiles[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        AutomationSdkAction testActions[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        
        auto profileCode = AutomationSdkGetProfiles(testProfiles, AUTOMATION_SDK_ITEMS_COUNT_MAX, &profileSize);
        auto actionCode = AutomationSdkGetLibraryActions(testActions, AUTOMATION_SDK_ITEMS_COUNT_MAX, &actionSize);
        auto dpiCode = AutomationSdkGetDpiDevices(testDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &dpiSize);
        auto eqCode = AutomationSdkGetEqualizerDevices(testDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &eqSize);
        auto coolCode = AutomationSdkGetCoolingDevices(testDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &coolSize);
        
        logMsg(std::format("Automation SDK - Profiles: size={} code={}", profileSize, (int)profileCode));
        logMsg(std::format("Automation SDK - Actions: size={} code={}", actionSize, (int)actionCode));
        logMsg(std::format("Automation SDK - DPI devices: size={} code={}", dpiSize, (int)dpiCode));
        logMsg(std::format("Automation SDK - EQ devices: size={} code={}", eqSize, (int)eqCode));
        logMsg(std::format("Automation SDK - Cooling devices: size={} code={}", coolSize, (int)coolCode));
        
        if (profileSize < 0 && dpiSize < 0) {
            logMsg("WARNING: Automation SDK may not be properly connected or approved in iCUE!");
            logMsg("Please check iCUE Settings > Software Integrations and approve the plugin.");
        }
    }

    return g_isInitialized;
}

static const std::string CONFIGURATION_MESSAGE =
    "Oops! The Corsair Plugin for G-Assist couldn't connect. To fix this:\n"
    "1. Verify the Corsair devices are connected.\n"
    "2. Ensure iCUE is installed and running.\n"
    "3. In iCUE, give permission to the plugin.\n"
    "4. In Windows, go to Settings > Personalization > Dynamic Lighting and disable 'Use Dynamic Lighting on my devices.'\n"
    "5. Close and reopen G-Assist.\n";

// ============================================================================
// Device Type Mapping
// ============================================================================

static const std::map<CorsairDeviceType, std::string> deviceStrings{
    { CDT_Headset, "headset" },
    { CDT_Keyboard, "keyboard" },
    { CDT_Mouse, "mouse" },
    { CDT_Mousemat, "mouse mat" },
    { CDT_HeadsetStand, "headset stand" },
    { CDT_FanLedController, "fan controller" },
    { CDT_LedController, "led controller" },
    { CDT_MemoryModule, "DRAM" },
    { CDT_Cooler, "cooler" },
    { CDT_Motherboard, "motherboard" },
    { CDT_GraphicsCard, "GPU" },
    { CDT_Touchbar, "touchbar" },
    { CDT_GameController, "gamepad" },
};

// ============================================================================
// Lighting Command Handlers
// ============================================================================

static json changeDeviceLighting(const CorsairDeviceType type, const json& params)
{
    if (!g_isInitialized && !ensureInitialized())
    {
        return json(CONFIGURATION_MESSAGE);
    }

    if (!deviceStrings.contains(type))
    {
        return json("Failed to update lighting for the Corsair device. Unknown device.");
    }

    const auto SUCCESS_MESSAGE = std::format("Corsair {} lighting updated.", deviceStrings.at(type));
    const auto ERROR_MESSAGE = std::format("Failed to update lighting for the Corsair {}.", deviceStrings.at(type));

    Color color = { 0, 0, 0, 0 };
    if (!getLedColor(params, color))
    {
        return json(std::format("{} Unknown or missing color.", ERROR_MESSAGE));
    }

    CorsairDeviceId deviceId;
    if (!getDeviceId(type, deviceId))
    {
        return json("Could not communicate to device");
    }

    auto isSuccess = doLightingChange(deviceId, color);
    return isSuccess ? json(SUCCESS_MESSAGE) : json(ERROR_MESSAGE);
}

static json cmdHeadsetLights(const json& params) { return changeDeviceLighting(CDT_Headset, params); }
static json cmdKeyboardLights(const json& params) { return changeDeviceLighting(CDT_Keyboard, params); }
static json cmdMouseLights(const json& params) { return changeDeviceLighting(CDT_Mouse, params); }
static json cmdHeadsetStandLights(const json& params) { return changeDeviceLighting(CDT_HeadsetStand, params); }
static json cmdFanControllerLights(const json& params) { return changeDeviceLighting(CDT_FanLedController, params); }
static json cmdMousematLights(const json& params) { return changeDeviceLighting(CDT_Mousemat, params); }
static json cmdLedControllerLights(const json& params) { return changeDeviceLighting(CDT_LedController, params); }
static json cmdCoolerLights(const json& params) { return changeDeviceLighting(CDT_Cooler, params); }
static json cmdMotherboardLights(const json& params) { return changeDeviceLighting(CDT_Motherboard, params); }
static json cmdGpuLights(const json& params) { return changeDeviceLighting(CDT_GraphicsCard, params); }
static json cmdDramLights(const json& params) { return changeDeviceLighting(CDT_MemoryModule, params); }
static json cmdTouchbarLights(const json& params) { return changeDeviceLighting(CDT_Touchbar, params); }
static json cmdGamepadLights(const json& params) { return changeDeviceLighting(CDT_GameController, params); }

// ============================================================================
// Profile Command Handlers
// ============================================================================

static json cmdActivateProfile(const json& params)
{
    const std::string profileNameKey = "name";
    if (!params.contains(profileNameKey) || !params[profileNameKey].is_string()) {
        return json("Could not parse the profile name from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkProfile profiles[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetProfiles(profiles, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE profiles");
    }

    const std::string profileName = params[profileNameKey].get<std::string>();
    for (int i = 0; i < size; ++i) {
        if (toLowerCase(profiles[i].name) == toLowerCase(profileName)) {
            if (AutomationSdkActivateProfile(profiles[i].id) == AutomationSdkErrorCode::Success) {
                return json(std::format("Active iCUE profile changed to the {}.", profileName));
            } else {
                return json(std::format("Failed to activate the iCUE profile with the name {}.", profileName));
            }
        }
    }
    return json(std::format("Could not find the iCUE profile with the name {}.", profileName));
}

static json cmdGetProfilesList(const json& params)
{
    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkProfile profiles[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetProfiles(profiles, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE profiles");
    }

    std::string result("The list of the profiles in iCUE:\n");
    for (int i = 0; i < size; ++i) {
        const auto& profile = profiles[i];
        result.append(std::format("* {}\n", profile.name));
    }
    return json(result);
}

// ============================================================================
// Action Command Handlers
// ============================================================================

static json cmdGetActionsList(const json& params)
{
    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkAction actions[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetLibraryActions(actions, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE actions.");
    }

    std::string result("The list of the actions in iCUE:\n");
    for (int i = 0; i < size; ++i) {
        const auto& action = actions[i];
        result.append(std::format("* {}\n", action.name));
    }
    return json(result);
}

static json cmdActivateAction(const json& params)
{
    const std::string actionNameKey = "name";
    if (!params.contains(actionNameKey) || !params[actionNameKey].is_string()) {
        return json("Could not parse the action name from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkAction actions[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetLibraryActions(actions, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE actions.");
    }

    const std::string actionName = params[actionNameKey].get<std::string>();
    for (int i = 0; i < size; ++i) {
        if (toLowerCase(actions[i].name) == toLowerCase(actionName)) {
            if (AutomationSdkActivateLibraryAction(actions[i].id) == AutomationSdkErrorCode::Success) {
                return json(std::format("The iCUE action with the name {} has been executed.", actionName));
            } else {
                return json(std::format("Failed to activate the iCUE action with the name {}.", actionName));
            }
        }
    }
    return json(std::format("Could not find the iCUE action with the name {}.", actionName));
}

// ============================================================================
// Cooling Command Handlers
// ============================================================================

static json cmdGetCoolingPresetsList(const json& params)
{
    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    const std::string executeFailureMessage("Could not get available iCUE cooling presets.");
    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetCoolingDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json(executeFailureMessage);
    }

    std::string result("The list of the cooling presets in iCUE:\n");
    for (int i = 0; i < size; ++i) {
        const auto& device = devices[i];
        int presetsSize = 0;
        AutomationSdkCoolingPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        code = AutomationSdkGetCoolingPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
        if (code != AutomationSdkErrorCode::Success) {
            return json(executeFailureMessage);
        }
        result.append(std::format("- Device {}\n", device.name));
        for (int j = 0; j < presetsSize; ++j) {
            const auto& preset = presets[j];
            result.append(std::format("\t* {}\n", preset.name));
        }
    }
    return json(result);
}

static json cmdActivateCoolingPreset(const json& params)
{
    const std::string presetNameKey = "presetName";
    if (!params.contains(presetNameKey) || !params[presetNameKey].is_string()) {
        return json("Could not parse the preset name from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetCoolingDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success || size <= 0) {
        return json("No Corsair cooling devices found.");
    }

    const std::string deviceName = getDeviceNameParam(params);
    const std::string presetName = params[presetNameKey].get<std::string>();

    int deviceIdx = findDeviceByName(devices, size, deviceName);
    if (deviceIdx < 0) {
        std::string available = "Available devices: ";
        for (int i = 0; i < size; ++i) {
            if (i > 0) available += ", ";
            available += devices[i].name;
        }
        return json(std::format("Could not find device '{}'. {}", deviceName, available));
    }

    const auto& device = devices[deviceIdx];
    int presetsSize = 0;
    AutomationSdkCoolingPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetCoolingPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE cooling presets.");
    }

    // Find preset with fuzzy matching
    std::string lowerPreset = toLowerCase(presetName);
    for (int j = 0; j < presetsSize; ++j) {
        const auto& preset = presets[j];
        std::string presetLower = toLowerCase(preset.name);
        if (presetLower == lowerPreset || presetLower.find(lowerPreset) != std::string::npos) {
            if (AutomationSdkActivateCoolingPreset(device.id, preset.id) == AutomationSdkErrorCode::Success) {
                return json(std::format("Cooling preset '{}' activated on {}.", preset.name, device.name));
            } else {
                return json(std::format("Failed to activate cooling preset '{}' on {}.", preset.name, device.name));
            }
        }
    }

    std::string available = "Available presets: ";
    for (int j = 0; j < presetsSize; ++j) {
        if (j > 0) available += ", ";
        available += presets[j].name;
    }
    return json(std::format("Preset '{}' not found. {}", presetName, available));
}

// ============================================================================
// Equalizer Command Handlers
// ============================================================================

static json cmdGetEqualizerPresetsList(const json& params)
{
    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    const std::string executeFailureMessage("Could not get available iCUE equalizer presets.");
    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetEqualizerDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json(executeFailureMessage);
    }

    std::string result("The list of the equalizer presets in iCUE:\n");
    for (int i = 0; i < size; ++i) {
        const auto& device = devices[i];
        int presetsSize = 0;
        AutomationSdkEqualizerPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        code = AutomationSdkGetEqualizerPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
        if (code != AutomationSdkErrorCode::Success) {
            return json(executeFailureMessage);
        }
        result.append(std::format("- Device {}\n", device.name));
        for (int j = 0; j < presetsSize; ++j) {
            const auto& preset = presets[j];
            result.append(std::format("\t* {}\n", preset.name));
        }
    }
    return json(result);
}

static json cmdActivateEqualizerPreset(const json& params)
{
    const std::string presetNameKey = "presetName";
    if (!params.contains(presetNameKey) || !params[presetNameKey].is_string()) {
        return json("Could not parse the preset name from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetEqualizerDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success || size <= 0) {
        return json("No Corsair headset with EQ support found.");
    }

    const std::string deviceName = getDeviceNameParam(params);
    const std::string presetName = params[presetNameKey].get<std::string>();

    int deviceIdx = findDeviceByName(devices, size, deviceName);
    if (deviceIdx < 0) {
        std::string available = "Available devices: ";
        for (int i = 0; i < size; ++i) {
            if (i > 0) available += ", ";
            available += devices[i].name;
        }
        return json(std::format("Could not find device '{}'. {}", deviceName, available));
    }

    const auto& device = devices[deviceIdx];
    int presetsSize = 0;
    AutomationSdkEqualizerPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetEqualizerPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE equalizer presets.");
    }

    // Find preset with fuzzy matching
    std::string lowerPreset = toLowerCase(presetName);
    for (int j = 0; j < presetsSize; ++j) {
        const auto& preset = presets[j];
        std::string presetLower = toLowerCase(preset.name);
        if (presetLower == lowerPreset || presetLower.find(lowerPreset) != std::string::npos) {
            if (AutomationSdkActivateEqualizerPreset(device.id, preset.id) == AutomationSdkErrorCode::Success) {
                return json(std::format("EQ preset '{}' activated on {}.", preset.name, device.name));
            } else {
                return json(std::format("Failed to activate EQ preset '{}' on {}.", preset.name, device.name));
            }
        }
    }

    std::string available = "Available presets: ";
    for (int j = 0; j < presetsSize; ++j) {
        if (j > 0) available += ", ";
        available += presets[j].name;
    }
    return json(std::format("Preset '{}' not found. {}", presetName, available));
}

// ============================================================================
// DPI Command Handlers
// ============================================================================

static json cmdGetDpiPresetsList(const json& params)
{
    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    const std::string executeFailureMessage("Could not get available iCUE DPI presets.");
    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success) {
        return json(executeFailureMessage);
    }

    std::string result("The list of the DPI presets in iCUE:\n");
    for (int i = 0; i < size; ++i) {
        const auto& device = devices[i];
        int presetsSize = 0;
        AutomationSdkDpiPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        code = AutomationSdkGetDpiPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
        if (code != AutomationSdkErrorCode::Success) {
            return json(executeFailureMessage);
        }
        result.append(std::format("- Device {}\n", device.name));
        for (int j = 0; j < presetsSize; ++j) {
            const auto& preset = presets[j];
            result.append(std::format("\t* {}\n", preset.name));
        }
    }
    return json(result);
}

static json cmdActivateDpiPreset(const json& params)
{
    const std::string presetNameKey = "presetName";
    if (!params.contains(presetNameKey) || !params[presetNameKey].is_string()) {
        return json("Could not parse the preset name from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success || size <= 0) {
        return json("No DPI-capable Corsair devices found.");
    }

    const std::string deviceName = getDeviceNameParam(params);
    const std::string presetName = params[presetNameKey].get<std::string>();

    int deviceIdx = findDeviceByName(devices, size, deviceName);
    if (deviceIdx < 0) {
        std::string available = "Available devices: ";
        for (int i = 0; i < size; ++i) {
            if (i > 0) available += ", ";
            available += devices[i].name;
        }
        return json(std::format("Could not find device '{}'. {}", deviceName, available));
    }

    const auto& device = devices[deviceIdx];
    int presetsSize = 0;
    AutomationSdkDpiPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetDpiPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
    if (code != AutomationSdkErrorCode::Success) {
        return json("Could not get available iCUE DPI presets.");
    }

    // Find preset with fuzzy matching
    std::string lowerPreset = toLowerCase(presetName);
    for (int j = 0; j < presetsSize; ++j) {
        const auto& preset = presets[j];
        std::string presetLower = toLowerCase(preset.name);
        if (presetLower == lowerPreset || presetLower.find(lowerPreset) != std::string::npos) {
            if (AutomationSdkActivateDpiPreset(device.id, preset.id) == AutomationSdkErrorCode::Success) {
                return json(std::format("DPI preset '{}' activated on {}.", preset.name, device.name));
            } else {
                return json(std::format("Failed to activate DPI preset '{}' on {}.", preset.name, device.name));
            }
        }
    }

    // List available presets
    std::string available = "Available presets: ";
    for (int j = 0; j < presetsSize; ++j) {
        if (j > 0) available += ", ";
        available += presets[j].name;
    }
    return json(std::format("Preset '{}' not found. {}", presetName, available));
}

static json cmdGetDpiStagesList(const json& params)
{
    logMsg("cmdGetDpiStagesList called");
    
    if (!g_isInitialized && !ensureInitialized()) {
        logMsg("ERROR: SDK not initialized");
        return json(CONFIGURATION_MESSAGE);
    }

    const std::string executeFailureMessage("Could not get available iCUE DPI stages.");
    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    logMsg(std::format("AutomationSdkGetDpiDevices: code={}, size={}", (int)code, size));
    
    if (code != AutomationSdkErrorCode::Success) {
        return json(executeFailureMessage);
    }

    std::string result("The list of the DPI stages in iCUE:\n");
    for (int i = 0; i < size; ++i) {
        const auto& device = devices[i];
        logMsg(std::format("Device {}: {}", i, device.name));
        
        int stagesSize = 0;
        AutomationSdkDpiStage stages[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
        code = AutomationSdkGetDpiStages(device.id, stages, AUTOMATION_SDK_ITEMS_COUNT_MAX, &stagesSize);
        logMsg(std::format("  GetDpiStages: code={}, stagesSize={}", (int)code, stagesSize));
        
        if (code != AutomationSdkErrorCode::Success) {
            return json(executeFailureMessage);
        }
        result.append(std::format("- Device {}\n", device.name));
        for (int j = 0; j < stagesSize; ++j) {
            const auto& stage = stages[j];
            logMsg(std::format("    Stage {}: {}", j, stage.name));
            result.append(std::format("\t* {}\n", stage.name));
        }
    }
    logMsg("Result: " + result);
    return json(result);
}

static json cmdActivateDpiStage(const json& params)
{
    const std::string stageNumberKey = "stageNumber";
    if (!params.contains(stageNumberKey) || !params[stageNumberKey].is_number()) {
        return json("Could not parse the stage number from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success || size <= 0) {
        return json("No DPI-capable Corsair devices found.");
    }

    const std::string deviceName = getDeviceNameParam(params);
    const int stageNumber = params[stageNumberKey].get<int>();
    const int stageIndex = stageNumber - 1;
    if (stageIndex < AutomationSdkDpiStageIndex::Stage1 || stageIndex > AutomationSdkDpiStageIndex::SniperStage) {
        return json("Invalid DPI stage number has been provided");
    }

    int deviceIdx = findDeviceByName(devices, size, deviceName);
    if (deviceIdx < 0) {
        // List available devices to help user
        std::string available = "Available devices: ";
        for (int i = 0; i < size; ++i) {
            if (i > 0) available += ", ";
            available += devices[i].name;
        }
        return json(std::format("Could not find device '{}'. {}", deviceName, available));
    }

    const auto& device = devices[deviceIdx];
    code = AutomationSdkActivateDpiStage(device.id, static_cast<AutomationSdkDpiStageIndex>(stageIndex));
    if (code == AutomationSdkErrorCode::Success) {
        return json(std::format("DPI stage {} activated on {}.", stageNumber, device.name));
    } else {
        return json(std::format("Failed to activate DPI stage {} on {}.", stageNumber, device.name));
    }
}

static json cmdActivateDpiSniperStage(const json& params)
{
    if (!g_isInitialized && !ensureInitialized()) {
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    if (code != AutomationSdkErrorCode::Success || size <= 0) {
        return json("No DPI-capable Corsair devices found.");
    }

    const std::string deviceName = getDeviceNameParam(params);
    int deviceIdx = findDeviceByName(devices, size, deviceName);
    if (deviceIdx < 0) {
        std::string available = "Available devices: ";
        for (int i = 0; i < size; ++i) {
            if (i > 0) available += ", ";
            available += devices[i].name;
        }
        return json(std::format("Could not find device '{}'. {}", deviceName, available));
    }

    const auto& device = devices[deviceIdx];
    code = AutomationSdkActivateDpiStage(device.id, AutomationSdkDpiStageIndex::SniperStage);
    if (code == AutomationSdkErrorCode::Success) {
        return json(std::format("DPI sniper stage activated on {}.", device.name));
    } else {
        return json(std::format("Failed to activate DPI sniper stage on {}.", device.name));
    }
}

static json cmdSetDpiStageValue(const json& params)
{
    logMsg("cmdSetDpiStageValue called with params: " + params.dump());
    
    const std::string stageValueKey = "stageValue";
    if (!params.contains(stageValueKey) || !params[stageValueKey].is_number()) {
        logMsg("ERROR: Could not parse stageValue from params");
        return json("Could not parse the DPI value from the request.");
    }

    if (!g_isInitialized && !ensureInitialized()) {
        logMsg("ERROR: SDK not initialized");
        return json(CONFIGURATION_MESSAGE);
    }

    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    logMsg(std::format("AutomationSdkGetDpiDevices returned {} devices, code={}", size, (int)code));
    
    // If we get invalid result, try reconnecting
    if (size < 0) {
        logMsg("Got invalid size, attempting to reconnect Automation SDK...");
        AutomationSdkDisconnect();
        Sleep(500);
        auto reconnectCode = AutomationSdkConnect("com.corsair.g_assist_plugin");
        logMsg(std::format("AutomationSdkConnect returned {}", (int)reconnectCode));
        Sleep(1000);
        code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
        logMsg(std::format("After reconnect: {} devices, code={}", size, (int)code));
    }
    
    if (code != AutomationSdkErrorCode::Success || size <= 0) {
        logMsg("ERROR: No DPI-capable devices found");
        return json("No DPI-capable Corsair devices found.");
    }

    const std::string deviceName = getDeviceNameParam(params);
    const int stageValue = params[stageValueKey].get<int>();
    logMsg(std::format("Looking for device='{}', stageValue={}", deviceName, stageValue));

    int deviceIdx = findDeviceByName(devices, size, deviceName);
    logMsg(std::format("findDeviceByName returned index={}", deviceIdx));
    
    if (deviceIdx < 0) {
        std::string available = "Available devices: ";
        for (int i = 0; i < size; ++i) {
            if (i > 0) available += ", ";
            available += devices[i].name;
        }
        logMsg("ERROR: Device not found. " + available);
        return json(std::format("Could not find device '{}'. {}", deviceName, available));
    }

    const auto& device = devices[deviceIdx];
    logMsg(std::format("Setting DPI to {} on device '{}'", stageValue, device.name));
    code = AutomationSdkSetDpiValue(device.id, stageValue);
    
    if (code == AutomationSdkErrorCode::Success) {
        logMsg("SUCCESS: DPI set");
        return json(std::format("DPI set to {} on {}.", stageValue, device.name));
    } else {
        logMsg(std::format("ERROR: Failed to set DPI, code={}", (int)code));
        return json(std::format("Failed to set DPI on {}.", device.name));
    }
}

// ============================================================================
// DLL Directory Setup
// ============================================================================

static void setupDllDirectory()
{
    wchar_t exePath[MAX_PATH];
    if (GetModuleFileNameW(NULL, exePath, MAX_PATH)) {
        wchar_t* lastSlash = wcsrchr(exePath, L'\\');
        if (lastSlash) {
            *(lastSlash + 1) = L'\0';
            std::wstring libsPath = std::wstring(exePath) + L"libs";
            AddDllDirectory(libsPath.c_str());
            SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        }
    }
}

// ============================================================================
// Main Entry Point
// ============================================================================

int main()
{
    // Immediate crash-safe log - write to known location first
    {
        std::ofstream crashLog("C:\\ProgramData\\NVIDIA Corporation\\nvtopps\\rise\\plugins\\corsair\\startup.log", std::ios::app);
        if (crashLog.is_open()) {
            crashLog << "=== main() entered ===" << std::endl;
            crashLog.close();
        }
    }
    
    // Initialize logging
    initLogging();
    logMsg("========== Corsair-Ext Plugin Starting ==========");
    
    // Set up DLL search path for SDK DLLs
    logMsg("Setting up DLL directory...");
    setupDllDirectory();
    logMsg("DLL directory setup complete");

    logMsg("Creating plugin instance...");
    gassist::Plugin plugin("corsair", "2.0.0", "Extended Corsair iCUE Plugin for G-Assist");
    g_plugin = &plugin;
    logMsg("Plugin instance created");

    // Register lighting commands
    logMsg("Registering commands...");
    plugin.command("corsair_change_keyboard_lights", cmdKeyboardLights);
    plugin.command("corsair_change_mouse_lights", cmdMouseLights);
    plugin.command("corsair_change_headphone_lights", cmdHeadsetLights);
    plugin.command("corsair_change_headset_stand_lights", cmdHeadsetStandLights);
    plugin.command("corsair_change_mousemat_lights", cmdMousematLights);
    plugin.command("corsair_change_fan_controller_lights", cmdFanControllerLights);
    plugin.command("corsair_change_led_controller_lights", cmdLedControllerLights);
    plugin.command("corsair_change_cooler_lights", cmdCoolerLights);
    plugin.command("corsair_change_dram_lights", cmdDramLights);
    plugin.command("corsair_change_motherboard_lights", cmdMotherboardLights);
    plugin.command("corsair_change_gpu_lights", cmdGpuLights);
    plugin.command("corsair_change_touchbar_lights", cmdTouchbarLights);
    plugin.command("corsair_change_gamepad_lights", cmdGamepadLights);

    // Register profile commands
    plugin.command("corsair_activate_profile", cmdActivateProfile);
    plugin.command("corsair_get_profiles_list", cmdGetProfilesList);

    // Register action commands
    plugin.command("corsair_get_actions_list", cmdGetActionsList);
    plugin.command("corsair_activate_action", cmdActivateAction);

    // Register cooling commands
    plugin.command("corsair_get_cooling_presets_list", cmdGetCoolingPresetsList);
    plugin.command("corsair_activate_cooling_preset", cmdActivateCoolingPreset);

    // Register equalizer commands
    plugin.command("corsair_get_equalizer_presets_list", cmdGetEqualizerPresetsList);
    plugin.command("corsair_activate_equalizer_preset", cmdActivateEqualizerPreset);

    // Register DPI commands
    plugin.command("corsair_get_dpi_presets_list", cmdGetDpiPresetsList);
    plugin.command("corsair_activate_dpi_preset", cmdActivateDpiPreset);
    plugin.command("corsair_get_dpi_stages_list", cmdGetDpiStagesList);
    plugin.command("corsair_activate_dpi_stage", cmdActivateDpiStage);
    plugin.command("corsair_activate_dpi_sniper_stage", cmdActivateDpiSniperStage);
    plugin.command("corsair_set_dpi_stage_value", cmdSetDpiStageValue);
    logMsg("All commands registered");

    // Run the plugin
    logMsg("Starting plugin.run()...");
    plugin.run();
    logMsg("plugin.run() returned");

    // Cleanup
    if (g_isInitialized)
    {
        logMsg("Cleaning up SDK connections...");
        CorsairDisconnect();
        AutomationSdkDisconnect();
    }

    logMsg("Plugin shutdown complete");
    return 0;
}

