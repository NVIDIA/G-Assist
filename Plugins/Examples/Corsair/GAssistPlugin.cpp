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
#include <cstring>
#include <format>
#include <locale>
#include <utility>

#include "GAssistPlugin.h"


const std::string GAssistPlugin::FUNCTION_PROPERTY = "func";
const std::string GAssistPlugin::MESSAGE_PROPERTY = "message";
const std::string GAssistPlugin::MESSAGES_PROPERTY = "messages";
const std::string GAssistPlugin::PARAMETERS_PROPERTY = "params";
const std::string GAssistPlugin::SUCCESS_PROPERTY = "success";
const std::string GAssistPlugin::SYSTEM_INFO_PROPERTY = "system_info";
const std::string GAssistPlugin::TOOL_CALLS_PROPERTY = "tool_calls";

const std::string GAssistPlugin::INITIALIZE_COMMAND = "initialize";
const std::string GAssistPlugin::SHUTDOWN_COMMAND = "shutdown";


GAssistPlugin::GAssistPlugin(HANDLE commandPipe, HANDLE responsePipe)
    : m_commandPipe(commandPipe)
    , m_responsePipe(responsePipe)
    , m_handlers()
{
    // add handlers for specialized functions
    m_handlers[INITIALIZE_COMMAND] = [&](const json&, const json&) { this->initialize(); };
    m_handlers[SHUTDOWN_COMMAND] = [&](const json&, const json&) { this->shutdown(); };
}

GAssistPlugin::~GAssistPlugin()
{
}

int GAssistPlugin::run()
{
    std::string cmd;
    do
    {
        json input;
        if (!readCommand(input))
        {
            continue;
        }

        if (hasRequiredProperties(input))
        {
            json toolCalls = input[TOOL_CALLS_PROPERTY];
            json context = input.contains(MESSAGES_PROPERTY) ? input[MESSAGES_PROPERTY] : json::object();

            for (const auto& call : toolCalls)
            {
                json params = call.contains(PARAMETERS_PROPERTY) ? call[PARAMETERS_PROPERTY] : json::object();
                cmd = toLowerCase(call[FUNCTION_PROPERTY]);
                m_handlers.contains(cmd)
                    ? m_handlers.at(cmd)(params, context)
                    : failure(std::format("Unknown command encountered: {}", cmd));
            }
        }
        else
        {
            failure("Malformed input encountered.");
        }
    } while (cmd != SHUTDOWN_COMMAND);

    return 0;
}

std::string GAssistPlugin::toLowerCase(std::string s)
{
    std::string lower = std::move(s);
    std::transform(lower.begin(), lower.end(), lower.begin(),
        [](unsigned char c) { return std::tolower(c); });
    return lower;
}

void GAssistPlugin::initialize()
{
    success();
}

void GAssistPlugin::shutdown()
{
    success();
}

bool GAssistPlugin::addCommand(const std::string& command, CommandHandler handler)
{
    // do we want to return an error is a subsequent handler for a known
    // command was added, or do we just override what was previously there?
    // if we allow overriding commands, we need to make sure that we do not
    // override reserved commands (i.e. "initialize").
    std::string cmd = toLowerCase(command);
    if (m_handlers.contains(cmd))
    {
        return false;
    }

    m_handlers[cmd] = handler;
    return true;
}

void GAssistPlugin::message(const std::string& message)
{
    json response = createMessage(message);
    writeResponse(response);
}

void GAssistPlugin::success(const std::string& message)
{
    json response = createNotification(true, message);
    writeResponse(response);
}

void GAssistPlugin::failure(const std::string& message)
{
    json response = createNotification(false, message);
    writeResponse(response);
}

bool GAssistPlugin::hasRequiredProperties(const json& input)
{
    // At the minimum, the input needs to have the "tool_calls" property.
    // This property must be 1) an array and 2) the objects in the array must
    // have the "func" property. All other properties are optional.
    if (input.contains(TOOL_CALLS_PROPERTY) && input[TOOL_CALLS_PROPERTY].is_array())
    {
        json toolCalls = input[TOOL_CALLS_PROPERTY];
        return std::all_of(toolCalls.begin(), toolCalls.end(), [](const json& call) {
            return call.contains(FUNCTION_PROPERTY) && call[FUNCTION_PROPERTY].is_string();
            });
    }
    else
    {
        return false;
    }
}

json GAssistPlugin::createMessage(const std::string& message)
{
    json response;
    if (!message.empty())
    {
        response[MESSAGE_PROPERTY] = message;
    }

    return response;
}

json GAssistPlugin::createNotification(bool isSuccess, const std::string& message)
{
    json response;
    response = createMessage(message);
    response[SUCCESS_PROPERTY] = isSuccess;
    return response;
}

bool GAssistPlugin::readCommand(json& input) const
{
    constexpr size_t BUFFER_SIZE = 4096;
    char buffer[BUFFER_SIZE];
    std::memset(buffer, 0, BUFFER_SIZE);
    DWORD bytesRead = 0;

    if (!ReadFile(m_commandPipe, buffer, BUFFER_SIZE - 1, &bytesRead, NULL))
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

void GAssistPlugin::writeResponse(const json& response) const
{
    static const std::string END_TOKEN = "<<END>>";
    auto output = response.dump() + END_TOKEN;
    DWORD bytesWritten = 0;
    WriteFile(m_responsePipe, output.c_str(), static_cast<DWORD>(output.size()), &bytesWritten, NULL);
}
