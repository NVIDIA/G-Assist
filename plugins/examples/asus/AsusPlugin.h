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
#include "GAssistPlugin.h"
#include <format>


class AsusPlugin: public GAssistPlugin
{
public:
	AsusPlugin(HANDLE commandPipe, HANDLE responsePipe);
	virtual ~AsusPlugin();

protected:

    void initialize() override;
    void shutdown() override;

private:

    void HandleFanModeCommand(const json& params);
    void HandleModelnameCommand(const json& params);
    void HandleBiosVersionCommand(const json& params);
    void HandleDriverLinkCommand(const json& params);

};