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
#include <fstream>
#include <chrono>
#include <ctime>
#include <iomanip>
#include <sstream>

#include <Windows.h>

#include "nlohmann/json.hpp"
#include "libs/include/gassist_sdk.hpp"
#include "AutomationSDK/iCUEAutomationSDK.h"
#include "iCUESDK/iCUESDK.h"

using json = nlohmann::json;

// ============================================================================
// Logging Utility
// ============================================================================

static std::ofstream g_logFile;

static void initLogging() {
    // Log to file next to the executable
    char exePath[MAX_PATH];
    if (GetModuleFileNameA(NULL, exePath, MAX_PATH)) {
        std::string logPath = exePath;
        auto pos = logPath.find_last_of("\\/");
        if (pos != std::string::npos) {
            logPath = logPath.substr(0, pos + 1) + "corsair_plugin.log";
        } else {
            logPath = "corsair_plugin.log";
        }
        g_logFile.open(logPath, std::ios::out | std::ios::app);
        if (g_logFile.is_open()) {
            g_logFile << "\n========== Plugin Started ==========\n";
        }
    }
}

static void logMsg(const std::string& msg) {
    if (!g_logFile.is_open()) return;
    
    // Get timestamp
    auto now = std::chrono::system_clock::now();
    auto time = std::chrono::system_clock::to_time_t(now);
    auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        now.time_since_epoch()) % 1000;
    
    std::tm tm_buf;
    localtime_s(&tm_buf, &time);
    
    g_logFile << std::put_time(&tm_buf, "%H:%M:%S") << "." 
              << std::setfill('0') << std::setw(3) << ms.count() 
              << " " << msg << "\n";
    g_logFile.flush();
}

static std::string corsairErrorToString(CorsairError err) {
    switch (err) {
        case CE_Success: return "Success";
        case CE_NotConnected: return "NotConnected";
        case CE_NoControl: return "NoControl";
        case CE_IncompatibleProtocol: return "IncompatibleProtocol";
        case CE_InvalidArguments: return "InvalidArguments";
        case CE_InvalidOperation: return "InvalidOperation";
        case CE_DeviceNotFound: return "DeviceNotFound";
        case CE_NotAllowed: return "NotAllowed";
        default: return std::format("Unknown({})", static_cast<int>(err));
    }
}

static std::string automationErrorToString(AutomationSdkErrorCode err) {
    switch (err) {
        case Success: return "Success";
        case Failure: return "Failure";
        case NotConnected: return "NotConnected";
        case InvalidArguments: return "InvalidArguments";
        case ResourceNotFound: return "ResourceNotFound";
        default: return std::format("Unknown({})", static_cast<int>(err));
    }
}

// ============================================================================
// Global State
// ============================================================================

bool g_initialized = false;
CorsairDeviceInfo g_devices[CORSAIR_DEVICE_COUNT_MAX];
int g_numDevices = 0;

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
    if (g_initialized) {
        logMsg("[INIT] Already initialized, skipping");
        return true;
    }
    
    logMsg("[INIT] Starting Corsair SDK initialization...");
    
    auto callback = [](void*, const CorsairSessionStateChanged* event) {
        logMsg(std::format("[INIT] Session state changed: {}", static_cast<int>(event->state)));
        if (event->state == CSS_Connected) {
            logMsg("[INIT] Session connected, enumerating devices...");
            CorsairDeviceFilter filter;
            filter.deviceTypeMask = CDT_All;
            auto devErr = CorsairGetDevices(&filter, CORSAIR_DEVICE_COUNT_MAX, g_devices, &g_numDevices);
            logMsg(std::format("[INIT] CorsairGetDevices returned: {}, found {} devices", 
                corsairErrorToString(devErr), g_numDevices));
            for (int i = 0; i < g_numDevices; i++) {
                logMsg(std::format("[INIT]   Device {}: '{}' (type={})", 
                    i, g_devices[i].model, static_cast<int>(g_devices[i].type)));
            }
        }
    };
    
    // Step 1: Connect to iCUE SDK first
    logMsg("[INIT] Calling CorsairConnect...");
    auto status = CorsairConnect(callback, nullptr);
    logMsg(std::format("[INIT] CorsairConnect returned: {}", corsairErrorToString(status)));
    
    if (status != CE_Success) {
        logMsg("[INIT] iCUE SDK connection failed");
        return false;
    }
    
    // Step 2: Wait for iCUE to fully initialize and enumerate devices
    logMsg("[INIT] Waiting 1000ms for iCUE device enumeration to complete...");
    Sleep(1000);
    logMsg(std::format("[INIT] After wait: {} devices found", g_numDevices));
    
    // Step 3: NOW connect to Automation SDK (after iCUE is ready)
    logMsg("[INIT] Calling AutomationSdkConnect...");
    auto autoStatus = AutomationSdkConnect("com.nvidia.g_assist_corsair");
    logMsg(std::format("[INIT] AutomationSdkConnect returned: {}", automationErrorToString(autoStatus)));
    
    if (autoStatus != Success) {
        logMsg("[INIT] Automation SDK connection failed");
        // Continue anyway - iCUE SDK works for lighting
    }
    
    // Step 4: Give Automation SDK time to sync with iCUE
    logMsg("[INIT] Waiting 500ms for Automation SDK to sync...");
    Sleep(500);
    
    g_initialized = (status == CE_Success);
    logMsg(std::format("[INIT] Initialization result: {}", g_initialized ? "SUCCESS" : "FAILED"));
    
    return g_initialized;
}

// ============================================================================
// Lighting Helper
// ============================================================================

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
// Tries multiple approaches: direct value, presets, and stages
static json cmdSetMouseDpi(const json& args) {
    logMsg("[DPI] ========== cmdSetMouseDpi called ==========");
    logMsg(std::format("[DPI] Args: {}", args.dump()));
    
    if (!ensureInitialized()) {
        logMsg("[DPI] ERROR: ensureInitialized() returned false");
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    int dpi = args.value("dpi", 0);
    logMsg(std::format("[DPI] Requested DPI value: {}", dpi));
    
    if (dpi < 100 || dpi > 26000) {
        logMsg(std::format("[DPI] ERROR: Invalid DPI value {} (must be 100-26000)", dpi));
        return json("Invalid DPI value. Please specify a value between 100 and 26000.");
    }
    
    // =====================================================================
    // DIAGNOSTIC: Query what Automation SDK thinks are DPI-capable devices
    // =====================================================================
    logMsg("[DPI] --- Automation SDK DPI Device Query ---");
    int automationDpiCount = 0;
    AutomationSdkDevice automationDpiDevices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto dpiQueryCode = AutomationSdkGetDpiDevices(automationDpiDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &automationDpiCount);
    logMsg(std::format("[DPI] AutomationSdkGetDpiDevices returned: code={}, count={}", 
        automationErrorToString(dpiQueryCode), automationDpiCount));
    
    if (dpiQueryCode == Success && automationDpiCount > 0) {
        for (int i = 0; i < automationDpiCount; i++) {
            logMsg(std::format("[DPI]   Automation DPI Device {}: id='{}', name='{}'", 
                i, automationDpiDevices[i].id, automationDpiDevices[i].name));
        }
    } else {
        logMsg("[DPI]   WARNING: Automation SDK reports NO DPI-capable devices!");
        logMsg("[DPI]   This could mean:");
        logMsg("[DPI]   - Mouse doesn't support DPI control via Automation SDK");
        logMsg("[DPI]   - iCUE needs to be restarted");
        logMsg("[DPI]   - Mouse firmware may need update");
    }
    
    // =====================================================================
    // Find mouse from iCUE SDK devices
    // =====================================================================
    logMsg("[DPI] --- iCUE SDK Device List ---");
    CorsairDeviceInfo* mouseDevice = nullptr;
    for (int i = 0; i < g_numDevices; i++) {
        logMsg(std::format("[DPI]   iCUE Device {}: model='{}', type={}, id='{}'", 
            i, g_devices[i].model, static_cast<int>(g_devices[i].type), g_devices[i].id));
        if (g_devices[i].type == CDT_Mouse && !mouseDevice) {
            mouseDevice = &g_devices[i];
            logMsg(std::format("[DPI]   ^ Selected as target mouse"));
        }
    }
    
    if (!mouseDevice) {
        logMsg("[DPI] ERROR: No mouse found in iCUE device list");
        return json("No Corsair mouse found. Please connect a Corsair mouse.");
    }
    
    logMsg(std::format("[DPI] Target mouse: '{}', iCUE ID='{}'", mouseDevice->model, mouseDevice->id));
    
    // =====================================================================
    // Check if iCUE mouse ID matches any Automation SDK DPI device
    // =====================================================================
    bool foundInAutomationSdk = false;
    std::string automationSdkId = "";
    for (int i = 0; i < automationDpiCount; i++) {
        if (strcmp(automationDpiDevices[i].id, mouseDevice->id) == 0) {
            foundInAutomationSdk = true;
            automationSdkId = automationDpiDevices[i].id;
            logMsg(std::format("[DPI] MATCH: iCUE mouse ID matches Automation SDK DPI device ID"));
            break;
        }
    }
    if (!foundInAutomationSdk && automationDpiCount > 0) {
        logMsg("[DPI] WARNING: iCUE mouse ID does NOT match any Automation SDK DPI device ID!");
        logMsg("[DPI]   iCUE device IDs and Automation SDK device IDs may be different namespaces.");
        logMsg("[DPI]   Will try using Automation SDK device ID instead...");
        automationSdkId = automationDpiDevices[0].id;  // Use first Automation SDK DPI device
        logMsg(std::format("[DPI]   Using Automation SDK ID: '{}'", automationSdkId));
    }
    
    // Determine which ID to use for DPI calls
    const char* dpiDeviceId = (automationDpiCount > 0 && !foundInAutomationSdk) 
        ? automationSdkId.c_str() 
        : mouseDevice->id;
    logMsg(std::format("[DPI] Using device ID for DPI calls: '{}'", dpiDeviceId));
    
    // Try approach 1: Direct SetDpiValue
    logMsg("[DPI] Approach 1: Trying AutomationSdkSetDpiValue...");
    auto code = AutomationSdkSetDpiValue(dpiDeviceId, dpi);
    logMsg(std::format("[DPI] AutomationSdkSetDpiValue('{}', {}) returned: {}", 
        dpiDeviceId, dpi, automationErrorToString(code)));
    
    if (code == Success) {
        logMsg(std::format("[DPI] SUCCESS via direct SetDpiValue: {} DPI = {}", mouseDevice->model, dpi));
        return json(std::format("Set {} DPI to {}.", mouseDevice->model, dpi));
    }
    logMsg(std::format("[DPI] Approach 1 FAILED: code={}", automationErrorToString(code)));
    
    // Try approach 2: Get DPI presets and find closest match
    logMsg("[DPI] Approach 2: Trying DPI presets...");
    int presetCount = 0;
    AutomationSdkDpiPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetDpiPresets(dpiDeviceId, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetCount);
    logMsg(std::format("[DPI] AutomationSdkGetDpiPresets('{}') returned: code={}, count={}", 
        dpiDeviceId, automationErrorToString(code), presetCount));
    
    if (code == Success && presetCount > 0) {
        // Log available presets
        for (int i = 0; i < presetCount; i++) {
            logMsg(std::format("[DPI]   Preset {}: name='{}', id='{}'", i, presets[i].name, presets[i].id));
        }
        
        // Try to find a preset that matches the requested DPI (by name)
        std::string dpiStr = std::to_string(dpi);
        for (int i = 0; i < presetCount; i++) {
            std::string presetName = presets[i].name;
            if (presetName.find(dpiStr) != std::string::npos) {
                logMsg(std::format("[DPI] Found matching preset: '{}'", presetName));
                code = AutomationSdkActivateDpiPreset(dpiDeviceId, presets[i].id);
                logMsg(std::format("[DPI] AutomationSdkActivateDpiPreset returned: {}", automationErrorToString(code)));
                
                if (code == Success) {
                    return json(std::format("Set {} to DPI preset '{}'.", deviceName, presetName));
                }
            }
        }
        
        // No exact match - list available presets
        std::string presetList = "";
        for (int i = 0; i < presetCount; i++) {
            if (i > 0) presetList += ", ";
            presetList += presets[i].name;
        }
        logMsg(std::format("[DPI] No preset matches {}. Available: {}", dpi, presetList));
    } else {
        logMsg(std::format("[DPI] Approach 2 FAILED: code={}, count={}", automationErrorToString(code), presetCount));
    }
    
    // Try approach 3: DPI stages
    logMsg("[DPI] Approach 3: Trying DPI stages...");
    int stageCount = 0;
    AutomationSdkDpiStage stages[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetDpiStages(dpiDeviceId, stages, AUTOMATION_SDK_ITEMS_COUNT_MAX, &stageCount);
    logMsg(std::format("[DPI] AutomationSdkGetDpiStages('{}') returned: code={}, count={}", 
        dpiDeviceId, automationErrorToString(code), stageCount));
    
    if (code == Success && stageCount > 0) {
        // Log available stages
        for (int i = 0; i < stageCount; i++) {
            logMsg(std::format("[DPI]   Stage {}: name='{}', index={}", 
                i, stages[i].name, static_cast<int>(stages[i].index)));
        }
        
        // Try to find a stage that matches the requested DPI (by name)
        std::string dpiStr = std::to_string(dpi);
        for (int i = 0; i < stageCount; i++) {
            std::string stageName = stages[i].name;
            if (stageName.find(dpiStr) != std::string::npos) {
                logMsg(std::format("[DPI] Found matching stage: '{}'", stageName));
                code = AutomationSdkActivateDpiStage(dpiDeviceId, stages[i].index);
                logMsg(std::format("[DPI] AutomationSdkActivateDpiStage returned: {}", automationErrorToString(code)));
                
                if (code == Success) {
                    return json(std::format("Set {} to DPI stage '{}'.", deviceName, stageName));
                }
            }
        }
        
        // No exact match - try first stage as fallback
        logMsg("[DPI] No matching stage, trying Stage1...");
        code = AutomationSdkActivateDpiStage(dpiDeviceId, Stage1);
        logMsg(std::format("[DPI] AutomationSdkActivateDpiStage(Stage1) returned: {}", automationErrorToString(code)));
        
        if (code == Success) {
            return json(std::format("DPI {} not available on {}. Set to '{}' instead.", 
                dpi, deviceName, stages[0].name));
        }
    } else {
        logMsg(std::format("[DPI] Approach 3 FAILED: code={}, count={}", automationErrorToString(code), stageCount));
    }
    
    // All approaches failed - comprehensive diagnostic summary
    logMsg("[DPI] ========== ALL APPROACHES FAILED - SUMMARY ==========");
    logMsg(std::format("[DPI] Mouse model: {}", mouseDevice->model));
    logMsg(std::format("[DPI] iCUE SDK device ID: {}", mouseDevice->id));
    logMsg(std::format("[DPI] Automation SDK DPI devices found: {}", automationDpiCount));
    logMsg(std::format("[DPI] ID match between iCUE and Automation SDK: {}", foundInAutomationSdk ? "YES" : "NO"));
    logMsg(std::format("[DPI] Device ID used for calls: {}", dpiDeviceId));
    logMsg("[DPI] Possible reasons for failure:");
    logMsg("[DPI]   1. Mouse model not supported by Automation SDK for DPI control");
    logMsg("[DPI]   2. iCUE version may be outdated (needs 5.x+)");
    logMsg("[DPI]   3. iCUE SDK Control may be disabled in iCUE settings");
    logMsg("[DPI]   4. Another application may have exclusive DPI control");
    logMsg("[DPI]   5. Device ID mismatch between iCUE SDK and Automation SDK");
    logMsg("[DPI] Recommendation: Check corsair_plugin.log for full trace");
    logMsg("[DPI] ==========================================================");
    
    return json(std::format(
        "Could not set DPI on {}. Try setting DPI directly in iCUE.", deviceName));
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
        return json(std::format("Unknown color '{}'. Try: red, green, blue, cyan, magenta, yellow, white, orange, purple, pink, gold, teal, gray, or 'off'.", colorName));
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
        if (colorName == "off") {
            result = "Lighting off:\n";
        } else {
            result = std::format("Lighting set to {}:\n", colorName);
        }
        for (const auto& name : updated) {
            result += std::format("- {}\n", name);
        }
    }
    
    if (!failed.empty()) {
        if (!result.empty()) result += "\n";
        result += "Failed:\n";
        for (const auto& name : failed) {
            result += std::format("- {}\n", name);
        }
    }
    
    return json(result);
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
    
    if (code != Success || size == 0) {
        return json("No Corsair headset with EQ support found. Please connect a Corsair headset.");
    }

    // Use first headset
    const auto& device = devices[0];

    // Get available presets
    int presetsSize = 0;
    AutomationSdkEqualizerPreset presets[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    code = AutomationSdkGetEqualizerPresets(device.id, presets, AUTOMATION_SDK_ITEMS_COUNT_MAX, &presetsSize);
    
    if (code != Success || presetsSize == 0) {
        return json(std::format("No EQ presets available for {}.", device.name));
    }
    
    // Find matching preset (case-insensitive)
    std::string lowerPreset = toLowerCase(presetName);
    for (int i = 0; i < presetsSize; i++) {
        if (toLowerCase(presets[i].name) == lowerPreset || 
            toLowerCase(presets[i].name).find(lowerPreset) != std::string::npos) {
            
            code = AutomationSdkActivateEqualizerPreset(device.id, presets[i].id);
            if (code == Success) {
                return json(std::format("Set {} EQ to '{}'.", device.name, presets[i].name));
            } else {
                return json(std::format("Failed to apply EQ preset '{}' to {}.", presets[i].name, device.name));
            }
        }
    }
    
    // Preset not found - list available presets
    std::string available = std::format("EQ preset '{}' not found.\n\nAvailable presets for {}:\n", presetName, device.name);
    for (int i = 0; i < presetsSize; i++) {
        available += std::format("- {}\n", presets[i].name);
    }
    
    return json(available);
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
    
    if (code != Success || size == 0) {
        return json("No iCUE profiles found. Create profiles in iCUE to use this feature.");
    }
    
    // Find matching profile (case-insensitive)
    std::string lowerName = toLowerCase(profileName);
    for (int i = 0; i < size; i++) {
        if (toLowerCase(profiles[i].name) == lowerName ||
            toLowerCase(profiles[i].name).find(lowerName) != std::string::npos) {
            
            code = AutomationSdkActivateProfile(profiles[i].id);
            if (code == Success) {
                return json(std::format("Switched to profile '{}'.", profiles[i].name));
            } else {
                return json(std::format("Failed to switch to profile '{}'.", profiles[i].name));
            }
        }
    }
    
    // Profile not found - list available
    std::string available = std::format("Profile '{}' not found.\n\nAvailable profiles:\n", profileName);
    for (int i = 0; i < size; i++) {
        available += std::format("- {}\n", profiles[i].name);
    }
    
    return json(available);
}

// Get connected devices
static json cmdGetDevices(const json& args) {
    logMsg("[DEVICES] ========== cmdGetDevices called ==========");
    
    if (!ensureInitialized()) {
        logMsg("[DEVICES] ERROR: ensureInitialized() returned false");
        return json("Unable to connect to iCUE. Please ensure iCUE is running and the plugin has permissions.");
    }
    
    logMsg(std::format("[DEVICES] g_numDevices = {}", g_numDevices));
    
    if (g_numDevices == 0) {
        logMsg("[DEVICES] No devices found via CorsairGetDevices");
        return json("No Corsair devices found. Please connect a Corsair device and ensure iCUE is running.");
    }
    
    // Query device capabilities first
    int dpiSize = 0;
    AutomationSdkDevice dpiDevices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto dpiCode = AutomationSdkGetDpiDevices(dpiDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &dpiSize);
    logMsg(std::format("[DEVICES] AutomationSdkGetDpiDevices: code={}, size={}", 
        automationErrorToString(dpiCode), dpiSize));
    
    int eqSize = 0;
    AutomationSdkDevice eqDevices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto eqCode = AutomationSdkGetEqualizerDevices(eqDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &eqSize);
    logMsg(std::format("[DEVICES] AutomationSdkGetEqualizerDevices: code={}, size={}", 
        automationErrorToString(eqCode), eqSize));
    
    int coolSize = 0;
    AutomationSdkDevice coolDevices[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto coolCode = AutomationSdkGetCoolingDevices(coolDevices, AUTOMATION_SDK_ITEMS_COUNT_MAX, &coolSize);
    logMsg(std::format("[DEVICES] AutomationSdkGetCoolingDevices: code={}, size={}", 
        automationErrorToString(coolCode), coolSize));
    
    // Helper to check if device name matches any in a list
    auto hasFeature = [](const char* model, AutomationSdkDevice* devices, int count) {
        for (int i = 0; i < count; i++) {
            if (std::string(model).find(devices[i].name) != std::string::npos ||
                std::string(devices[i].name).find(model) != std::string::npos) {
                return true;
            }
        }
        return false;
    };
    
    // Build device list with per-device features
    std::string result = "Corsair Devices:\n";
    for (int i = 0; i < g_numDevices; i++) {
        logMsg(std::format("[DEVICES] Device {}: model='{}', type={}", 
            i, g_devices[i].model, static_cast<int>(g_devices[i].type)));
        
        // Build feature list for this device
        std::vector<std::string> features;
        if (dpiCode == Success && hasFeature(g_devices[i].model, dpiDevices, dpiSize)) {
            features.push_back("DPI control");
        }
        if (eqCode == Success && hasFeature(g_devices[i].model, eqDevices, eqSize)) {
            features.push_back("EQ presets");
        }
        if (coolCode == Success && hasFeature(g_devices[i].model, coolDevices, coolSize)) {
            features.push_back("cooling presets");
        }
        
        result += std::format("- **{}** ({})\n", g_devices[i].model, getDeviceTypeName(g_devices[i].type));
        if (!features.empty()) {
            result += "  Supports: ";
            for (size_t j = 0; j < features.size(); j++) {
                if (j > 0) result += ", ";
                result += features[j];
            }
            result += "\n";
        }
    }
    
    // Profiles are global to iCUE, not per-device
    logMsg("[DEVICES] Querying profiles...");
    int profileCount = 0;
    AutomationSdkProfile profiles[AUTOMATION_SDK_ITEMS_COUNT_MAX] = {};
    auto profileCode = AutomationSdkGetProfiles(profiles, AUTOMATION_SDK_ITEMS_COUNT_MAX, &profileCount);
    logMsg(std::format("[DEVICES] AutomationSdkGetProfiles returned: {}, count={}", 
        automationErrorToString(profileCode), profileCount));
    
    if (profileCode == Success && profileCount > 0) {
        result += "\nProfiles: ";
        for (int i = 0; i < profileCount; i++) {
            logMsg(std::format("[DEVICES] Profile {}: '{}'", i, profiles[i].name));
            if (i > 0) result += ", ";
            result += profiles[i].name;
        }
        result += "\n";
    }
    
    logMsg("[DEVICES] Returning result");
    return json(result);
}

// ============================================================================
// Main Entry Point
// ============================================================================

// Set up DLL search path to find SDK DLLs in libs/ subfolder
static void setupDllDirectory() {
    wchar_t exePath[MAX_PATH];
    if (GetModuleFileNameW(NULL, exePath, MAX_PATH)) {
        // Find last backslash to get directory
        wchar_t* lastSlash = wcsrchr(exePath, L'\\');
        if (lastSlash) {
            *(lastSlash + 1) = L'\0';  // Keep trailing backslash
            std::wstring libsPath = std::wstring(exePath) + L"libs";
            AddDllDirectory(libsPath.c_str());
            SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS);
        }
    }
}

int main() {
    // Initialize logging first
    initLogging();
    logMsg("========== Corsair Plugin Starting ==========");
    
    // MUST call before any delay-loaded DLL functions
    logMsg("[MAIN] Setting up DLL directory...");
    setupDllDirectory();
    logMsg("[MAIN] DLL directory setup complete");
    
    gassist::Plugin plugin("corsair", "2.0.0", "Control Corsair iCUE devices");
    logMsg("[MAIN] Plugin instance created");
    
    // Register commands
    logMsg("[MAIN] Registering commands...");
    plugin.command("corsair_set_mouse_dpi", cmdSetMouseDpi);
    plugin.command("corsair_set_lighting", cmdSetLighting);
    plugin.command("corsair_set_headset_eq", cmdSetHeadsetEq);
    plugin.command("corsair_set_profile", cmdSetProfile);
    plugin.command("corsair_get_devices", cmdGetDevices);
    logMsg("[MAIN] Commands registered");
    
    // Run the plugin
    logMsg("[MAIN] Starting plugin.run()...");
    plugin.run();
    logMsg("[MAIN] plugin.run() returned");
    
    // Cleanup
    if (g_initialized) {
        CorsairDisconnect();
        AutomationSdkDisconnect();
    }
    
    return 0;
}