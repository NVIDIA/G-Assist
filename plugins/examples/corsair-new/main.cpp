/*
 * SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 *
 * Corsair iCUE Plugin for G-Assist (Protocol V2)
 * 
 * Smart auto-discovery plugin that controls Corsair devices without requiring
 * users to manually list devices or profiles first.
 */

#include <algorithm>
#include <format>
#include <map>
#include <string>
#include <vector>

#include <Windows.h>

#include "nlohmann/json.hpp"
#include "gassist_sdk.hpp"
#include "AutomationSDK/iCUEAutomationSDK.h"
#include "iCUESDK/iCUESDK.h"

using json = nlohmann::json;

// ============================================================================
// Global State
// ============================================================================

bool g_initialized = false;
CorsairDeviceInfo g_devices[CORSAIR_DEVICE_COUNT_MAX];
int g_numDevices = 0;
gassist::Plugin* g_plugin = nullptr;

// ============================================================================
// Utility Functions
// ============================================================================

static std::string toLowerCase(const std::string& s) {
    std::string lower = s;
    std::transform(lower.begin(), lower.end(), lower.begin(),
        [](unsigned char c) { return std::tolower(c); });
    return lower;
}

// Color name to RGB mapping
struct Color { int r, g, b, a; };

static bool getColor(const std::string& colorName, Color& out) {
    static const std::map<std::string, Color> colors = {
        {"red",      {255, 0, 0, 255}},
        {"green",    {0, 255, 0, 255}},
        {"blue",     {0, 0, 255, 255}},
        {"cyan",     {0, 255, 255, 255}},
        {"magenta",  {255, 0, 255, 255}},
        {"yellow",   {255, 255, 0, 255}},
        {"white",    {255, 255, 255, 255}},
        {"black",    {0, 0, 0, 255}},
        {"off",      {0, 0, 0, 0}},
        {"orange",   {255, 165, 0, 255}},
        {"purple",   {128, 0, 128, 255}},
        {"pink",     {255, 192, 203, 255}},
        {"gold",     {255, 215, 0, 255}},
        {"teal",     {0, 128, 128, 255}},
        {"grey",     {128, 128, 128, 255}},
        {"gray",     {128, 128, 128, 255}},
    };
    
    auto it = colors.find(toLowerCase(colorName));
    if (it != colors.end()) {
        out = it->second;
        return true;
    }
    return false;
}

// Device type name mapping
static CorsairDeviceType getDeviceType(const std::string& name) {
    static const std::map<std::string, CorsairDeviceType> types = {
        {"keyboard",   CDT_Keyboard},
        {"mouse",      CDT_Mouse},
        {"headset",    CDT_Headset},
        {"headphone",  CDT_Headset},
        {"mousemat",   CDT_Mousemat},
        {"fans",       CDT_FanLedController},
        {"cooler",     CDT_Cooler},
        {"ram",        CDT_MemoryModule},
        {"dram",       CDT_MemoryModule},
        {"memory",     CDT_MemoryModule},
        {"motherboard", CDT_Motherboard},
        {"gpu",        CDT_GraphicsCard},
    };
    
    auto it = types.find(toLowerCase(name));
    return (it != types.end()) ? it->second : CDT_Unknown;
}

static std::string getDeviceTypeName(CorsairDeviceType type) {
    static const std::map<CorsairDeviceType, std::string> names = {
        {CDT_Keyboard, "keyboard"},
        {CDT_Mouse, "mouse"},
        {CDT_Headset, "headset"},
        {CDT_Mousemat, "mousemat"},
        {CDT_FanLedController, "fan controller"},
        {CDT_LedController, "LED controller"},
        {CDT_Cooler, "cooler"},
        {CDT_MemoryModule, "RAM"},
        {CDT_Motherboard, "motherboard"},
        {CDT_GraphicsCard, "GPU"},
        {CDT_HeadsetStand, "headset stand"},
        {CDT_Touchbar, "touchbar"},
        {CDT_GameController, "gamepad"},
    };
    
    auto it = names.find(type);
    return (it != names.end()) ? it->second : "unknown device";
}

// ============================================================================
// Corsair SDK Initialization
// ============================================================================

static bool ensureInitialized() {
    if (g_initialized) return true;
    
    auto callback = [](void*, const CorsairSessionStateChanged* event) {
        if (event->state == CSS_Connected) {
            CorsairDeviceFilter filter;
            filter.deviceTypeMask = CDT_All;
            CorsairGetDevices(&filter, CORSAIR_DEVICE_COUNT_MAX, g_devices, &g_numDevices);
        }
    };
    
    auto status = CorsairConnect(callback, nullptr);
    auto autoStatus = AutomationSdkConnect("com.corsair.g_assist_plugin");
    
    g_initialized = (status == CE_Success) && (autoStatus == AutomationSdkErrorCode::Success);
    
    // Wait briefly for device enumeration
    if (g_initialized) {
        Sleep(500);
    }
    
    return g_initialized;
}

// ============================================================================
// Auto-Discovery Helpers
// ============================================================================

// Find first device of a specific type
static bool findDevice(CorsairDeviceType type, CorsairDeviceId& outId, std::string& outName) {
    for (int i = 0; i < g_numDevices; i++) {
        if (g_devices[i].type == type) {
            memcpy(outId, g_devices[i].id, sizeof(CorsairDeviceId));
            outName = g_devices[i].model;
            return true;
        }
    }
    return false;
}

// Find all devices of a specific type
struct DeviceInfo {
    CorsairDeviceId id;
    std::string name;
};

static std::vector<DeviceInfo> findDevices(CorsairDeviceType type) {
    std::vector<DeviceInfo> results;
    for (int i = 0; i < g_numDevices; i++) {
        if (type == CDT_Unknown || g_devices[i].type == type) {
            DeviceInfo info;
            memcpy(info.id, g_devices[i].id, sizeof(CorsairDeviceId));
            info.name = g_devices[i].model;
            results.push_back(info);
        }
    }
    return results;
}

// Set lighting on a specific device
static bool setDeviceLighting(const CorsairDeviceId& id, const Color& color) {
    CorsairLedPosition leds[CORSAIR_DEVICE_LEDCOUNT_MAX];
    int numLeds = 0;
    
    if (CorsairGetLedPositions(id, CORSAIR_DEVICE_LEDCOUNT_MAX, leds, &numLeds) != CE_Success) {
        return false;
    }
    
    std::vector<CorsairLedColor> colors(numLeds);
    for (int i = 0; i < numLeds; i++) {
        memcpy(&colors[i].id, &leds[i].id, sizeof(CorsairLedLuid));
        colors[i].r = color.r;
        colors[i].g = color.g;
        colors[i].b = color.b;
        colors[i].a = color.a;
    }
    
    return CorsairSetLedColors(id, numLeds, colors.data()) == CE_Success;
}

// ============================================================================
// Command Handlers
// ============================================================================

// Set mouse DPI with auto-discovery
static json cmdSetMouseDpi(const json& args) {
    if (!ensureInitialized()) {
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    int dpi = args.value("dpi", 0);
    if (dpi < 100 || dpi > 26000) {
        return json("Invalid DPI value. Please specify a value between 100 and 26000.");
    }
    
    // Find DPI-capable devices via Automation SDK
    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetDpiDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    
    if (code != AutomationSdkErrorCode::Success || size == 0) {
        return json("No Corsair mouse found. Please connect a Corsair mouse with DPI control.");
    }
    
    // Set DPI on first mouse found
    const auto& device = devices[0];
    code = AutomationSdkSetDpiValue(device.id, dpi);
    
    if (code == AutomationSdkErrorCode::Success) {
        return json(std::format("Set {} DPI to {}.", device.name, dpi));
    } else {
        return json(std::format("Failed to set DPI on {}.", device.name));
    }
}

// Set lighting with optional device targeting
static json cmdSetLighting(const json& args) {
    if (!ensureInitialized()) {
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    std::string colorName = args.value("color", "");
    std::string deviceFilter = toLowerCase(args.value("device", "all"));
    
    Color color;
    if (!getColor(colorName, color)) {
        return json(std::format("Unknown color '{}'. Try: red, blue, green, cyan, magenta, yellow, white, orange, purple, pink, gold, or 'off'.", colorName));
    }
    
    std::vector<std::string> updated;
    std::vector<std::string> failed;
    
    // Determine which devices to target
    bool targetAll = (deviceFilter == "all" || deviceFilter.empty());
    CorsairDeviceType targetType = targetAll ? CDT_Unknown : getDeviceType(deviceFilter);
    
    for (int i = 0; i < g_numDevices; i++) {
        if (targetAll || g_devices[i].type == targetType) {
            CorsairDeviceId id;
            memcpy(id, g_devices[i].id, sizeof(CorsairDeviceId));
            
            if (setDeviceLighting(id, color)) {
                updated.push_back(g_devices[i].model);
            } else {
                failed.push_back(g_devices[i].model);
            }
        }
    }
    
    if (updated.empty() && failed.empty()) {
        if (targetAll) {
            return json("No Corsair devices found. Please connect a Corsair device.");
        } else {
            return json(std::format("No Corsair {} found.", deviceFilter));
        }
    }
    
    std::string result;
    if (!updated.empty()) {
        result = std::format("Set {} lighting to {}", updated.size() == 1 ? updated[0] : std::to_string(updated.size()) + " devices", colorName);
        if (colorName == "off") {
            result = std::format("Turned off lighting on {}", updated.size() == 1 ? updated[0] : std::to_string(updated.size()) + " devices");
        }
    }
    if (!failed.empty()) {
        if (!result.empty()) result += ". ";
        result += std::format("Failed to update: {}", failed.size());
    }
    
    return json(result + ".");
}

// Set headset EQ with auto-discovery
static json cmdSetHeadsetEq(const json& args) {
    if (!ensureInitialized()) {
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    std::string presetName = args.value("preset", "");
    if (presetName.empty()) {
        return json("Please specify an EQ preset name.");
    }
    
    // Find equalizer-capable devices
    int size = 0;
    AutomationSdkDevice devices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetEqualizerDevices(devices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    
    if (code != AutomationSdkErrorCode::Success || size == 0) {
        return json("No Corsair headset with EQ support found. Please connect a Corsair headset.");
    }
    
    // Use first headset
    const auto& device = devices[0];
    
    // Get available presets
    int presetsSize = 0;
    AutomationSdkEqualizerPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetEqualizerPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
    
    if (code != AutomationSdkErrorCode::Success) {
        return json("Failed to get EQ presets from headset.");
    }
    
    // Find matching preset (case-insensitive)
    std::string lowerPreset = toLowerCase(presetName);
    for (int i = 0; i < presetsSize; i++) {
        if (toLowerCase(presets[i].name) == lowerPreset || 
            toLowerCase(presets[i].name).find(lowerPreset) != std::string::npos) {
            
            code = AutomationSdkActivateEqualizerPreset(device.id, presets[i].id);
            if (code == AutomationSdkErrorCode::Success) {
                return json(std::format("Set {} EQ to '{}'.", device.name, presets[i].name));
            } else {
                return json(std::format("Failed to set EQ preset on {}.", device.name));
            }
        }
    }
    
    // Preset not found - list available presets
    std::string available = "Available EQ presets: ";
    for (int i = 0; i < presetsSize; i++) {
        if (i > 0) available += ", ";
        available += presets[i].name;
    }
    
    return json(std::format("EQ preset '{}' not found. {}", presetName, available));
}

// Set iCUE profile
static json cmdSetProfile(const json& args) {
    if (!ensureInitialized()) {
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    std::string profileName = args.value("name", "");
    if (profileName.empty()) {
        return json("Please specify a profile name.");
    }
    
    int size = 0;
    AutomationSdkProfile profiles[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto code = AutomationSdkGetProfiles(profiles, AUTOMATION_SDK_ITEMS_COUNT_MAX, &size);
    
    if (code != AutomationSdkErrorCode::Success) {
        return json("Failed to get iCUE profiles.");
    }
    
    // Find matching profile (case-insensitive)
    std::string lowerName = toLowerCase(profileName);
    for (int i = 0; i < size; i++) {
        if (toLowerCase(profiles[i].name) == lowerName ||
            toLowerCase(profiles[i].name).find(lowerName) != std::string::npos) {
            
            code = AutomationSdkActivateProfile(profiles[i].id);
            if (code == AutomationSdkErrorCode::Success) {
                return json(std::format("Activated iCUE profile '{}'.", profiles[i].name));
            } else {
                return json(std::format("Failed to activate profile '{}'.", profiles[i].name));
            }
        }
    }
    
    // Profile not found - list available
    std::string available = "Available profiles: ";
    for (int i = 0; i < size; i++) {
        if (i > 0) available += ", ";
        available += profiles[i].name;
    }
    
    return json(std::format("Profile '{}' not found. {}", profileName, available));
}

// Get connected devices
static json cmdGetDevices(const json& args) {
    if (!ensureInitialized()) {
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    if (g_numDevices == 0) {
        return json("No Corsair devices found. Please connect a Corsair device and ensure iCUE is running.");
    }
    
    std::string result = std::format("Found {} Corsair device(s):\n", g_numDevices);
    
    for (int i = 0; i < g_numDevices; i++) {
        result += std::format("- {} ({})\n", g_devices[i].model, getDeviceTypeName(g_devices[i].type));
    }
    
    // Also show available profiles
    int profileCount = 0;
    AutomationSdkProfile profiles[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    if (AutomationSdkGetProfiles(profiles, AUTOMATION_SDK_ITEMS_COUNT_MAX, &profileCount) == AutomationSdkErrorCode::Success && profileCount > 0) {
        result += "\nAvailable profiles: ";
        for (int i = 0; i < profileCount; i++) {
            if (i > 0) result += ", ";
            result += profiles[i].name;
        }
    }
    
    return json(result);
}

// ============================================================================
// Main Entry Point
// ============================================================================

int main() {
    gassist::Plugin plugin("corsair", "2.0.0", "Control Corsair iCUE devices");
    g_plugin = &plugin;
    
    // Register commands
    plugin.command("corsair_set_mouse_dpi", cmdSetMouseDpi);
    plugin.command("corsair_set_lighting", cmdSetLighting);
    plugin.command("corsair_set_headset_eq", cmdSetHeadsetEq);
    plugin.command("corsair_set_profile", cmdSetProfile);
    plugin.command("corsair_get_devices", cmdGetDevices);
    
    // Run the plugin
    plugin.run();
    
    // Cleanup
    if (g_initialized) {
        CorsairDisconnect();
        AutomationSdkDisconnect();
    }
    
    return 0;
}
