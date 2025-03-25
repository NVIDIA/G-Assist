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
#include <algorithm>
#include <cctype>
#include <format>
#include <map>
#include <stdexcept>
#include <string>

#include <Windows.h>

#include "iCUESDK/iCUESDK.h"
#include "nlohmann/json.hpp"


// Data types
using json = nlohmann::json;
using CommandHandler = json(*)(const json&);

/**
 * Data structure to hold the RGBA values of a color.
 */
struct Color {
    int red;
    int green;
    int blue;
    int alpha;
};


// Function prototypes
static std::string toLowerCase(const std::string&);

static bool readCommand(HANDLE, json&);
static void writeResponse(HANDLE, const json&);

static json generateFailureResponse();
static json generateFailureResponse(const std::string&);
static json generateSuccessResponse();
static json generateSuccessResponse(const std::string&);

static json executeInitializeCommand(const json& params);
static json executeShutdownCommand(const json& params);
static json executeHeadsetCommand(const json&);
static json executeKeyboardCommand(const json&);
static json executeMouseCommand(const json&);

static json changeDeviceLighting(const CorsairDeviceType, const json&);
static bool getDeviceId(const CorsairDeviceType, CorsairDeviceId&);
static bool getLedColor(const json&, Color&);
static bool getRgbaValue(const std::string&, Color&);
static bool doLightingChange(const CorsairDeviceId& id, const Color& color);


// Globals
/**
 * Flag specifying the plugin was initialized.
 */
bool g_isInitialized = false;

/**
 * Info about Corsair keyboard, mice, and headsets.
 */
CorsairDeviceInfo g_devices[CORSAIR_DEVICE_COUNT_MAX];

/**
 * Number of Corsair keyboards, mice, and headsets.
 */
int g_numDevices = 0;


/**
 * Main entry point.
 *
 * Sits in a loop listening to a pipe, waiting for commands to be issued. After
 * receiving the command, it is processed and the result returned. The loop
 * continues until the "shutdown" command is issued.
 *
 * @return 0 if no errors occurred during execution; non-zero if an error occurred
 */
int main()
{
    const std::string TOOLS = "tool_calls";
    const std::string FUNCTION = "func";
    const std::string PARAMETERS = "params";
    const std::string SHUTDOWN = "shutdown";

    const std::string ERROR_MESSAGE = "Failed to update lighting for Corsair device(s).";

    HANDLE hReadPipe = GetStdHandle(STD_INPUT_HANDLE);
    HANDLE hWritePipe = GetStdHandle(STD_OUTPUT_HANDLE);

    const std::map<const std::string, CommandHandler> commands{
        { "initialize", executeInitializeCommand },
        { "shutdown", executeShutdownCommand },
        { "corsair_change_keyboard_lights", executeKeyboardCommand },
        { "corsair_change_mouse_lights", executeMouseCommand },
        { "corsair_change_headphone_lights", executeHeadsetCommand }
    };
    std::string cmd;

    do
    {
        json input;
        json response{ { "success", true } };
        if (!readCommand(hReadPipe, input))
        {
            // Error reading the command. Continuing...
            continue;
        }

        if (input.contains(TOOLS) && input[TOOLS].is_array())
        {
            json function = input[TOOLS][0];
            if (function.contains(FUNCTION) && function[FUNCTION].is_string())
            {
                cmd = toLowerCase(function[FUNCTION]);
                response = commands.contains(cmd)
                    ? commands.at(cmd)(function.contains(PARAMETERS) ? function[PARAMETERS] : json{})
                    : generateFailureResponse(std::format("{} Unknown command: {}.", ERROR_MESSAGE, cmd));
            }
            else
            {
                response = generateFailureResponse(std::format("{} Malformed input.", ERROR_MESSAGE));
            }
        }
        else
        {
            response = generateFailureResponse(std::format("{} Malformed input.", ERROR_MESSAGE));
        }

        writeResponse(hWritePipe, response);
    } while (cmd != SHUTDOWN);

    return 0;
}

/**
 * Returns the string converted to lower case.
 *
 * @param[in] s  the string
 *
 * @return a new string representing the calling string converted to lower case
 */
static std::string toLowerCase(const std::string& s)
{
    std::string lower = s;
    std::transform(lower.begin(), lower.end(), lower.begin(),
        [](unsigned char c) { return std::tolower(c); });
    return lower;
}

/**
 * Reads a command from the communication pipe.
 *
 * @param[in]  hPipe  handle to the pipe to read
 * @param[out] input  location to store the JSON input
 *
 * @return boolean indicating the read was successful or not
 */
static bool readCommand(HANDLE hPipe, json& input)
{
    const size_t BUFFER_SIZE = 4096;
    char buffer[BUFFER_SIZE];
    ZeroMemory(buffer, BUFFER_SIZE);
    DWORD bytesRead = 0;

    if (!ReadFile(hPipe, buffer, BUFFER_SIZE - 1, &bytesRead, NULL))
    {
        return false;
    }

    try
    {
        buffer[bytesRead] = '\0';
        input = json::parse(buffer);
        return true;
    }
    catch (const json::parse_error&)
    {
        return false;
    }
}

/**
 * Writes a response to the communication pipe.
 *
 * @param[in] hPipe     handle to the pipe to write to
 * @param[in] response  the JSON response
 */
static void writeResponse(HANDLE hPipe, const json& response)
{
    auto output = response.dump() + "<<END>>";
    DWORD bytesWritten = 0;
    WriteFile(hPipe, output.c_str(), static_cast<DWORD>(output.size()), &bytesWritten, NULL);
}

/**
 * Generates a response indicating failure.
 *
 * @return JSON response
 */
static json generateFailureResponse()
{
    return { { "success", false } };
}

/**
 * Generates a response indicating failure.
 *
 * @param[in] message  message to be attached to the response
 *
 * @return JSON response
 */
static json generateFailureResponse(const std::string& message)
{
    return {
        { "success", false },
        { "message", message }
    };
}

/**
 * Generates a response indicating success.
 *
 * @return JSON response
 */
static json generateSuccessResponse()
{
    return { { "success", true } };
}

/**
 * Generates a response indicating success.
 *
 * @param[in] message  message to be attached to the response
 *
 * @return JSON response
 */
static json generateSuccessResponse(const std::string& message)
{
    return {
        { "success", true },
        { "message", message }
    };
}

/**
 * Command handler for the "initialize" command.
 *
 * @param[in] params  the command parameters
 *
 * @return the result of the command as JSON
 */
static json executeInitializeCommand(const json& params)
{
    auto callback = [](void* context, const CorsairSessionStateChanged* eventData)
    {
        const int CONNECTION_ATTEMPT_LIMIT = 5;
        static int numTimeouts = 0;
        switch (eventData->state)
        {
        case CSS_Connected:
            const CorsairDeviceFilter filter = static_cast<CorsairDeviceFilter>(CDT_Keyboard | CDT_Mouse | CDT_Headset);
            (void)CorsairGetDevices(&filter, CORSAIR_DEVICE_COUNT_MAX, g_devices, &g_numDevices);
            break;
        case CSS_Timeout:
            ++numTimeouts;
            if (numTimeouts >= CONNECTION_ATTEMPT_LIMIT)
            {
                g_numDevices = 0;
                g_isInitialized = false;
                CorsairDisconnect();
            }
            break;
        default:
            // ignore other states
            break;
        }
    };
    auto status = CorsairConnect(callback, nullptr);
    g_isInitialized = (status == CE_Success);

    const std::string CONFIGURATION_MESSAGE =
        "Oops! The Corsair Illumination Plugin for G-Assist couldn't update your lighting. To fix this:\n"
        "1. Verify the Corsair devices are connected.\n"
        "2. Ensure iCUE is installed and running.\n"
        "3. In iCUE, give permission to the plugin.\n"
        "4. In Windows, go to Settings > Personalization > Dynamic Lighting and disable 'Use Dynamic Lighting on my devices.'\n"
        "5. Close and reopen G-Assist.\n";

    if (!g_isInitialized)
    {
        return generateFailureResponse(CONFIGURATION_MESSAGE);
    }
}

/**
 * Command handler for the "shutdown" command.
 *
 * @param[in] params  the command parameters
 *
 * @return the result of the command as JSON
 */
static json executeShutdownCommand(const json& params)
{
    CorsairDisconnect();
    g_isInitialized = false;
    return generateSuccessResponse();
}

/**
 * Command handler for the "corsair_change_headphone_lights" command.
 *
 * @param[in] params  the command parameters
 *
 * @return the result of the command as JSON
 */
static json executeHeadsetCommand(const json& params)
{
    return changeDeviceLighting(CDT_Headset, params);
}

/**
 * Command handler for the "corsair_change_keyboard_lights" command.
 *
 * @param[in] params  the command parameters
 *
 * @return the result of the command as JSON
 */
static json executeKeyboardCommand(const json& params)
{
    return changeDeviceLighting(CDT_Keyboard, params);
}

/**
 * Command handler for the "corsair_change_mouse_lights" command.
 *
 * @param[in] params  the command parameters
 *
 * @return the result of the command as JSON
 */
static json executeMouseCommand(const json& params)
{
    return changeDeviceLighting(CDT_Mouse, params);
}

/**
 * Changes the color of a Corsair device.
 *
 * @param[in] device  the Corsair device
 * @param[in] color   the command parameters
 *
 * @return the result of the command as JSON
 */
static json changeDeviceLighting(const CorsairDeviceType type, const json& params)
{
    

    if (!g_isInitialized)
    {
        executeInitializeCommand(params);
    }

    const std::map<CorsairDeviceType, std::string> deviceStrings{
        { CDT_Headset, "headset" },
        { CDT_Keyboard, "keyboard" },
        { CDT_Mouse, "mouse" },
    };

    if (!deviceStrings.contains(type))
    {
        return generateFailureResponse("Failed to update lighting for the Corsair device. Unknown device.");
    }

    const auto SUCCESS_MESSAGE = std::format("Corsair {} lighting updated.", deviceStrings.at(type));
    const auto ERROR_MESSAGE = std::format("Failed to update lighting for the Corsair {}.", deviceStrings.at(type));

    Color color = { 0, 0, 0, 0 };
    if (!getLedColor(params, color))
    {
        return generateFailureResponse(std::format("{} Unknown or missing color.", ERROR_MESSAGE));
    }

    CorsairDeviceId deviceId;
    if (!getDeviceId(type, deviceId))
    {
        return generateFailureResponse("Could not communicate to device");
    }

    auto isSuccess = doLightingChange(deviceId, color);
    return isSuccess
        ? generateSuccessResponse(SUCCESS_MESSAGE)
        : generateFailureResponse(ERROR_MESSAGE);
}

/**
 * Extracts the color parameters from the command.
 *
 * The numeric value of the color indicates the percentage. If values outside
 * a percentage are provided, the value is clamped to [0, 100].
 *
 * The function also handles several special "colors". These "colors" are
 * commands `off`, `bright_up`, and `bright_down`, which turn the color
 * value for off (black), increased brigthness, and decreased brightness of the
 * LED, respectively.
 *
 * @param[in]     params     the command parameters
 * @param[in,out] rgbaValue  the current/new color
 *
 * @returns `true` if the colors were extracted; `false` otherwise (the value
 * of `rgbaValue` is unchanged)
 */
static bool getLedColor(const json& params, Color& rgbaValue)
{
    const std::string COLOR = "color";
    const std::string OFF = "off";
    const std::string BRIGHTEN = "bright_up";
    const std::string DIM = "bright_down";
    const std::string RAINBOW = "rainbow";

    const int BRIGHTNESS_LEVEL = 10;

    auto boundBrightness = [](int value)
        {
            const int LOWER = 0;
            const int UPPER = 255;

            return std::clamp(value, LOWER, UPPER);
        };

    if (!params.contains(COLOR) || !params[COLOR].is_string())
    {
        return false;
    }

    std::string color = toLowerCase(params[COLOR]);
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
        if (!getRgbaValue(params[COLOR], rgbaValue))
        {
            return false;
        }

        return true;
    }
}

/**
 * Gets the RGB value for a predetermined color string.
 *
 * @param[in]  color      predefined color string
 * @param[out] rgbaValue  the RGB value
 *
 * @return `true` if the color string was converted into the RGB value;
 * `false` otherwise
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
 * Searches for the device type and returns the associated ID.
 *
 * @param[in]  type  device type
 * @param[out] id    device ID
 *
 * @return `true` if the device type was found and the ID populated; `false`
 * if the device type was not found and the value of `id` is not updated
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
 * Changes the color of a a device.
 *
 * @param[in] device  the device's ID
 * @param[in] colors  the color to change to
 *
 * @return `true` if the device lighting was updated; `false` otherwise
 */
static bool doLightingChange(const CorsairDeviceId& id, const Color& color)
{
    // get the number of LEDs for the device
    CorsairLedPosition leds[CORSAIR_DEVICE_LEDCOUNT_MAX];
    int numLeds = 0;
    auto status = CorsairGetLedPositions(id, CORSAIR_DEVICE_LEDCOUNT_MAX, leds, &numLeds);
    if (status != CE_Success)
    {
        return false;
    }

    // set the color of each LED
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
