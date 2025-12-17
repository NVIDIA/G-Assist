// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// G-Assist Plugin SDK for C++ (Protocol V2 - JSON-RPC 2.0)
//
// Single-header SDK for building G-Assist plugins in C++.
// Requires: nlohmann/json (https://github.com/nlohmann/json)
//
// Usage:
//   #include <nlohmann/json.hpp>
//   #include "gassist_sdk.hpp"
//
//   int main() {
//       gassist::Plugin plugin("my-plugin", "1.0.0");
//       
//       plugin.command("greet", [&](const nlohmann::json& args) {
//           std::string name = args.value("name", "World");
//           return nlohmann::json("Hello, " + name + "!");
//       });
//       
//       plugin.run();
//       return 0;
//   }

#ifndef GASSIST_SDK_HPP
#define GASSIST_SDK_HPP

#include <nlohmann/json.hpp>

#include <string>
#include <map>
#include <functional>
#include <iostream>
#include <fstream>
#include <cstdint>
#include <mutex>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#else
#include <unistd.h>
#endif

namespace gassist {

// Use nlohmann::json directly
using json = nlohmann::json;

// ============================================================================
// Protocol Handler
// ============================================================================

class Protocol {
public:
    static constexpr size_t MAX_MESSAGE_SIZE = 10 * 1024 * 1024; // 10MB

    Protocol() : m_closed(false) {
#ifdef _WIN32
        m_stdin_handle = GetStdHandle(STD_INPUT_HANDLE);
        m_stdout_handle = GetStdHandle(STD_OUTPUT_HANDLE);
        // Set binary mode for stdin/stdout
        _setmode(_fileno(stdin), _O_BINARY);
        _setmode(_fileno(stdout), _O_BINARY);
#endif
    }

    bool read_message(json& out_message) {
        if (m_closed) return false;

        std::lock_guard<std::mutex> lock(m_read_mutex);

        // Read 4-byte length header (big-endian)
        uint8_t header[4];
        if (!read_bytes(header, 4)) {
            m_closed = true;
            return false;
        }

        uint32_t length = (static_cast<uint32_t>(header[0]) << 24) | 
                          (static_cast<uint32_t>(header[1]) << 16) | 
                          (static_cast<uint32_t>(header[2]) << 8) | 
                          static_cast<uint32_t>(header[3]);

        if (length > MAX_MESSAGE_SIZE || length == 0) {
            return false;
        }

        // Read JSON payload
        std::vector<char> buffer(length);
        if (!read_bytes(reinterpret_cast<uint8_t*>(buffer.data()), length)) {
            m_closed = true;
            return false;
        }

        // Parse JSON
        try {
            out_message = json::parse(buffer.begin(), buffer.end());
            return true;
        } catch (...) {
            return false;
        }
    }

    bool write_message(const json& message) {
        if (m_closed) return false;

        std::lock_guard<std::mutex> lock(m_write_mutex);

        // Ensure jsonrpc field
        json msg = message;
        if (!msg.contains("jsonrpc")) {
            msg["jsonrpc"] = "2.0";
        }

        // Serialize to JSON
        std::string payload = msg.dump();

        if (payload.size() > MAX_MESSAGE_SIZE) {
            return false;
        }

        // Create length-prefixed message
        uint32_t length = static_cast<uint32_t>(payload.size());
        uint8_t header[4] = {
            static_cast<uint8_t>((length >> 24) & 0xFF),
            static_cast<uint8_t>((length >> 16) & 0xFF),
            static_cast<uint8_t>((length >> 8) & 0xFF),
            static_cast<uint8_t>(length & 0xFF)
        };

        // Write header + payload
        if (!write_bytes(header, 4)) return false;
        if (!write_bytes(reinterpret_cast<const uint8_t*>(payload.data()), payload.size())) return false;

        return true;
    }

    void close() { m_closed = true; }
    bool is_closed() const { return m_closed; }

private:
    bool read_bytes(uint8_t* buffer, size_t count) {
#ifdef _WIN32
        DWORD bytes_read = 0;
        size_t total_read = 0;
        while (total_read < count) {
            if (!ReadFile(m_stdin_handle, buffer + total_read, 
                         static_cast<DWORD>(count - total_read), &bytes_read, NULL)) {
                return false;
            }
            if (bytes_read == 0) return false;
            total_read += bytes_read;
        }
        return true;
#else
        size_t total_read = 0;
        while (total_read < count) {
            ssize_t n = read(STDIN_FILENO, buffer + total_read, count - total_read);
            if (n <= 0) return false;
            total_read += n;
        }
        return true;
#endif
    }

    bool write_bytes(const uint8_t* buffer, size_t count) {
#ifdef _WIN32
        DWORD bytes_written = 0;
        if (!WriteFile(m_stdout_handle, buffer, static_cast<DWORD>(count), &bytes_written, NULL)) {
            return false;
        }
        FlushFileBuffers(m_stdout_handle);
        return bytes_written == count;
#else
        size_t total_written = 0;
        while (total_written < count) {
            ssize_t n = write(STDOUT_FILENO, buffer + total_written, count - total_written);
            if (n <= 0) return false;
            total_written += n;
        }
        fsync(STDOUT_FILENO);
        return true;
#endif
    }

    bool m_closed;
    std::mutex m_read_mutex;
    std::mutex m_write_mutex;
#ifdef _WIN32
    HANDLE m_stdin_handle;
    HANDLE m_stdout_handle;
#endif
};

// ============================================================================
// Plugin Class
// ============================================================================

class Plugin {
public:
    using CommandHandler = std::function<json(const json& arguments)>;

    Plugin(const std::string& name, const std::string& version, const std::string& description = "")
        : m_name(name), m_version(version), m_description(description),
          m_running(false), m_current_request_id(-1), m_keep_session(false) {
        // Open log file
        std::string log_path = get_plugin_dir() + "\\" + name + ".log";
        m_log_file.open(log_path, std::ios::app);
        log("Plugin '" + name + "' v" + version + " initialized");
    }

    ~Plugin() {
        if (m_log_file.is_open()) {
            m_log_file.close();
        }
    }

    // Register a command handler
    void command(const std::string& name, CommandHandler handler) {
        m_commands[name] = handler;
        log("Registered command: " + name);
    }

    // Send streaming data during command execution
    void stream(const std::string& data) {
        if (m_current_request_id < 0) return;

        json notification;
        notification["jsonrpc"] = "2.0";
        notification["method"] = "stream";
        notification["params"]["request_id"] = m_current_request_id;
        notification["params"]["data"] = data;
        m_protocol.write_message(notification);
    }

    // Set passthrough mode
    void set_keep_session(bool keep) {
        m_keep_session = keep;
    }

    // Run the plugin main loop
    void run() {
        log("Starting plugin main loop");
        m_running = true;

        while (m_running) {
            json message;
            if (!m_protocol.read_message(message)) {
                break;
            }

            handle_message(message);
        }

        log("Plugin stopped");
    }

private:
    std::string get_plugin_dir() {
#ifdef _WIN32
        const char* programdata = std::getenv("PROGRAMDATA");
        if (programdata) {
            return std::string(programdata) + "\\NVIDIA Corporation\\nvtopps\\rise\\plugins\\" + m_name;
        }
        return ".";
#else
        return "/var/lib/gassist/plugins/" + m_name;
#endif
    }

    void log(const std::string& message) {
        if (m_log_file.is_open()) {
            m_log_file << message << std::endl;
            m_log_file.flush();
        }
    }

    void handle_message(const json& message) {
        std::string method = message.value("method", "");
        int id = message.contains("id") ? message["id"].get<int>() : -1;
        json params = message.value("params", json::object());

        log("Received: " + method);

        if (method == "ping") {
            handle_ping(id, params);
        } else if (method == "initialize") {
            handle_initialize(id, params);
        } else if (method == "execute") {
            handle_execute(id, params);
        } else if (method == "input") {
            handle_input(id, params);
        } else if (method == "shutdown") {
            m_running = false;
        }
    }

    void handle_ping(int id, const json& params) {
        json response;
        response["jsonrpc"] = "2.0";
        response["id"] = id;
        response["result"]["timestamp"] = params.value("timestamp", 0);
        m_protocol.write_message(response);
    }

    void handle_initialize(int id, const json& params) {
        log("Initializing...");

        json commands = json::array();
        for (const auto& [name, handler] : m_commands) {
            json cmd;
            cmd["name"] = name;
            cmd["description"] = "";
            commands.push_back(cmd);
        }

        json response;
        response["jsonrpc"] = "2.0";
        response["id"] = id;
        response["result"]["name"] = m_name;
        response["result"]["version"] = m_version;
        response["result"]["description"] = m_description;
        response["result"]["protocol_version"] = "2.0";
        response["result"]["commands"] = commands;
        m_protocol.write_message(response);
        log("Initialization complete");
    }

    void handle_execute(int id, const json& params) {
        std::string function_name = params.value("function", "");
        json arguments = params.value("arguments", json::object());

        log("Executing: " + function_name);

        m_current_request_id = id;
        m_keep_session = false;

        auto it = m_commands.find(function_name);
        if (it == m_commands.end()) {
            send_error(id, -32601, "Unknown command: " + function_name);
            m_current_request_id = -1;
            return;
        }

        try {
            json result = it->second(arguments);
            send_complete(id, true, result);
        } catch (const std::exception& e) {
            send_error(id, -1, e.what());
        }

        m_current_request_id = -1;
    }

    void handle_input(int id, const json& params) {
        std::string content = params.value("content", "");

        log("Input: " + content.substr(0, 50));

        // Send acknowledgment
        json ack;
        ack["jsonrpc"] = "2.0";
        ack["id"] = id;
        ack["result"]["acknowledged"] = true;
        m_protocol.write_message(ack);

        m_current_request_id = id;
        m_keep_session = false;

        auto it = m_commands.find("on_input");
        if (it != m_commands.end()) {
            try {
                json args;
                args["content"] = content;
                json result = it->second(args);
                send_complete(id, true, result);
            } catch (const std::exception& e) {
                send_error(id, -1, e.what());
            }
        } else {
            send_complete(id, true, json("Received: " + content));
        }

        m_current_request_id = -1;
    }

    void send_complete(int request_id, bool success, const json& data) {
        json notification;
        notification["jsonrpc"] = "2.0";
        notification["method"] = "complete";
        notification["params"]["request_id"] = request_id;
        notification["params"]["success"] = success;
        notification["params"]["data"] = data;
        notification["params"]["keep_session"] = m_keep_session;
        m_protocol.write_message(notification);
    }

    void send_error(int request_id, int code, const std::string& message) {
        json notification;
        notification["jsonrpc"] = "2.0";
        notification["method"] = "error";
        notification["params"]["request_id"] = request_id;
        notification["params"]["code"] = code;
        notification["params"]["message"] = message;
        m_protocol.write_message(notification);
    }

    std::string m_name;
    std::string m_version;
    std::string m_description;
    Protocol m_protocol;
    std::map<std::string, CommandHandler> m_commands;
    bool m_running;
    int m_current_request_id;
    bool m_keep_session;
    std::ofstream m_log_file;
};

} // namespace gassist

#endif // GASSIST_SDK_HPP
