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
#include "LogiLedPlugin.h"


 /**
 * Main entry point.
 *
 * Instantiates a LogiLed plugin and calls its command handling loop.
 *
 * @return 0 if no errors occurred during execution; non-zero if an error occurred
 */
int main()
{
    // The driver creates two pipes when it spawns the plugin's process:
    // - A pipe for the plugin to read commands from
    // - A pipe for the plugin to write responses to
    HANDLE commandPipe = GetStdHandle(STD_INPUT_HANDLE);
    HANDLE responsePipe = GetStdHandle(STD_OUTPUT_HANDLE);

    LogiLedPlugin plugin(commandPipe, responsePipe);
    return plugin.run();
}
