#!/usr/bin/env python3
"""
Example G-Assist Plugin using Protocol V2

This plugin demonstrates how to implement the JSON-RPC 2.0 protocol
with length-prefixed framing for communication with the G-Assist engine.
"""

import sys
import json
import struct
import time
from typing import Dict, Any, Optional


# ============================================================================
# Protocol V2 Implementation
# ============================================================================

def encode_message(msg: dict) -> bytes:
    """Encode a message with length-prefix framing"""
    payload = json.dumps(msg).encode('utf-8')
    header = struct.pack('>I', len(payload))
    return header + payload


def decode_length(header: bytes) -> int:
    """Decode 4-byte big-endian length header"""
    return struct.unpack('>I', header)[0]


def send_response(request_id: int, result: Any = None, error: dict = None):
    """Send a JSON-RPC response"""
    msg = {"jsonrpc": "2.0", "id": request_id}
    if error:
        msg["error"] = error
    else:
        msg["result"] = result
    
    sys.stdout.buffer.write(encode_message(msg))
    sys.stdout.buffer.flush()


def send_notification(method: str, params: dict):
    """Send a JSON-RPC notification"""
    msg = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params
    }
    sys.stdout.buffer.write(encode_message(msg))
    sys.stdout.buffer.flush()


def stream(data: str):
    """Send streaming data to engine"""
    send_notification("stream", {"data": data})


def complete(success: bool = True, data: str = "", keep_session: bool = False):
    """Signal completion to engine"""
    send_notification("complete", {
        "success": success,
        "data": data,
        "keep_session": keep_session
    })


def log(level: str, message: str):
    """Send log message to engine"""
    send_notification("log", {"level": level, "message": message})


def error(code: int, message: str):
    """Send error notification to engine"""
    send_notification("error", {"code": code, "message": message})


# ============================================================================
# Plugin Implementation
# ============================================================================

class ExamplePlugin:
    """Example plugin implementation"""
    
    def __init__(self):
        self.session_active = False
        self.user_name = None
    
    def handle_initialize(self, params: dict) -> dict:
        """Handle initialize request"""
        log("info", "Plugin initializing...")
        return {
            "success": True,
            "protocol_version": "2.0",
            "capabilities": ["streaming", "passthrough"]
        }
    
    def handle_shutdown(self, params: dict) -> dict:
        """Handle shutdown request"""
        log("info", "Plugin shutting down...")
        self.session_active = False
        return {"success": True}
    
    def handle_ping(self, params: dict) -> dict:
        """Handle ping request - return pong with timestamp"""
        return {"timestamp": params.get("timestamp", int(time.time() * 1000))}
    
    def handle_execute(self, params: dict):
        """Handle execute request"""
        function = params.get("function", "")
        arguments = params.get("arguments", {})
        
        log("info", f"Executing function: {function}")
        
        if function == "example_greet":
            self.handle_greet(arguments)
        elif function == "example_calculate":
            self.handle_calculate(arguments)
        else:
            error(-32601, f"Unknown function: {function}")
            complete(success=False, data=f"Unknown function: {function}")
    
    def handle_greet(self, args: dict):
        """Handle greet function"""
        name = args.get("name", "World")
        self.user_name = name
        
        # Stream greeting
        stream(f"Hello, {name}! ")
        time.sleep(0.1)  # Simulate some processing
        stream("Welcome to the example plugin. ")
        time.sleep(0.1)
        stream("How can I help you today?\n")
        
        # Stay in passthrough mode for conversation
        complete(success=True, keep_session=True)
        self.session_active = True
    
    def handle_calculate(self, args: dict):
        """Handle calculate function"""
        operation = args.get("operation", "add")
        a = float(args.get("a", 0))
        b = float(args.get("b", 0))
        
        result = None
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                error(-1, "Division by zero")
                complete(success=False, data="Error: Division by zero")
                return
            result = a / b
        else:
            error(-32602, f"Unknown operation: {operation}")
            complete(success=False, data=f"Unknown operation: {operation}")
            return
        
        complete(success=True, data=f"Result: {a} {operation} {b} = {result}")
    
    def handle_input(self, params: dict):
        """Handle user input in passthrough mode"""
        content = params.get("content", "").strip().lower()
        
        # Check for exit commands
        if content in ("exit", "quit", "done", "bye"):
            stream(f"Goodbye{', ' + self.user_name if self.user_name else ''}! ")
            stream("Thanks for using the example plugin.\n")
            complete(success=True, keep_session=False)
            self.session_active = False
            return
        
        # Acknowledge the input
        send_response(self._current_request_id, {"acknowledged": True})
        
        # Process the input
        if "hello" in content or "hi" in content:
            stream(f"Hi{', ' + self.user_name if self.user_name else ''}! ")
            stream("What would you like to do?\n")
        elif "help" in content:
            stream("Available commands:\n")
            stream("  - hello: Say hello\n")
            stream("  - help: Show this help\n")
            stream("  - exit/quit/done: Leave the plugin\n")
            stream("  - Or just chat with me!\n")
        elif "name" in content:
            if self.user_name:
                stream(f"Your name is {self.user_name}.\n")
            else:
                stream("I don't know your name. Tell me!\n")
        else:
            stream(f"You said: '{content}'\n")
            stream("Type 'help' for available commands, or 'exit' to leave.\n")
        
        complete(success=True, keep_session=True)
    
    def run(self):
        """Main plugin loop"""
        log("info", "Example plugin started")
        
        read_buffer = bytearray()
        expected_length = 0
        
        while True:
            try:
                # Read available data
                data = sys.stdin.buffer.read(4096)
                if not data:
                    break
                
                read_buffer.extend(data)
                
                # Process complete messages
                while True:
                    # Need at least 4 bytes for header
                    if len(read_buffer) < 4:
                        break
                    
                    # Read length if needed
                    if expected_length == 0:
                        expected_length = decode_length(bytes(read_buffer[:4]))
                    
                    # Check if we have complete message
                    if len(read_buffer) < 4 + expected_length:
                        break
                    
                    # Extract message
                    json_bytes = bytes(read_buffer[4:4 + expected_length])
                    read_buffer = read_buffer[4 + expected_length:]
                    expected_length = 0
                    
                    # Parse and handle message
                    try:
                        msg = json.loads(json_bytes.decode('utf-8'))
                        self.handle_message(msg)
                    except json.JSONDecodeError as e:
                        log("error", f"JSON parse error: {e}")
                        
            except Exception as e:
                log("error", f"Plugin error: {e}")
                break
        
        log("info", "Example plugin stopped")
    
    def handle_message(self, msg: dict):
        """Handle incoming JSON-RPC message"""
        if msg.get("jsonrpc") != "2.0":
            return
        
        method = msg.get("method", "")
        params = msg.get("params", {})
        request_id = msg.get("id")
        
        self._current_request_id = request_id
        
        if method == "initialize":
            result = self.handle_initialize(params)
            send_response(request_id, result)
        elif method == "shutdown":
            result = self.handle_shutdown(params)
            send_response(request_id, result)
        elif method == "ping":
            result = self.handle_ping(params)
            send_response(request_id, result)
        elif method == "execute":
            self.handle_execute(params)
        elif method == "input":
            self.handle_input(params)
        else:
            send_response(request_id, error={
                "code": -32601,
                "message": f"Method not found: {method}"
            })


if __name__ == "__main__":
    plugin = ExamplePlugin()
    plugin.run()

