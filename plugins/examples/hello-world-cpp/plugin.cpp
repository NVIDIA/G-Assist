// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Hello World G-Assist Plugin (C++ SDK Version)
//
// A simple example plugin demonstrating the C++ SDK and JSON-RPC V2 protocol.
//
// Build with CMake:
//   mkdir build && cd build
//   cmake .. -G "Visual Studio 17 2022" -A x64
//   cmake --build . --config Release

#include "gassist_sdk.hpp"

#include <string>
#include <thread>
#include <chrono>
#include <vector>
#include <algorithm>
#include <cctype>

// Use the json type from gassist namespace (which is nlohmann::json)
using gassist::json;

// Conversation history for passthrough mode
std::vector<std::string> conversation_history;

int main() {
    // Create the plugin
    gassist::Plugin plugin("hello-world-cpp", "1.0.0", "A simple C++ example plugin");
    
    // ========================================================================
    // Command: say_hello
    // Basic command that takes a parameter and returns a greeting
    // ========================================================================
    plugin.command("say_hello", [&](const json& args) -> json {
        std::string name = args.value("name", "World");
        return json("Hello, " + name + "! Welcome to G-Assist C++ plugins.");
    });
    
    // ========================================================================
    // Command: count_with_streaming
    // Demonstrates streaming output with plugin.stream()
    // ========================================================================
    plugin.command("count_with_streaming", [&](const json& args) -> json {
        int count_to = args.value("count_to", 5);
        
        // Clamp to reasonable range
        if (count_to < 1) count_to = 1;
        if (count_to > 20) count_to = 20;
        
        plugin.stream("Counting to " + std::to_string(count_to) + "...\n\n");
        
        for (int i = 1; i <= count_to; i++) {
            plugin.stream(std::to_string(i) + "\n");
            std::this_thread::sleep_for(std::chrono::milliseconds(300));
        }
        
        plugin.stream("\nDone counting to " + std::to_string(count_to) + "!");
        
        return json("");  // All output was streamed
    });
    
    // ========================================================================
    // Command: start_conversation
    // Enters passthrough mode for multi-turn conversations
    // ========================================================================
    plugin.command("start_conversation", [&](const json& args) -> json {
        std::string topic = args.value("topic", "anything");
        
        // Clear previous conversation
        conversation_history.clear();
        conversation_history.push_back("Started conversation about: " + topic);
        
        // Enter passthrough mode
        plugin.set_keep_session(true);
        
        return json("Starting a conversation about: " + topic + "\n\n"
               "I'm now in conversation mode! You can:\n"
               "- Send messages and I'll echo them back\n"
               "- Type \"summary\" to see our conversation so far\n"
               "- Type \"exit\" to end the conversation\n\n"
               "What would you like to say?");
    });
    
    // ========================================================================
    // Command: on_input
    // Handles follow-up user input in passthrough mode
    // ========================================================================
    plugin.command("on_input", [&](const json& args) -> json {
        std::string content = args.value("content", "");
        
        // Trim whitespace
        size_t start = content.find_first_not_of(" \t\n\r");
        size_t end = content.find_last_not_of(" \t\n\r");
        if (start != std::string::npos && end != std::string::npos) {
            content = content.substr(start, end - start + 1);
        }
        
        // Convert to lowercase for comparison
        std::string lower_content = content;
        std::transform(lower_content.begin(), lower_content.end(), lower_content.begin(),
                      [](unsigned char c){ return std::tolower(c); });
        
        // Check for exit commands
        if (lower_content == "exit" || lower_content == "quit" || 
            lower_content == "bye" || lower_content == "done") {
            conversation_history.clear();
            plugin.set_keep_session(false);
            return json("Goodbye! Conversation ended.");
        }
        
        // Check for summary command
        if (lower_content == "summary") {
            std::string summary = "Conversation Summary (" + 
                                  std::to_string(conversation_history.size()) + " messages):\n\n";
            
            int count = 0;
            for (const auto& msg : conversation_history) {
                if (++count > 5) {
                    summary += "...\n";
                    break;
                }
                std::string truncated = msg.length() > 50 ? msg.substr(0, 50) + "..." : msg;
                summary += "- " + truncated + "\n";
            }
            
            summary += "\nContinue chatting or type 'exit' to end.";
            plugin.set_keep_session(true);
            return json(summary);
        }
        
        // Add to conversation history
        conversation_history.push_back(content);
        
        // Echo with a twist
        std::string response = "You said: \"" + content + "\"\n\n"
                              "(Message #" + std::to_string(conversation_history.size()) + 
                              " in our conversation)";
        
        // Stay in passthrough mode
        plugin.set_keep_session(true);
        
        return json(response);
    });
    
    // Run the plugin
    plugin.run();
    
    return 0;
}
