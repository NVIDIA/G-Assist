// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0
//
// G-Assist Plugin SDK for Node.js (Protocol V2 - JSON-RPC 2.0)
//
// Usage:
//   const { Plugin } = require('./gassist-sdk');
//
//   const plugin = new Plugin('my-plugin', '1.0.0');
//
//   plugin.command('greet', (args) => {
//       return `Hello, ${args.name || 'World'}!`;
//   });
//
//   plugin.run();

const fs = require('fs');
const path = require('path');

// ============================================================================
// Protocol Handler
// ============================================================================

class Protocol {
    constructor() {
        this.MAX_MESSAGE_SIZE = 10 * 1024 * 1024; // 10MB
        this.closed = false;
        this.buffer = Buffer.alloc(0);
    }

    async readMessage() {
        if (this.closed) return null;

        try {
            // Read 4-byte length header
            const header = await this._readBytes(4);
            if (!header) {
                this.closed = true;
                return null;
            }

            const length = header.readUInt32BE(0);

            if (length > this.MAX_MESSAGE_SIZE || length === 0) {
                throw new Error(`Invalid message length: ${length}`);
            }

            // Read JSON payload
            const payload = await this._readBytes(length);
            if (!payload) {
                this.closed = true;
                return null;
            }

            // Parse JSON
            const message = JSON.parse(payload.toString('utf-8'));
            return message;

        } catch (err) {
            if (err.message !== 'EOF') {
                console.error('Protocol read error:', err.message);
            }
            this.closed = true;
            return null;
        }
    }

    writeMessage(message) {
        if (this.closed) return false;

        try {
            // Ensure jsonrpc field
            if (!message.jsonrpc) {
                message.jsonrpc = '2.0';
            }

            // Serialize to JSON
            const payload = Buffer.from(JSON.stringify(message), 'utf-8');

            if (payload.length > this.MAX_MESSAGE_SIZE) {
                return false;
            }

            // Create length-prefixed message
            const header = Buffer.alloc(4);
            header.writeUInt32BE(payload.length, 0);

            // Write to stdout
            process.stdout.write(header);
            process.stdout.write(payload);

            return true;
        } catch (err) {
            console.error('Protocol write error:', err.message);
            return false;
        }
    }

    close() {
        this.closed = false;
    }

    _readBytes(count) {
        return new Promise((resolve, reject) => {
            const tryRead = () => {
                // Check if we have enough data in buffer
                if (this.buffer.length >= count) {
                    const result = this.buffer.slice(0, count);
                    this.buffer = this.buffer.slice(count);
                    resolve(result);
                    return;
                }

                // Need more data
                const chunk = process.stdin.read();
                if (chunk) {
                    this.buffer = Buffer.concat([this.buffer, chunk]);
                    tryRead();
                } else {
                    // Wait for more data
                    process.stdin.once('readable', tryRead);
                    process.stdin.once('end', () => resolve(null));
                    process.stdin.once('error', reject);
                }
            };

            tryRead();
        });
    }
}

// ============================================================================
// Plugin Class
// ============================================================================

class Plugin {
    constructor(name, version, description = '') {
        this.name = name;
        this.version = version;
        this.description = description;

        this.protocol = new Protocol();
        this.commands = new Map();
        this.running = false;
        this.currentRequestId = null;
        this.keepSession = false;

        // Setup logging
        this.logFile = null;
        this._setupLogging();

        this.log(`Plugin '${name}' v${version} initialized`);
    }

    _setupLogging() {
        const pluginDir = this._getPluginDir();
        try {
            if (!fs.existsSync(pluginDir)) {
                fs.mkdirSync(pluginDir, { recursive: true });
            }
            const logPath = path.join(pluginDir, `${this.name}.log`);
            this.logFile = fs.createWriteStream(logPath, { flags: 'a' });
        } catch (err) {
            // Ignore logging errors
        }
    }

    _getPluginDir() {
        const programData = process.env.PROGRAMDATA || process.env.HOME || '.';
        if (process.platform === 'win32') {
            return path.join(programData, 'NVIDIA Corporation', 'nvtopps', 'rise', 'plugins', this.name);
        }
        return path.join(programData, '.gassist', 'plugins', this.name);
    }

    log(message) {
        const timestamp = new Date().toISOString();
        const line = `${timestamp} ${message}\n`;
        if (this.logFile) {
            this.logFile.write(line);
        }
    }

    /**
     * Register a command handler
     * @param {string} name - Command name
     * @param {function} handler - Handler function (args) => result
     */
    command(name, handler) {
        this.commands.set(name, handler);
        this.log(`Registered command: ${name}`);
    }

    /**
     * Send streaming data during command execution
     * @param {string} data - Data to stream
     */
    stream(data) {
        if (this.currentRequestId === null) return;

        this.protocol.writeMessage({
            jsonrpc: '2.0',
            method: 'stream',
            params: {
                request_id: this.currentRequestId,
                data: data
            }
        });
    }

    /**
     * Set passthrough mode
     * @param {boolean} keep - Whether to keep session open
     */
    setKeepSession(keep) {
        this.keepSession = keep;
    }

    /**
     * Run the plugin main loop
     */
    async run() {
        this.log('Starting plugin main loop');
        this.running = true;

        // Set stdin to raw mode for binary reading
        if (process.stdin.setRawMode) {
            process.stdin.setRawMode(true);
        }
        process.stdin.resume();

        while (this.running) {
            const message = await this.protocol.readMessage();
            if (!message) break;

            await this._handleMessage(message);
        }

        this.log('Plugin stopped');
        process.exit(0);
    }

    async _handleMessage(message) {
        const method = message.method || '';
        const id = message.id;
        const params = message.params || {};

        this.log(`Received: ${method}`);

        switch (method) {
            case 'ping':
                this._handlePing(id, params);
                break;
            case 'initialize':
                this._handleInitialize(id, params);
                break;
            case 'execute':
                await this._handleExecute(id, params);
                break;
            case 'input':
                await this._handleInput(id, params);
                break;
            case 'shutdown':
                this.running = false;
                break;
        }
    }

    _handlePing(id, params) {
        this.protocol.writeMessage({
            jsonrpc: '2.0',
            id: id,
            result: { timestamp: params.timestamp }
        });
    }

    _handleInitialize(id, params) {
        this.log('Initializing...');

        const commands = [];
        for (const [name, handler] of this.commands) {
            commands.push({ name, description: '' });
        }

        this.protocol.writeMessage({
            jsonrpc: '2.0',
            id: id,
            result: {
                name: this.name,
                version: this.version,
                description: this.description,
                protocol_version: '2.0',
                commands: commands
            }
        });

        this.log('Initialization complete');
    }

    async _handleExecute(id, params) {
        const functionName = params.function || '';
        const args = params.arguments || {};

        this.log(`Executing: ${functionName}`);

        this.currentRequestId = id;
        this.keepSession = false;

        const handler = this.commands.get(functionName);
        if (!handler) {
            this._sendError(id, -32601, `Unknown command: ${functionName}`);
            this.currentRequestId = null;
            return;
        }

        try {
            const result = await handler(args);
            this._sendComplete(id, true, result);
        } catch (err) {
            this._sendError(id, -1, err.message);
        }

        this.currentRequestId = null;
    }

    async _handleInput(id, params) {
        const content = params.content || '';

        this.log(`Input: ${content.substring(0, 50)}`);

        // Send acknowledgment
        this.protocol.writeMessage({
            jsonrpc: '2.0',
            id: id,
            result: { acknowledged: true }
        });

        this.currentRequestId = id;
        this.keepSession = false;

        const handler = this.commands.get('on_input');
        if (handler) {
            try {
                const result = await handler({ content });
                this._sendComplete(id, true, result);
            } catch (err) {
                this._sendError(id, -1, err.message);
            }
        } else {
            this._sendComplete(id, true, `Received: ${content}`);
        }

        this.currentRequestId = null;
    }

    _sendComplete(requestId, success, data) {
        this.protocol.writeMessage({
            jsonrpc: '2.0',
            method: 'complete',
            params: {
                request_id: requestId,
                success: success,
                data: data,
                keep_session: this.keepSession
            }
        });
    }

    _sendError(requestId, code, message) {
        this.protocol.writeMessage({
            jsonrpc: '2.0',
            method: 'error',
            params: {
                request_id: requestId,
                code: code,
                message: message
            }
        });
    }
}

module.exports = { Plugin, Protocol };

