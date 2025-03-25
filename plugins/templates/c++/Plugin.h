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

class Plugin : public GAssistPlugin
{
public:
    /**
     * Constructor.
     *
     * @param[in] commandPipe  - handle to the pipe to read commands from
     * @param[in] responsePipe - handle to the pipe to write response to
     */
    Plugin(HANDLE commandPipe, HANDLE responsePipe);

    /**
     * Destructor.
     */
    ~Plugin();

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
     * Command handler for the command.
     *
     * @param[in] params - the command parameters
     * @param[in] context - the AI context
     *
     * @return the result of the command as JSON
     */
    void handleCommand(const json& params, const json& context);
};
