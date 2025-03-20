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
#include <functional>
#include <map>
#include <string>

#include <Windows.h>
#include <nlohmann/json.hpp>


using json = nlohmann::json;
using CommandHandler = std::function<void(const json&, const json&)>;


/**
 * Base class for G-Assist plugins.
 *
 * Handles communications with the drivers and dispatching of commands
 * received.
 */
class GAssistPlugin
{
public:
    /**
     * Constructor.
     *
     * @param[in] commandPipe  - handle to the pipe to read commands from
     * @param[in] responsePipe - handle to the pipe to write response to
     */
    GAssistPlugin(HANDLE commandPipe, HANDLE responsePipe);

    /**
     * Destructor.
     */
    virtual ~GAssistPlugin();

    /**
     * Enters the plugin's main processing loop. Plugin exits when it receives
     * the `shutdown` command.
     *
     * @return status code
     */
    int run();

protected:
    /**
     * Converts the specified string to all lower-case letters.
     *
     * @param[in] s - the string
     *
     * @return the lower-case version of the string
     */
    static std::string toLowerCase(std::string s);

    /**
     * Default handler for the initialize command.
     */
    virtual void initialize();

    /**
     * Default handler for the shutdown command.
     */
    virtual void shutdown();

    /**
     * Adds a handler for a plugin command.
     *
     * @param[in] command - the command
     * @param[in] handler - the command handler
     *
     * @return true if the handler was registered; false otherwise
     */
    bool addCommand(const std::string& command, CommandHandler handler);

    /**
     * Send a message to the NVIDIA driver.
     *
     * @param[in] message  message to send
     */
    void message(const std::string& message);

    /**
     * Send a success notification to the NVIDIA driver.
     *
     * @param[in] message - [optional] message to include
     */
    void success(const std::string& message = "");

    /**
     * Send a failure notification to the NVIDIA driver.
     *
     * @param[in] message - [optional] message to include
     */
    void failure(const std::string& message = "");

private:
    /** Key in the command containing the function's name. */
    static const std::string FUNCTION_PROPERTY;

    /** Key in the notification/message containing the message. */
    static const std::string MESSAGE_PROPERTY;

    /** Key in the command containing the context history. */
    static const std::string MESSAGES_PROPERTY;

    /** Key in the command containing the function's parameters. */
    static const std::string PARAMETERS_PROPERTY;

    /** Key in the notification containing the success of the function. */
    static const std::string SUCCESS_PROPERTY;

    /** Key in the command containing the system information. */
    static const std::string SYSTEM_INFO_PROPERTY;

    /** Key in the command containing the function call information. */
    static const std::string TOOL_CALLS_PROPERTY;

    /** The initialize command string. */
    static const std::string INITIALIZE_COMMAND;

    /** The shutdown command string. */
    static const std::string SHUTDOWN_COMMAND;

    /** Handle to the pipe containing commands from the driver. */
    HANDLE m_commandPipe;

    /** Handle to the pipe to send responses to the driver. */
    HANDLE m_responsePipe;

    /** Map of the plugin's commands and handlers. */
    std::map<std::string, CommandHandler> m_handlers;

    /**
     * Validates the input received by the driver to verify the required
     * properties are present.
     *
     * @param[in] input - JSON received from the driver
     *
     * @return Boolean indicating the input has the required properties
     */
    static bool hasRequiredProperties(const json& input);

    /**
     * Creates a message to send to the driver.
     *
     * @param[in] message - [optional] string to send as part of the message
     *
     * @return the message
     */
    static json createMessage(const std::string& message);

    /**
     * Creates a notification to send to the driver.
     *
     * @param[in] isSuccess - Boolean specifying if the notification is to be
     *                        a success or failure notification
     * @param[in] message   - [optional] string to send as part of the
     *                        notification
     */
    static json createNotification(bool isSuccess, const std::string& message = "");

    /**
     * Reads a command from the communication pipe.
     *
     * @param[out] input - location to store the JSON input
     *
     * @return Boolean indicating the read was successful or not
     */
    bool readCommand(json& input) const;

    /**
     * Writes a response to the communication pipe.
     *
     * @param[in] response - the JSON response
     */
    void writeResponse(const json& response) const;
};
