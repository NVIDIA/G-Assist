// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// Hello World G-Assist Plugin (Node.js SDK Version)
//
// A simple example plugin demonstrating the Node.js SDK and JSON-RPC V2 protocol.

const { Plugin } = require('./gassist-sdk');

// Conversation history for passthrough mode
let conversationHistory = [];

// Create the plugin
const plugin = new Plugin('hello-world-nodejs', '1.0.0', 'A simple Node.js example plugin');

// ============================================================================
// Command: say_hello
// Basic command that takes a parameter and returns a greeting
// ============================================================================
plugin.command('say_hello', (args) => {
    const name = args.name || 'World';
    return `Hello, ${name}! Welcome to G-Assist Node.js plugins. 🎉`;
});

// ============================================================================
// Command: count_with_streaming
// Demonstrates streaming output with plugin.stream()
// ============================================================================
plugin.command('count_with_streaming', async (args) => {
    let countTo = args.count_to || 5;
    
    // Clamp to reasonable range
    countTo = Math.max(1, Math.min(20, countTo));
    
    plugin.stream(`Counting to ${countTo}...\n\n`);
    
    for (let i = 1; i <= countTo; i++) {
        plugin.stream(`🔢 ${i}\n`);
        await sleep(300);
    }
    
    plugin.stream(`\n✅ Done counting to ${countTo}!`);
    
    return '';  // All output was streamed
});

// ============================================================================
// Command: start_conversation
// Enters passthrough mode for multi-turn conversations
// ============================================================================
plugin.command('start_conversation', (args) => {
    const topic = args.topic || 'anything';
    
    // Clear previous conversation
    conversationHistory = [];
    conversationHistory.push(`Started conversation about: ${topic}`);
    
    // Enter passthrough mode
    plugin.setKeepSession(true);
    
    return `💬 Starting a conversation about: ${topic}

I'm now in conversation mode! You can:
- Send messages and I'll echo them back
- Type "summary" to see our conversation so far
- Type "exit" to end the conversation

What would you like to say?`;
});

// ============================================================================
// Command: on_input
// Handles follow-up user input in passthrough mode
// ============================================================================
plugin.command('on_input', (args) => {
    let content = (args.content || '').trim();
    const lowerContent = content.toLowerCase();
    
    // Check for exit commands
    if (['exit', 'quit', 'bye', 'done'].includes(lowerContent)) {
        conversationHistory = [];
        plugin.setKeepSession(false);
        return '👋 Goodbye! Conversation ended.';
    }
    
    // Check for summary command
    if (lowerContent === 'summary') {
        const count = conversationHistory.length;
        let summary = `📝 **Conversation Summary** (${count} messages):\n\n`;
        
        conversationHistory.slice(0, 5).forEach((msg, i) => {
            const truncated = msg.length > 50 ? msg.substring(0, 50) + '...' : msg;
            summary += `- ${truncated}\n`;
        });
        
        if (count > 5) {
            summary += '...\n';
        }
        
        summary += '\nContinue chatting or type "exit" to end.';
        plugin.setKeepSession(true);
        return summary;
    }
    
    // Add to conversation history
    conversationHistory.push(content);
    
    // Echo with a twist
    const response = `🗣️ You said: "${content}"

(Message #${conversationHistory.length} in our conversation)`;
    
    // Stay in passthrough mode
    plugin.setKeepSession(true);
    
    return response;
});

// Helper function for delays
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

// Run the plugin
plugin.run();

