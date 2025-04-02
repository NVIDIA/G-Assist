import os
import sys
import json
import subprocess
import threading
import shutil
import time
import tempfile
from flask import Flask, request, jsonify
from flask_cors import CORS
from rise import rise

# Create a Flask server to handle API requests from the Electron app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize RISE client
try:
    rise.register_rise_client()
    print("RISE client initialization commented out")
except Exception as e:
    print(f"Error initializing RISE client: {str(e)}")
    sys.exit(1)

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """API endpoint to send messages to RISE"""
    data = request.json
    message = data.get('message', '')
    adapter = data.get('adapter', '')
    system_prompt = data.get('system_prompt', '')
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    try:
        # Send message to RISE
        response = rise.send_rise_command(message, adapter, system_prompt)
        #response = f"RISE module is commented out. Your message was: {message}"
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def start_electron_app():
    """Start the Electron app"""
    # Create temp directory for the Electron app
    temp_dir = tempfile.mkdtemp(prefix='rise_electron_')
    electron_dir = os.path.join(temp_dir, 'rise-electron-app')
    print(electron_dir)
    # Create the base directory and public directory
    os.makedirs(os.path.join(electron_dir, 'public'), exist_ok=True)
    
    # Check if the index.html file exists
    if not os.path.exists(os.path.join(electron_dir, 'public', 'index.html')):
        print("Creating Electron app directory structure...")
        
        # Check if npm and npx are installed
        try:
            # Check if npm is available
            subprocess.run(['npm', '--version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Initialize a new Electron React app
            subprocess.run(['npx', 'create-react-app', electron_dir], check=True)
            
            # Install Electron and other dependencies
            subprocess.run(['npm', 'install', '--save', 'electron', 'electron-builder', 'concurrently', 'wait-on', 'axios', 'chart.js@4.4.2'], 
                          cwd=electron_dir, check=True)
            
            # Create Electron main.js file
            os.makedirs(os.path.join(electron_dir, 'public'), exist_ok=True)
            with open(os.path.join(electron_dir, 'public', 'electron.js'), 'w') as f:
                f.write('''
const { app, BrowserWindow } = require('electron');
const path = require('path');
const url = require('url');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    frame: false,
    transparent: false,
    titleBarStyle: 'hidden',
    backgroundColor: '#0a0a0f'
  });

  const startUrl = process.env.ELECTRON_START_URL || url.format({
    pathname: path.join(__dirname, '../build/index.html'),
    protocol: 'file:',
    slashes: true
  });
  
  mainWindow.loadURL(startUrl);
  mainWindow.setTitle('RISE');

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

app.on('ready', createWindow);

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', function () {
  if (mainWindow === null) {
    createWindow();
  }
});
''')
            
            # Update package.json
            package_path = os.path.join(electron_dir, 'package.json')
            with open(package_path, 'r') as f:
                package_data = json.load(f)
            
            package_data['main'] = 'public/electron.js'
            package_data['scripts']['electron-dev'] = 'concurrently "BROWSER=none npm start" "wait-on http://localhost:3000 && electron ."'
            package_data['scripts']['electron-build'] = 'npm run build && electron-builder'
            
            with open(package_path, 'w') as f:
                json.dump(package_data, f, indent=2)
            
            # Create src directory if it doesn't exist
            os.makedirs(os.path.join(electron_dir, 'src'), exist_ok=True)
            # Create a basic React component for the chat interface
            with open(os.path.join(electron_dir, 'src', 'App.js'), 'w') as f:
                f.write('''
import React, { useState, useEffect, useRef } from 'react';
import Chart from 'chart.js/auto';
import axios from 'axios';
import './App.css';

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('Ready');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    // Add welcome message
    setMessages([
      { type: 'system', text: 'Welcome to the RISE. How can I assist you today?' }
    ]);
    
    // Focus the input field on load
    inputRef.current?.focus();
  }, []);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { type: 'user', text: input };
    setMessages([...messages, userMessage]);
    setInput('');
    setStatus('Processing');
    setIsTyping(true);

    try {
      const response = await axios.post('http://localhost:5000/api/send-message', {
        message: input.trim()
      });
      
      setMessages(prev => [...prev, { type: 'assistant', text: response.data.response }]);
      setStatus('Ready');
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, { 
        type: 'system', 
        text: `Error communicating with RISE: ${error.response?.data?.error || error.message}` 
      }]);
      setStatus('Error: Communication failed');
    } finally {
      setIsTyping(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      sendMessage(e);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <div className="drag-region">
          <h1>RISE</h1>
        </div>
        <div className="window-controls">
          <button className="minimize">_</button>
          <button className="maximize">□</button>
          <button className="close">×</button>
        </div>
      </header>
      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.type}`}>
              <div className={`message-content ${msg.type}`}>
                <div className="message-header">
                  <span className="sender">
                    {msg.type === 'user' ? 'You ' : msg.type === 'assistant' ? 'RISE ' : 'System '}
                  </span>
                </div>
                <div className="text">{msg.text}</div>
                <span className="timestamp">{new Date().toLocaleTimeString()}</span>
              </div>
            </div>
          ))}
          {isTyping && (
            <div className="message assistant typing">
              <div className="message-content">
                <div className="message-header">
                  <span className="sender">RISE</span>
                </div>
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
        <form class="input-area" id="messageForm">
          <input type="text" id="messageInput" placeholder="Type your message here..." autofocus class="message-input">
          <button type="submit" id="sendButton">
            <svg class="send-icon" viewBox="0 0 24 24">
              <line x1="22" y1="2" x2="11" y2="13"></line>
              <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
          </button>
        </form>
        <div className="status-bar">
          <div className="status-indicator">
            <span className={`status-dot ${status === 'Ready' ? 'online' : status === 'Processing' ? 'busy' : 'offline'}`}></span>
            {status}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
''')
            
            # Create CSS for the chat interface with the same style for all message bubbles
            with open(os.path.join(electron_dir, 'src', 'App.css'), 'w') as f:
                f.write('''
:root {
  /* Theme colors */
  --bg-primary: #0a0a0f;
  --bg-secondary: #0d0d12;
  --text-primary: #e8e8e8;
  --text-secondary: #a0a0a0;
  --accent-primary: #76b900; /* NVIDIA Green */
  --accent-secondary: #8fd619; /* Lighter NVIDIA Green */
  --msg-bg: #0f0f14; /* Same background for all messages */
  --border-radius: 16px;
  --input-bg: #1a1b26;
  --button-bg: #76b900; /* NVIDIA Green */
  --button-hover: #8fd619; /* Lighter NVIDIA Green */
  --status-online: #76b900; /* NVIDIA Green */
  --status-busy: #ffb300; /* Amber */
  --status-offline: #ff3d00; /* Red */
  --shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
  --transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
  --border-color: rgba(118, 185, 0, 0.2); /* NVIDIA Green with opacity */
  --glow: 0 0 10px rgba(118, 185, 0, 0.4); /* NVIDIA Green glow */
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'SF Pro Display', 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  line-height: 1.6;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.App {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: linear-gradient(to bottom, var(--bg-secondary), var(--bg-primary));
}

.App-header {
  background-color: var(--bg-secondary);
  padding: 16px 24px;
  color: var(--text-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
  -webkit-app-region: drag;
  border-bottom: 1px solid var(--border-color);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
}

.drag-region {
  flex: 1;
}

.App-header h1 {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 600;
  letter-spacing: 0.5px;
  background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 20px rgba(118, 185, 0, 0.3);
}

.window-controls {
  display: flex;
  -webkit-app-region: no-drag;
}

.window-controls button {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 1.2rem;
  margin-left: 12px;
  cursor: pointer;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: var(--transition);
}

.window-controls button:hover {
  background-color: rgba(255, 255, 255, 0.1);
  transform: scale(1.1);
}

.window-controls .close:hover {
  background-color: var(--status-offline);
  color: var(--bg-primary);
}
                        
.chat-page {
  display: flex;
  flex-direction: row;
  gap: 1rem;
}
.settings-pane {
  flex: 1
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex: 2;
  padding: 24px;
  background-color: var(--bg-primary);
  overflow: hidden;
  position: relative;
}

.chat-container::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: radial-gradient(circle at top right, rgba(118, 185, 0, 0.05), transparent 70%);
  pointer-events: none;
}

.messages {
  flex: 1;
  overflow-y: auto;
  margin-bottom: 24px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  scrollbar-width: thin;
  scrollbar-color: var(--accent-primary) var(--bg-secondary);
  mask-image: linear-gradient(to bottom, transparent, black 10px, black 90%, transparent);
}

.messages::-webkit-scrollbar {
  width: 6px;
}

.messages::-webkit-scrollbar-track {
  background: var(--bg-secondary);
  border-radius: 10px;
}

.messages::-webkit-scrollbar-thumb {
  background-color: var(--accent-primary);
  border-radius: 10px;
  border: 2px solid var(--bg-secondary);
}

.message {
  display: flex;
  margin-bottom: 4px;
  animation: fadeIn 0.4s ease-out;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-content {
  padding: 16px 20px;
  border-radius: var(--border-radius);
  max-width: 80%;
  box-shadow: var(--shadow);
  transition: var(--transition);
  border: 1px solid var(--border-color);
  backdrop-filter: blur(10px);
  position: relative;
  background-color: var(--msg-bg); /* Same background for all messages */
  width: 100%; /* Full width for all messages */
  max-width: 100%; /* Full width for all messages */
  font-style: italic; /* Italic text for all messages */
  opacity: 0.9; /* Slightly transparent for all messages */
  border: 1px dashed var(--border-color); /* Dashed border for all messages */
}
                            
.assistant {
  text-align: left !important;                        
}

/* Default text alignment */
.message-content {
  text-align: left;
}

/* User messages alignment - right aligned */
.message.user .message-content {
  text-align: right;
  margin-left: auto;
}

/* System and assistant messages alignment - left aligned */
.message.system .message-content,
.message.assistant .message-content {
  text-align: left !important;
  margin-right: auto;
}

.message-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 0.85rem;
  border-bottom: 1px solid rgba(118, 185, 0, 0.2);
  padding-bottom: 6px;
}

.sender {
  font-weight: 600;
  letter-spacing: 0.5px;
}
                        
.timestamp-container {
  display: flex;
  justify-content: flex-end;
  margin-top: 5px;
}

.timestamp {
  color: rgba(255, 255, 255, 0.7);
  font-size: 0.75rem;
  opacity: 0.8;
  position: absolute;
  bottom: 1px;
  right: 10px;
  display: inline-block; /* Ensure it's displayed */
  /* Fix for disappearing timestamps */
  z-index: 1;
  transition: none; /* Prevent any transitions that might cause it to disappear */
}

.text {
  word-break: break-word;
  white-space: pre-wrap;
  line-height: 1.7;
  letter-spacing: 0.2px;
  margin-bottom: 15px; /* Add space for timestamp */
}

.typing-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background-color: var(--accent-primary);
  border-radius: 50%;
  display: inline-block;
  animation: bounce 1.5s infinite ease-in-out;
}

.typing-indicator span:nth-child(1) {
  animation-delay: 0s;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}

.input-area {
  display: flex;
  margin-bottom: 16px;
  background-color: var(--input-bg);
  border-radius: var(--border-radius);
  padding: 6px;
  box-shadow: var(--shadow);
  border: 1px solid var(--border-color);
  transition: var(--transition);
  position: relative;
  overflow: hidden;
}

.input-area:focus-within {
  border-color: var(--accent-primary);
  box-shadow: var(--glow);
}

.input-area::before {
  content: '';
  position: absolute;
  top: -50%;
  left: -50%;
  width: 200%;
  height: 200%;
  background: linear-gradient(
    to bottom right,
    rgba(118, 185, 0, 0.05),
    rgba(143, 214, 25, 0.05)
  );
  transform: rotate(45deg);
  z-index: -1;
}

.input-area input {
  flex: 1;
  padding: 14px 18px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 1rem;
  outline: none;
  font-family: inherit;
}

.input-area input::placeholder {
  color: var(--text-secondary);
  opacity: 0.7;
}

.input-area button {
  padding: 10px 18px;
  background-color: var(--button-bg);
  color: var(--bg-primary);
  border: none;
  border-radius: var(--border-radius);
  cursor: pointer;
  font-size: 1rem;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: var(--transition);
  margin-left: 8px;
  box-shadow: 0 2px 8px rgba(118, 185, 0, 0.4);
}

.input-area button:hover:not(:disabled) {
  background-color: var(--button-hover);
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 4px 12px rgba(143, 214, 25, 0.5);
}

.input-area button:active:not(:disabled) {
  transform: translateY(1px);
}

.input-area button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.input-area button svg {
  width: 20px;
  height: 20px;
  filter: drop-shadow(0 0 2px rgba(0, 0, 0, 0.3));
}
                        
textarea {
    height: 15rem;
    border-radius: 10px;
    padding: 10px;
    font-size: 1rem;
    font-family: inherit;
    outline: none;
    background-color: var(--input-bg);
    color: var(--text-primary);
}

.status-bar {
  padding: 10px 16px;
  background-color: var(--bg-secondary);
  border-radius: var(--border-radius);
  color: var(--text-secondary);
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow);
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  position: relative;
}

.status-dot.online {
  background-color: var(--status-online);
  box-shadow: 0 0 10px var(--status-online);
}

.status-dot.busy {
  background-color: var(--status-busy);
  box-shadow: 0 0 10px var(--status-busy);
}

.status-dot.offline {
  background-color: var(--status-offline);
  box-shadow: 0 0 10px var(--status-offline);
}

.status-dot::after {
  content: '';
  position: absolute;
  top: -5px;
  left: -5px;
  right: -5px;
  bottom: -5px;
  border-radius: 50%;
  background: transparent;
  border: 2px solid currentColor;
  opacity: 0.5;
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.5); opacity: 0.8; }
  70% { transform: scale(1.2); opacity: 0; }
  100% { transform: scale(0.5); opacity: 0; }
}

/* Responsive styles */
@media (max-width: 768px) {
  .message-content {
    max-width: 90%;
  }
  
  .App-header {
    padding: 12px 16px;
  }
  
  .chat-container {
    padding: 16px;
  }
  
  .input-area input {
    padding: 12px 14px;
  }
}

/* Force dark mode */
.App {
  background: linear-gradient(to bottom, #0d0d12, #0a0a0f);
}

.message-content {
  background-color: var(--msg-bg);
  color: var(--text-primary);
  box-shadow: 0 4px 12px rgba(15, 15, 20, 0.3);
}
''')
            
            print("Electron React app created successfully!")
            
        except FileNotFoundError:
            print("Error: npm or npx not found. Please install Node.js and npm.")
            print("Creating a simple HTML interface instead...")
            
            # Create a simple HTML interface as fallback
            os.makedirs(os.path.join(electron_dir, 'public'), exist_ok=True)
            with open(os.path.join(electron_dir, 'public', 'index.html'), 'w') as f:
                f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>RISE</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        :root {
          /* Theme colors */
          --bg-primary: #0a0a0f;
          --bg-secondary: #0d0d12;
          --text-primary: #e8e8e8;
          --text-secondary: #a0a0a0;
          --accent-primary: #76b900; /* NVIDIA Green */
          --accent-secondary: #8fd619; /* Lighter NVIDIA Green */
          --msg-bg: #0f0f14; /* Same background for all messages */
          --border-radius: 16px;
          --input-bg: #1a1b26;
          --button-bg: #76b900; /* NVIDIA Green */
          --button-hover: #8fd619; /* Lighter NVIDIA Green */
          --status-online: #76b900; /* NVIDIA Green */
          --status-busy: #ffb300; /* Amber */
          --status-offline: #ff3d00; /* Red */
          --shadow: 0 8px 16px rgba(0, 0, 0, 0.4);
          --transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
          --border-color: rgba(118, 185, 0, 0.2); /* NVIDIA Green with opacity */
          --glow: 0 0 10px rgba(118, 185, 0, 0.4); /* NVIDIA Green glow */
        }
        
        * {
          box-sizing: border-box;
          margin: 0;
          padding: 0;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            margin: 0;
            padding: 0;
            height: 100vh;
            display: flex;
            flex-direction: column;
            background: linear-gradient(to bottom, var(--bg-secondary), var(--bg-primary));
            color: var(--text-primary);
            line-height: 1.6;
            font-size: 16px;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        
        header {
            background-color: var(--bg-secondary);
            padding: 16px 24px;
            color: var(--text-primary);
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        }
        
        h1 {
            margin: 0;
            font-size: 1.4rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-shadow: 0 0 20px rgba(118, 185, 0, 0.3);
        }
                        
        textarea {
          height: 15rem;
          border-radius: 10px;
          border: none;
          padding: 10px;
          font-size: 1rem;
          font-family: inherit;
          outline: none;
          background-color: var(--input-bg);
          color: var(--text-primary);
        }
                        
        .chat-page {
            display: flex;
            flex-direction: row;
            gap: 1rem;
            height: 100%
        }
        .settings-pane {
            flex: 1;
            border-left: 1px solid var(--border-color);
            display: flex;
            flex-direction: column; 
            gap: 1rem;
            padding: 2rem 1rem;
        }
        .settings-container {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        
        .chat-container {
            display: flex;
            flex-direction: column;
            flex: 2;
            padding: 24px;
            background-color: var(--bg-primary);
            overflow: hidden;
            position: relative;
        }
        
        .chat-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: radial-gradient(circle at top right, rgba(118, 185, 0, 0.03), transparent 70%);
            pointer-events: none;
        }
        
        .messages {
            flex: 1;
            overflow-y: auto;
            margin-bottom: 24px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            scrollbar-width: thin;
            scrollbar-color: var(--accent-primary) var (--bg-secondary);
            mask-image: linear-gradient(to bottom, transparent, black 10px, black 90%, transparent);
        }
        
        .messages::-webkit-scrollbar {
            width: 6px;
        }
        
        .messages::-webkit-scrollbar-track {
            background: var(--bg-secondary);
            border-radius: 10px;
        }
        
        .messages::-webkit-scrollbar-thumb {
            background-color: var(--accent-primary);
            border-radius: 10px;
            border: 2px solid var(--bg-secondary);
        }
        
        .message {
            display: flex;
            margin-bottom: 4px;
            animation: fadeIn 0.4s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message-content {
            padding: 16px 20px;
            border-radius: var(--border-radius);
            max-width: 80%;
            box-shadow: var(--shadow);
            transition: var(--transition);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
            animation: fadeIn 0.3s ease;
            position: relative; /* Added for timestamp positioning */
            background-color: var(--msg-bg); /* Same background for all messages */
            width: 100%; /* Full width for all messages */
            max-width: 100%; /* Full width for all messages */
            text-align: right; /* right align text for all messages */
            font-style: italic; /* Italic text for all messages */
            opacity: 0.9; /* Slightly transparent for all messages */
            border: 1px dashed var(--border-color); /* Dashed border for all messages */
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 6px;
            font-size: 0.8rem;
        }
        
        .sender {
            font-weight: 600;
            color: var(--accent-primary);
        }
        
        .timestamp-container {
          display: flex;
          justify-content: flex-end;
          margin-top: 5px;
        }
        
        .timestamp {
            color: var(--text-secondary);
            font-size: 0.7rem;
            position: absolute;
            bottom: 1px;
            right: 10px;
            margin-top: 10px;
        }
        
        .text {
            word-break: break-word;
            white-space: pre-wrap;
        }
        
        .typing-indicator {
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 4px 0;
        }
        
        .typing-indicator span {
            width: 8px;
            height: 8px;
            background-color: var (--accent-primary);
            border-radius: 50%;
            display: inline-block;
            animation: bounce 1.5s infinite ease-in-out;
        }
        
        .typing-indicator span:nth-child(1) {
            animation-delay: 0s;
        }
        
        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes bounce {
            0%, 60%, 100% { transform: translateY(0); }
            30% { transform: translateY(-6px); }
        }
        
        .input-area {
            display: flex;
            margin-bottom: 10px;
            background-color: var(--input-bg);
            border-radius: var(--border-radius);
            padding: 4px;
            box-shadow: var(--shadow);
        }
        
        input {
            flex: 1;
            padding: 12px 16px;
            border: none;
            background: transparent;
            color: var(--text-primary);
            font-size: 1rem;
            outline: none;
        }
        
        input::placeholder {
            color: var(--text-secondary);
        }
                        
        .adapter-input {
            background-color: var(--input-bg);
            color: var(--text-primary);
            border: none;
            padding: 12px 16px;
            border-radius: var(--border-radius);
            flex: 1;
       }
                        
        .message-input {
            flex: 2;
        }
        
        button {
            padding: 8px 16px;
            background-color: var(--button-bg);
            color: var(--bg-primary);
            border: none;
            border-radius: var(--border-radius);
            cursor: pointer;
            font-size: 1rem;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        }
        
        button:hover:not(:disabled) {
            background-color: var(--button-hover);
            transform: translateY(-2px);
        }
        
        button:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        
        .status-bar {
            padding: 8px 12px;
            background-color: var(--bg-secondary);
            border-radius: var(--border-radius);
            color: var(--text-secondary);
            font-size: 0.8rem;
            display: flex;
            align-items: center;
        }
        
        .status-indicator {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            display: inline-block;
        }
        
        .status-dot.online {
            background-color: var(--status-online);
            box-shadow: 0 0 8px var(--status-online);
        }
        
        .status-dot.busy {
            background-color: var(--status-busy);
            box-shadow: 0 0 8px var(--status-busy);
        }
        
        .status-dot.offline {
            background-color: var(--status-offline);
            box-shadow: 0 0 8px var(--status-offline);
        }
        
        .send-icon {
            width: 20px;
            height: 20px;
            stroke: currentColor;
            stroke-width: 2;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .assistant {
          text-align: left !important;                        
        }
    </style>
</head>
<body>
    <header>
        <h1>RISE</h1>
    </header>
    <div class="chat-page">
      <div class="chat-container">
          <div class="messages" id="messages">
              <div class="message system">
                  <div class="message-content">
                      <div class="message-header">
                          <span class="sender">System</span>
                      </div>
                      <div class="text">Welcome to RISE. How can I assist you today?</div>
                      <span class="timestamp"></span>
                  </div>
              </div>
          </div>
          <form class="input-area" id="messageForm">
              <input type="text" id="messageInput" placeholder="Type your message here..." autofocus class="message-input">
              <button type="submit" id="sendButton">
                  <svg class="send-icon" viewBox="0 0 24 24">
                      <line x1="22" y1="2" x2="11" y2="13"></line>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
              </button>
          </form>
          <div class="status-bar">
              <div class="status-indicator">
                  <span class="status-dot online" id="statusDot"></span>
                  <span id="status">Ready</span>
              </div>
          </div>
      </div>
      <div class="settings-pane">
          <h3>Settings</h3>
          <hr/>
          <div class="settings-container">
            <h5>Adapter</h5>
            <input type="text" id="adapterInput" placeholder="Adapter (optional)" class="adapter-input" >
           </div>
           <div class="settings-container">
            <h5>System Prompt</h5>
            <textarea id="systemPromptInput" placeholder="System Prompt (optional)" class="system-prompt-input"></textarea>
           </div>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const messageForm = document.getElementById('messageForm');
            const messageInput = document.getElementById('messageInput');
            const adapterInput = document.getElementById('adapterInput');
            const systemPromptInput = document.getElementById('systemPromptInput');
            const messagesContainer = document.getElementById('messages');
            const statusText = document.getElementById('status');
            const statusDot = document.getElementById('statusDot');
            const statusBar = document.getElementById('status');
            
            messageForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const message = messageInput.value.trim();
                const adapter = adapterInput.value.trim().toLowerCase();
                const system_prompt = systemPromptInput.value.trim().toLowerCase();
                if (!message) return;
                
                // Add user message
                addMessage('user', message);
                messageInput.value = '';
                statusBar.textContent = 'RISE is thinking...';
                
                try {
                    const response = await fetch('http://localhost:5000/api/send-message', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ message, adapter, system_prompt })
                    });
                    
                    const data = await response.json();
                    if (response.ok) {
                        addMessage('assistant', data.response.completed_response, data.response.completed_chart);
                    } else {
                        addMessage('system', `Error: ${data.error}`);
                    }
                    statusBar.textContent = 'Ready';
                } catch (error) {
                    console.error('Error:', error);
                    addMessage('system', `Error communicating with RISE: ${error.message}`);
                    statusBar.textContent = 'Error: Communication failed';
                }
            });
            function getScalesForData(chunkData) {
                let axes = {};

                if (chunkData?.length > 0) {
                    chunkData.forEach((chartData, index) => {
                        const xAxisName = `x${(index !== 0) ? index : ''}`;
                        const yAxisName = `y${(index !== 0) ? index : ''}`;
                        if (index === 0) {
                            axes = {
                                ...axes,
                                x: {
                                    title: {
                                        display: true,
                                        text: (chartData.xUnit !== '%') ? `${chartData.xUnit}` : ''
                                    },
                                    callback: function (value) {
                                        if (chartData.xUnit === '%') {
                                            return value + '%';
                                        } else {
                                            return value
                                        }
                                    }
                                },
                                y: {
                                    position: 'left',
                                    title: {
                                        display: true,
                                        text: (chartData.yUnit !== '%') ? `${chartData.yUnit}` : ''
                                    },
                                    ticks: {
                                        callback: function (value) {
                                            if (chartData.yUnit === '%') {
                                                return value + '%';
                                            } else {
                                                return value
                                            }
                                        }
                                    }
                                }
                            }

                            if ((axes.y !== undefined) && (chartData.yUpperLimit !== undefined)) {
                                axes.y.max = chartData.yUpperLimit
                            }
                            if ((axes.y !== undefined) && (chartData.yLowerLimit !== undefined)) {
                                axes.y.min = chartData.yLowerLimit
                            }
                        } else if (index > 0) {
                            if (chartData.xUnit !== chunkData[0].xUnit) {
                                axes = {
                                    ...axes,
                                    [xAxisName]: {
                                        position: 'top',
                                        title: {
                                            display: true,
                                            text: (chartData.xUnit !== '%') ? `${chartData.xUnit}` : ''
                                        },
                                        callback: function (value) {
                                            if (chartData.xUnit === '%') {
                                                return value + '%';
                                            } else {
                                                return value
                                            }
                                        },
                                        grid: {
                                            drawOnChartArea: false, // only want the grid lines for one axis to show up
                                        }
                                    }
                                }
                            } else if (chartData.yUnit !== chunkData[0].yUnit) {
                                axes = {
                                    ...axes,
                                    [yAxisName]: {
                                        position: 'right',
                                        title: {
                                            display: true,
                                            text: (chartData.yUnit !== '%') ? `${chartData.yUnit}` : ''
                                        },
                                        ticks: {
                                            callback: function (value) {
                                                if (chartData.yUnit === '%') {
                                                    return value + '%';
                                                } else {
                                                    return value
                                                }
                                            }
                                        },
                                        grid: {
                                            drawOnChartArea: false, // only want the grid lines for one axis to show up
                                        }
                                    }
                                }

                                if ((axes[yAxisName] !== undefined) && (chartData.yUpperLimit !== undefined)) {
                                    axes[yAxisName].max = chartData.yUpperLimit
                                }
                                if ((axes[yAxisName] !== undefined) && (chartData.yLowerLimit !== undefined)) {
                                    axes[yAxisName].min = chartData.yLowerLimit
                                }
                            }
                        }
                    })
                }
                return axes
            }
                    
            function addMessage(type, text, chart = '') {
                let chartId = '';
                // Create the outer message container
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${type}`;
                
                // Create the inner container with bounding box styling
                const contentDiv = document.createElement('div');
                contentDiv.className = `message-content ${type}`;
                
                // Create and append the sender element
                const sender = document.createElement('span');
                sender.className = 'sender';
                sender.textContent = type === 'user' ? 'You: ' : type === 'assistant' ? 'RISE: ' : 'System: ';
                contentDiv.appendChild(sender);
                
                // Create and append the text element
                const textSpan = document.createElement('span');
                textSpan.className = 'text';
                textSpan.textContent = text;
                contentDiv.appendChild(textSpan);
                        
                // Create and append the chart element
                if(chart !== '') {
                    const chartDiv = document.createElement('div');
                    const chartCanvas = document.createElement('canvas');
                    chartId = `chart-${Math.floor(Math.random() * 1000000)}`;
                    chartCanvas.setAttribute('id', chartId);
                    chartDiv.appendChild(chartCanvas);
                    contentDiv.appendChild(chartDiv);
                }
                
                // Create and append the timestamp element
                const timestamp = document.createElement('span');
                timestamp.className = 'timestamp';
                timestamp.textContent = new Date().toLocaleTimeString();
                contentDiv.appendChild(timestamp);
                
                // Append the content container to the main message div
                messageDiv.appendChild(contentDiv);
                
                // Append the message to the messages container
                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;                        
                if(chart !== '') {
                  const chartData = JSON.parse(chart);
                  const ctx = document.getElementById(chartId);
                  const labels = chartData[0].data.map((item) => item.x)

                  const chartObj = {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: chartData.map((chartInfo, index) => {
                            return {
                                label: chartInfo.chartTitle,
                                data: chartInfo.data.map((item) => item.y),
                                xAxisID: (index !== 0 && chartInfo.xUnit !== chartData[0].xUnit) ? `x${index}` : 'x',
                                yAxisID: (index !== 0 && chartInfo.yUnit !== chartData[0].yUnit) ? `y${index}` : 'y',
                            }
                        })
                    },
                    options: {
                          borderWidth: 1,
                          pointRadius: 1,
                          responsive: true,
                          maintainAspectRatio: true,
                          scales: getScalesForData(chartData),
                          plugins: {
                              tooltip: {
                                  callbacks: {
                                      label: function (context) {
                                          let label = context.dataset.label || '';

                                          if (label) {
                                              label += ': ';
                                          }
                                          if (context.parsed.y !== null) {
                                              label += context.parsed.y;
                                              label += ` ${chartData[context.datasetIndex].yUnit}`;
                                          }
                                          return label;
                                      }
                                  }
                              }
                          }
                      }
                  };
                  new Chart(ctx, chartObj);
                }
            }
        });
    </script>
</body>
</html>
''')
            print("Simple HTML interface created successfully!")
    
    # Start the web interface
    print("Starting web interface...")
    if sys.platform == 'darwin':  # macOS
        subprocess.Popen(['open', os.path.join(electron_dir, 'public', 'index.html')])
    elif sys.platform == 'win32':  # Windows
        os.startfile(os.path.join(electron_dir, 'public', 'index.html'))
    else:  # Linux
        try:
            subprocess.Popen(['xdg-open', os.path.join(electron_dir, 'public', 'index.html')])
        except:
            print(f"Please open {os.path.join(electron_dir, 'public', 'index.html')} in your browser")

def main():
    # Start the Electron app in a separate thread
    threading.Thread(target=start_electron_app, daemon=True).start()
    
    # Start the Flask server
    app.run(host='127.0.0.1', port=5000)

if __name__ == "__main__":
    main()
