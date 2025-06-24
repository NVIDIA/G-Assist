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

#include "AsusFanControl.h"
#include "AsusInfo.h"
#include "AsusPlugin.h"

AsusPlugin::AsusPlugin(HANDLE commandPipe, HANDLE responsePipe)
    : GAssistPlugin(commandPipe, responsePipe)
{
    addCommand("asus_change_fan_mode", [&](const json& params, const json& context) { this->HandleFanModeCommand(params); });
    addCommand("asus_get_model_name", [&](const json& params, const json& context) { this->HandleModelnameCommand(params); });
    addCommand("asus_get_BIOS_version", [&](const json& params, const json& context) { this->HandleBiosVersionCommand(params); });
    addCommand("asus_get_driverhub_link", [&](const json& params, const json& context) { this->HandleDriverLinkCommand(params); });

}

AsusPlugin::~AsusPlugin()
{
}

void AsusPlugin::initialize()
{
    return;
}


void AsusPlugin::shutdown()
{
    success();
    return;
}

void AsusPlugin::HandleFanModeCommand(const json& params)
{
    AsusFanControl control = AsusFanControl();

    const auto ERROR_MESSAGE = std::format("Failed to update motherboard fan settings.");

    std::string strModeIndex = "", strMode = "";
    if (!control.getFanMode(params, strModeIndex, strMode))
    {
        failure(std::format("{} Unknown fan mode: {}.", ERROR_MESSAGE, strMode));
        return;
    }

    const auto SUCCESS_MESSAGE = std::format("ASUS Fan Control has been successfully updated and is now operating in {} mode.", strMode);

    if (control.SendCmdToFanXpertPage(strModeIndex) != 0)
        success(SUCCESS_MESSAGE);
    else
        failure(std::format("{} Please ensure that both AI Suite SDK and ASUS Framework are installed. After installation, restart your system and attempt the operation again.", ERROR_MESSAGE));

    return;
}

void AsusPlugin::HandleModelnameCommand(const json& params)
{
    AsusInfo control = AsusInfo();
    
    std::string strName;
    if (control.checkASUSModel())
    {
        strName = control.getModelName();
        const auto SUCCESS_MESSAGE = std::format("This system is identified as using an ASUS motherboard.\nModel Name: {}", strName);
        success(SUCCESS_MESSAGE);
    }
    else
    {
        const auto ERROR_MESSAGE = std::format("");
        failure(std::format("Unfortunately, we are only able to provide support for ASUS hardware. Thank you for your understanding.", ERROR_MESSAGE));
    }

    return;

}

void AsusPlugin::HandleBiosVersionCommand(const json& params)
{
    AsusInfo control = AsusInfo();

    std::string strName;
    if (control.checkASUSModel())
    {
        strName = control.getBIOSVersion();
        const auto SUCCESS_MESSAGE = std::format("This system is identified as using an ASUS motherboard.\nBIOS version: {}", strName);
        success(SUCCESS_MESSAGE);
    }
    else
    {
        const auto ERROR_MESSAGE = std::format("");
        failure(std::format("Unfortunately, we are only able to provide support for ASUS hardware. Thank you for your understanding.", ERROR_MESSAGE));
    }

    return;
}

void AsusPlugin::HandleDriverLinkCommand(const json& params)
{
    AsusInfo control = AsusInfo();

    std::string strName;
    if (control.checkASUSModel())
    {
        strName = control.getModelName();
        const auto SUCCESS_MESSAGE = std::format("Please visit our official website to download the latest drivers and software for your ASUS motherboard : https://driverhub.asus.com \n");
        success(SUCCESS_MESSAGE);
    }
    else
    {
        const auto ERROR_MESSAGE = std::format("");
        failure(std::format("Unfortunately, we are only able to provide support for ASUS hardware. Thank you for your understanding.", ERROR_MESSAGE));
    }

    return;
}