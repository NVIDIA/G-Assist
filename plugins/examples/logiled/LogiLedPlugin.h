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
#pragma once
#include <stdexcept>
#include <string>

#include "GAssistPlugin.h"
#include "LogitechLEDLib.h"


 /**
  * Specifies a color in its RGB components.
  *
  * The values of each component must be between 0 and 255, inclusive.
  */
struct Color
{
    int red;
    int green;
    int blue;
};


/**
 * Logitech LED Plugin
 *
 * Updates the LEDs on select Logitech keyboards, mice, and headsets.
 */
class LogiLedPlugin : public GAssistPlugin
{
public:
    LogiLedPlugin(HANDLE commandPipe, HANDLE responsePipe);
    virtual ~LogiLedPlugin();

protected:
    /**
     * Command handler for the "initialize" command.
     *
     * @param[in] params - the command parameters
     *
     * @return the result of the command as JSON
     */
    void initialize() override;

    /**
     * Command handler for the "shutdown" command.
     *
     * @param[in] params - the command parameters
     *
     * @return the result of the command as JSON
     */
    void shutdown() override;

private:
    /**
     * Flag specifying if the LogitechLED SDK has been initialized.
     */
    bool m_isInitialized;


    /**
     * Command handler for the "logi_change_headphone_lights" command.
     *
     * @param[in] params - the command parameters
     *
     * @return the result of the command as JSON
     */
    void handleHeadphoneCommand(const json& params);

    /**
     * Command handler for the "logi_change_keyboard_lights" command.
     *
     * @param[in] params - the command parameters
     *
     * @return the result of the command as JSON
     */
    void handleKeyboardCommand(const json& params);

    /**
     * Command handler for the "logi_change_mouse_lights" command.
     *
     * @param[in] params - the command parameters
     *
     * @return the result of the command as JSON
     */
    void handleMouseCommand(const json& params);

    /**
     * Changes the color of a Logitech device.
     *
     * @param[in] device - the Logitech device
     * @param[in] color  - the command parameters
     *
     * @return the result of the command as JSON
     */
    void changeDeviceLighting(const LogiLed::DeviceType type, const json& params);

    /**
     * Extracts the color parameters from the command.
     *
     * The numeric value of the color indicates the percentage. If values outside
     * a percentage are provided, the value is clamped to [0, 100].
     *
     * The function also handles several special "colors". These "colors" are
     * commands `off`, `bright_up`, and `bright_down`, which turn get color
     * value for off (black), increased brightness, and decreased brightness of the
     * LED, respectively.
     *
     * @param[in]     params   - the command parameters
     * @param[in,out] rgbValue - the current/new color
     *
     * @returns `true` if the colors were extracted; `false` otherwise (the value
     * of `colors` is unchanged)
     */
    bool getLedColor(const json& params, Color& rgbValue);

    /**
     * Converts an 8-bit color to percentages.
     *
     * @param[in]  color    - the color
     * @param[out] sdkColor - the color value as a percentage
     */
    void getSdkColor(const Color& color, Color& sdkColor);

    /**
     * Gets the RGB value for a predetermined color string.
     *
     * @param[in]  color    - predefined color string
     * @param[out] rgbValue - the RGB value
     *
     * @throw std::out_of_range if the color string does not match one of the
     * pre-defined values.
     */
    void getRgbValue(const std::string& color, Color& rgbValue);

    /**
     * Changes the color of a Logitech device.
     *
     * @param[in] device - the Logitech device
     * @param[in] color  - the color
     *
     * @return `true` if the lighting was updated; `false` otherwise
     */
    bool doLightingChange(const LogiLed::DeviceType device, const Color& color);
};
