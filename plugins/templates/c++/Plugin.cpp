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
#include <sstream>
#include "Plugin.h"


Plugin::Plugin(HANDLE commandPipe, HANDLE responsePipe)
    : GAssistPlugin(commandPipe, responsePipe)
{
    addCommand("my_command", [&](const json& params, const json& context) { this->handleCommand(params, context); });
}

Plugin::~Plugin()
{
}

void Plugin::initialize()
{
    success("Plugin::initialize() executed");
}

void Plugin::shutdown()
{
    success("Plugin::shutdown() executed.");
}

void Plugin::handleCommand(const json& params, const json& context)
{
    std::stringstream ss;
    for (auto& p : params.items())
    {
        ss << "params[" << p.key() << "] = " << p.value() << '\n';
    }
    success("Plugin::handleCommand() executed.\n" + ss.str());
}
