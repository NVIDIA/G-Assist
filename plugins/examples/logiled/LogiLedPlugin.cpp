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
#include <cmath>
#include <cstring>
#include <format>
#include <map>
#include <vector>

#include <Windows.h>
#include <cfgmgr32.h>
#include <devguid.h>
#include <SetupAPI.h>
#include <fstream>
#include <filesystem>
#include "LogiLedPlugin.h"

LogiLedPlugin::LogiLedPlugin(HANDLE commandPipe, HANDLE responsePipe)
    : GAssistPlugin(commandPipe, responsePipe)
    , m_isInitialized(false)
{
    addCommand("logi_change_headphone_lights", [&](const json& params, const json& context) { this->handleHeadphoneCommand(params); });
    addCommand("logi_change_keyboard_lights", [&](const json& params, const json& context) { this->handleKeyboardCommand(params); });
    addCommand("logi_change_mouse_lights", [&](const json& params, const json& context) { this->handleMouseCommand(params); });
}

LogiLedPlugin::~LogiLedPlugin()
{
}

void LogiLedPlugin::initialize()
{
    m_isInitialized = LogiLedInit();
    if (!m_isInitialized)
    {
        //
        // At least one Logitech device was found; however, the plugin could
        // not establish communication with Logitech G Hub. Inform the user
        // of the issue and possible remedies the first time the function
        // is called. All future calls will return a failure with not reason.
        //
        const std::string CONFIGURATION_MESSAGE =
            "Oops! The Logitech Illumination Plugin for G-Assist couldn't update your lighting. To fix this:\n"
            "1. Ensure Logitech G Hub is installed and running.\n"
            "2. In G Hub, enable 'Allow programs to control lighting' (Settings > Allow Games and Applications to Control Illumination).\n"
            "3. In Windows, go to Settings > Personalization > Dynamic Lighting and disable 'Use Dynamic Lighting on my devices.'\n\n"
            "4. Close and reopen G-Assist.\n";
        failure(CONFIGURATION_MESSAGE);
    }
}


void LogiLedPlugin::shutdown()
{
    LogiLedShutdown();
    m_isInitialized = false;
    success();
}

void LogiLedPlugin::handleHeadphoneCommand(const json& params)
{
    changeDeviceLighting(LogiLed::DeviceType::Headset, params);
}

void LogiLedPlugin::handleKeyboardCommand(const json& params)
{
    changeDeviceLighting(LogiLed::DeviceType::Keyboard, params);
}

void LogiLedPlugin::handleMouseCommand(const json& params)
{
    changeDeviceLighting(LogiLed::DeviceType::Mouse, params);
}

void LogiLedPlugin::changeDeviceLighting(const LogiLed::DeviceType type, const json& params)
{

    if (!m_isInitialized)
    {
        initialize();
    }

    const std::map<LogiLed::DeviceType, std::string> deviceStrings{
        { LogiLed::DeviceType::Headset, "headset" },
        { LogiLed::DeviceType::Keyboard, "keyboard" },
        { LogiLed::DeviceType::Mouse, "mouse" },
    };

    if (!deviceStrings.contains(type))
    {
        failure("Failed to update lighting for the Logitech device. Unknown device.");
        return;
    }

    const auto SUCCESS_MESSAGE = std::format("Logitech {} lighting updated.", deviceStrings.at(type));
    const auto ERROR_MESSAGE = std::format("Failed to update lighting for the Logitech {}.", deviceStrings.at(type));

    Color color = { 0, 0, 0 };
    if (!getLedColor(params, color))
    {
        failure(std::format("{} Unknown or missing color.", ERROR_MESSAGE));
        return;
    }

    if (doLightingChange(type, color))
    {
        success(SUCCESS_MESSAGE);
    }
    else
    {
        failure(ERROR_MESSAGE);
    }
}

bool LogiLedPlugin::getLedColor(const json& params, Color& rgbValue)
{
    const std::string COLOR = "color";
    const std::string OFF = "off";
    const std::string BRIGHTEN = "bright_up";
    const std::string DIM = "bright_down";
    const std::string RAINBOW = "rainbow";

    if (!params[COLOR].is_string())
    {
        return false;
    }

    std::string clr = toLowerCase(params[COLOR]);
    Color rawRgbValue;
    if (clr == OFF)
    {
        const std::string OFF_COLOR = "black";
        getRgbValue(OFF_COLOR, rawRgbValue);
        getSdkColor(rawRgbValue, rgbValue);
    }
    else if (clr == BRIGHTEN || clr == DIM || clr == RAINBOW)
    {
    }
    else
    {
        try
        {
            getRgbValue(params[COLOR], rawRgbValue);
            getSdkColor(rawRgbValue, rgbValue);
        }
        catch (const std::out_of_range&)
        {
            return false;
        }
    }

    return true;
}

void LogiLedPlugin::getRgbValue(const std::string& color, Color& rgbValue)
{
    static const std::map<std::string, Color> colorMap
    {
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

    std::string key = toLowerCase(color);
    rgbValue = colorMap.at(key);
}

void LogiLedPlugin::getSdkColor(const Color& color, Color& sdkColor)
{
    auto toPercentage = [](int value)
        {
            return static_cast<int>(std::round(static_cast<double>(value) * 100.0 / 255.0));
        };

    sdkColor.red = toPercentage(color.red);
    sdkColor.green = toPercentage(color.green);
    sdkColor.blue = toPercentage(color.blue);
}

bool LogiLedPlugin::doLightingChange(const LogiLed::DeviceType device, const Color& color)
{
    const int MAX_ZONES = 10;
    for (int zone = 0; zone < MAX_ZONES; ++zone)
    {
        if (!LogiLedSetLightingForTargetZone(device, zone, color.red, color.green, color.blue))
        {
            if (zone == 0)
            {
                return false;
            }
            break;
        }
    }

    return true;
}
