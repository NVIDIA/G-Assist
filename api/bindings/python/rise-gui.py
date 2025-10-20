import os
import sys
import json
import subprocess
import threading
import shutil
import time
import tempfile
import webbrowser
import logging
import warnings
from flask import Flask, request, jsonify, Response, stream_with_context
from flask_cors import CORS
from waitress import serve
from rise import rise

# Suppress Python warnings for JavaScript code in HTML strings
warnings.filterwarnings('ignore', category=SyntaxWarning)

# Suppress Flask development server warnings
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Create a Flask server to handle API requests from the Electron app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize G-Assist client
try:
    rise.register_rise_client()
    print("G-Assist client initialized successfully")
except Exception as e:
    print(f"Error initializing G-Assist client: {str(e)}")
    sys.exit(1)

@app.route('/')
def index():
    """Serve the main HTML page"""
    return get_html_content()

def get_html_content():
    """Generate and return the HTML content from the start_electron_app function"""
    # Extract the HTML from the start_electron_app function's template
    import inspect
    import re
    source = inspect.getsource(start_electron_app)
    # Extract the HTML between f.write(''' and ''')
    match = re.search(r"with open\(os\.path\.join\(electron_dir, 'public', 'index\.html'\), 'w'\) as f:\s+f\.write\('''(.+?)'''\)", source, re.DOTALL)
    if match:
        html_content = match.group(1)
        return html_content
    else:
        # Fallback: return error message
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>G-Assist - Error</title>
</head>
<body>
    <h1>Error: Could not load interface</h1>
    <p>Please restart the server.</p>
</body>
</html>
'''

@app.route('/api/send-message', methods=['POST'])
def send_message():
    """API endpoint to send messages to G-Assist (legacy non-streaming)"""
    data = request.json
    message = data.get('message', '')
    assistant_identifier = data.get('assistant_identifier', '')
    custom_system_prompt = data.get('custom_system_prompt', '')
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    try:
        # Send message to RISE with client_config
        response = rise.send_rise_command(message, assistant_identifier, custom_system_prompt)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/check-microphones', methods=['GET'])
def check_microphones():
    """API endpoint to check available microphones"""
    try:
        # This will be checked on the client side using JavaScript navigator.mediaDevices.enumerateDevices()
        # Just return a success response
        return jsonify({'status': 'success', 'message': 'Use client-side enumeration'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe_audio():
    """API endpoint for audio transcription using Faster-Whisper"""
    try:
        # Get audio data from request
        if 'audio' not in request.files:
            return jsonify({'error': 'No audio file provided'}), 400
        
        audio_file = request.files['audio']
        
        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
            audio_file.save(temp_audio.name)
            temp_path = temp_audio.name
        
        try:
            # Lazy load Whisper model (loads on first use)
            global whisper_model
            if 'whisper_model' not in globals():
                from faster_whisper import WhisperModel
                print("Loading Faster-Whisper model (tiny.en)...")
                whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
                print("Whisper model loaded successfully")
            
            # Transcribe
            segments, info = whisper_model.transcribe(temp_path, language="en", beam_size=1)
            text = " ".join([seg.text.strip() for seg in segments])
            
            # Clean up temp file
            import os
            os.unlink(temp_path)
            
            return jsonify({'text': text, 'language': info.language})
            
        except Exception as e:
            # Clean up temp file on error
            import os
            try:
                os.unlink(temp_path)
            except:
                pass
            raise e
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/send-message-stream', methods=['POST'])
def send_message_stream():
    """API endpoint for streaming messages from G-Assist"""
    data = request.json
    message = data.get('message', '')
    assistant_identifier = data.get('assistant_identifier', '')
    custom_system_prompt = data.get('custom_system_prompt', '')
    thinking_enabled = data.get('thinking_enabled', False)
    
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    def generate():
        """Generator function for Server-Sent Events"""
        try:
            # Reset the global response before starting
            rise.response = ''
            rise.response_done = False
            
            # Track previous response length to send only new chunks
            prev_length = 0
            
            # Start the RISE command in a separate thread
            import threading
            result = {'response': None, 'error': None}
            
            def run_command():
                try:
                    # send_rise_command returns a dict with 'completed_response' and 'completed_chart'
                    result['response'] = rise.send_rise_command(message, assistant_identifier, custom_system_prompt, thinking_enabled)
                except Exception as e:
                    result['error'] = str(e)
            
            thread = threading.Thread(target=run_command)
            thread.start()
            
            # Poll for streaming updates
            is_likely_tool_call = False
            while not rise.response_done:
                current_response = rise.response
                if len(current_response) > prev_length:
                    # On first chunk, determine if this looks like JSON/tool call
                    if prev_length == 0:
                        stripped = current_response.strip()
                        if stripped.startswith('{') or stripped.startswith('['):
                            is_likely_tool_call = True
                            print(f"[SSE] Detected potential JSON/tool call, buffering...", flush=True)
                    
                    # If it's not a tool call, stream chunks normally
                    if not is_likely_tool_call:
                        chunk = current_response[prev_length:]
                        print(f"[SSE] Sending text chunk: '{chunk}'", flush=True)
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                        prev_length = len(current_response)
                    # If it is a tool call, we buffer until complete (do nothing here)
                    
                time.sleep(0.01)  # Poll every 10ms for faster updates
            
            # Wait for thread to complete
            thread.join(timeout=1.0)
            
            # Send completion signal
            if result['error']:
                yield f"data: {json.dumps({'error': result['error']})}\n\n"
            else:
                # Get the response from the result dict
                response_dict = result.get('response', {})
                print(f"[SSE DEBUG] result object: {result}", flush=True)
                print(f"[SSE DEBUG] response_dict: {response_dict}", flush=True)
                print(f"[SSE DEBUG] response_dict type: {type(response_dict)}", flush=True)
                
                if response_dict:
                    final_response = response_dict.get('completed_response', '')
                    final_chart = response_dict.get('completed_chart', '')
                    
                    print(f"[SSE] Final response: '{final_response}'", flush=True)
                    print(f"[SSE] Final response length: {len(final_response)}", flush=True)
                    print(f"[SSE] Final response type: {type(final_response)}", flush=True)
                    print(f"[SSE] Final chart: '{final_chart}'", flush=True)
                    print(f"[SSE] is_likely_tool_call: {is_likely_tool_call}, prev_length: {prev_length}", flush=True)
                    
                    # Helper function to check if string is valid JSON
                    def is_valid_json(text):
                        try:
                            json.loads(text)
                            return True
                        except:
                            return False
                    
                    # Check if final_response is valid JSON (tool call)
                    is_json = is_valid_json(final_response.strip()) if final_response else False
                    print(f"[SSE] is_valid_json: {is_json}", flush=True)
                    
                    # If the final response is valid JSON, always send as tool_call
                    if is_json and len(final_response) > 0:
                        print(f"[SSE] Sending as tool_call (valid JSON detected)", flush=True)
                        yield f"data: {json.dumps({'tool_call': final_response})}\n\n"
                    # If we buffered a tool call during streaming
                    elif is_likely_tool_call and len(final_response) > 0:
                        print(f"[SSE] Sending buffered tool call", flush=True)
                        yield f"data: {json.dumps({'tool_call': final_response})}\n\n"
                    # If there's remaining text content that wasn't sent during streaming
                    elif len(final_response) > prev_length:
                        remaining = final_response[prev_length:]
                        print(f"[SSE] Sending remaining text: '{remaining}'", flush=True)
                        yield f"data: {json.dumps({'chunk': remaining})}\n\n"
                    # If nothing was sent during streaming and it's not JSON
                    elif prev_length == 0 and len(final_response) > 0:
                        print(f"[SSE] Response came all at once (non-JSON text)", flush=True)
                        yield f"data: {json.dumps({'chunk': final_response})}\n\n"
                    
                    # Send chart data if available
                    if final_chart:
                        print(f"[SSE] Sending chart data", flush=True)
                        yield f"data: {json.dumps({'chart': final_chart})}\n\n"
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    response = Response(stream_with_context(generate()), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response

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
      { type: 'system', text: 'Welcome to G-Assist. How can I assist you today?' }
    ]);
    
    // Focus the input field on load
    inputRef.current?.focus();
  }, []);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { type: 'user', text: input };
    const userInput = input.trim();
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsTyping(true);

    try {
      // Use fetch API to initiate streaming request
      const response = await fetch('http://localhost:5000/api/send-message-stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: userInput,
          assistant_identifier: '',
          custom_system_prompt: ''
        })
      });

      if (!response.ok) {
        throw new Error('Network response was not ok');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = '';
      let messageAdded = false;

      // Read the stream
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));
              
              if (data.chunk) {
                // Hide typing indicator on first chunk
                if (!messageAdded) {
                  setIsTyping(false);
                  messageAdded = true;
                }
                
                // Append chunk to assistant text
                assistantText += data.chunk;
                
                // Update or create assistant message
                setMessages(prev => {
                  const newMessages = [...prev];
                  // Find the last assistant message or create new one
                  const lastIndex = newMessages.length - 1;
                  if (lastIndex >= 0 && newMessages[lastIndex].type === 'assistant' && messageAdded) {
                    // Update existing assistant message
                    newMessages[lastIndex] = { type: 'assistant', text: assistantText };
                  } else {
                    // Create new assistant message
                    newMessages.push({ type: 'assistant', text: assistantText });
                  }
                  return newMessages;
                });
              } else if (data.done) {
                setStatus('Ready');
                setIsTyping(false);
              } else if (data.error) {
                throw new Error(data.error);
              }
            } catch (parseError) {
              console.error('Error parsing SSE data:', parseError);
            }
          }
        }
      }
      
      setStatus('Ready');
    } catch (error) {
      console.error('Error sending message:', error);
      setIsTyping(false);
      setMessages(prev => [...prev, { 
        type: 'system', 
        text: `Error communicating with G-Assist: ${error.message}` 
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
          <h1>G-Assist</h1>
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
                    {msg.type === 'user' ? 'You ' : msg.type === 'assistant' ? 'G-Assist ' : 'System '}
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
                  <span className="sender">G-Assist</span>
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
        
        html, body {
            overflow: hidden;
            width: 100%;
            height: 100%;
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
        
        /* Hide scrollbars on body/html only */
        body::-webkit-scrollbar,
        html::-webkit-scrollbar {
            display: none;
        }
        
        html {
            scrollbar-width: none;
            -ms-overflow-style: none;
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
            flex: 1;
            overflow: hidden;
            min-height: 0;
            position: relative;
        }
        
        .settings-pane {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            width: 85%;
            max-width: 400px;
            background-color: var(--bg-secondary);
            border-left: 1px solid var(--border-color);
            display: flex;
            flex-direction: column; 
            gap: 1rem;
            padding: 2rem 1rem;
            overflow-y: auto;
            z-index: 1000;
            box-shadow: -4px 0 16px rgba(0, 0, 0, 0.5);
            transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
        }
        
        .settings-pane.hidden {
            transform: translateX(100%);
        }
        
        /* Settings backdrop overlay */
        .settings-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 999;
            opacity: 1;
            transition: opacity 0.3s ease;
        }
        
        .settings-backdrop.hidden {
            opacity: 0;
            pointer-events: none;
        }
        
        .settings-container {
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }
        
        .chat-container {
            display: flex;
            flex-direction: column;
            flex: 1;
            width: 100%;
            min-height: 0;
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
            min-height: 0;
            overflow-y: auto;
            overflow-x: hidden;
            margin-bottom: 24px;
            padding: 12px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            scrollbar-width: thin;
            scrollbar-color: var(--accent-primary) var(--bg-secondary);
            scroll-behavior: smooth;
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
            background-color: var(--msg-bg);
            width: 100%;
            max-width: 100%;
            text-align: left; /* Default left align */
        }
        
        /* User messages - right aligned */
        .message.user .message-content {
            text-align: right;
        }
        
        /* Assistant and system messages - left aligned */
        .message.assistant .message-content,
        .message.system .message-content {
            text-align: left;
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
        
        .code-block {
            background-color: #1e1e1e;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            color: #d4d4d4;
            text-align: left !important; /* Always left-align code blocks */
            font-style: normal; /* Remove italic from code */
        }
        
        .code-block pre {
            margin: 0;
            white-space: pre;
            text-align: left;
        }
        
        /* JSON Syntax Highlighting */
        .json-key {
            color: #9cdcfe; /* Light blue for keys */
            font-weight: 500;
        }
        
        .json-string {
            color: #ce9178; /* Orange-brown for string values */
        }
        
        .json-number {
            color: #b5cea8; /* Light green for numbers */
        }
        
        .json-boolean {
            color: #569cd6; /* Blue for booleans */
        }
        
        .json-null {
            color: #569cd6; /* Blue for null */
        }
        
        /* Thinking Block Styling */
        .thinking-block {
            background-color: #1a1a1a;
            border: 1px solid #2a2a2a;
            border-left: 3px solid #666;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
            overflow-x: auto;
            font-family: 'Georgia', 'Times New Roman', serif;
            font-size: 0.9rem;
            line-height: 1.6;
            color: #888;
            font-style: italic;
            text-align: left !important;
        }
        
        .thinking-block::before {
            content: "💭 Thinking...";
            display: block;
            font-weight: 600;
            font-style: normal;
            margin-bottom: 8px;
            color: #999;
            font-size: 0.8rem;
            font-family: Arial, sans-serif;
        }
        
        .thinking-block pre {
            margin: 0;
            white-space: pre-wrap;
            word-wrap: break-word;
            text-align: left;
            font-family: inherit;
            font-style: inherit;
            color: inherit;
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
            30% { transform: translateY(-6px); }
        }
        
        .input-area {
            display: flex;
            flex-shrink: 0;
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
        
        input:disabled, textarea:disabled {
            opacity: 0.6;
            cursor: not-allowed;
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
        
        button[type="submit"] {
            margin-right: 4px;
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
        
        /* Settings button */
        .settings-button {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: var(--transition);
            margin-left: auto;
        }
        
        .settings-button:hover {
            background-color: rgba(255, 255, 255, 0.1);
            color: var(--accent-primary);
            transform: rotate(90deg);
        }
        
        .settings-button svg {
            width: 24px;
            height: 24px;
        }
        
        /* Settings panel toggle */
        .settings-pane {
            transition: transform 0.3s ease, opacity 0.3s ease;
            transform: translateX(0);
            opacity: 1;
        }
        
        .settings-pane.hidden {
            transform: translateX(100%);
            opacity: 0;
            pointer-events: none;
            position: absolute;
            right: -100%;
        }
        
        /* Thinking toggle button */
        .thinking-toggle {
            background: none;
            border: 2px solid var(--text-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            padding: 10px 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            transition: var(--transition);
            margin-left: 4px;
            margin-right: 8px;
        }
        
        .thinking-toggle:hover {
            border-color: var(--accent-primary);
            color: var(--accent-primary);
            transform: translateY(-1px);
        }
        
        .thinking-toggle.active {
            background-color: var(--accent-primary);
            border-color: var(--accent-primary);
            color: #0a0a0f;
        }
        
        .thinking-toggle svg {
            width: 18px;
            height: 18px;
        }
        
        /* Voice button */
        .voice-button {
            background: none;
            border: 2px solid var(--text-secondary);
            color: var(--text-secondary);
            cursor: pointer;
            padding: 10px 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 8px;
            transition: var(--transition);
            margin-right: 8px;
        }
        
        .voice-button:hover {
            border-color: var(--accent-primary);
            color: var(--accent-primary);
            transform: translateY(-1px);
        }
        
        .voice-button.recording {
            background-color: #ff3d00;
            border-color: #ff3d00;
            color: white;
            animation: pulse-recording 1.5s ease-in-out infinite;
        }
        
        @keyframes pulse-recording {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .voice-button svg {
            width: 18px;
            height: 18px;
        }
        
        .voice-button:disabled {
            opacity: 0.4;
            cursor: not-allowed;
            border-color: #555;
            color: #555;
        }
        
        .voice-button:disabled:hover {
            transform: none;
            border-color: #555;
            color: #555;
        }
        
        /* Mic status in settings */
        .mic-status {
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 8px;
            font-style: italic;
        }
        
        .mic-status.error {
            color: #ff4d4d;
        }
        
        .mic-status.success {
            color: var(--accent-primary);
        }
        
        /* Close button */
        .close-button {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: var(--transition);
            margin-left: 8px;
        }
        
        .close-button:hover {
            background-color: rgba(255, 77, 77, 0.2);
            color: #ff4d4d;
        }
        
        .close-button svg {
            width: 20px;
            height: 20px;
        }
        
        /* Minimize button */
        .minimize-button {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: var(--transition);
        }
        
        .minimize-button:hover {
            background-color: rgba(255, 193, 7, 0.2);
            color: #ffc107;
        }
        
        .minimize-button svg {
            width: 20px;
            height: 20px;
        }
        
        /* Header buttons container */
        .header-buttons {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        /* Hamburger menu button */
        .hamburger-button {
            background: none;
            border: none;
            color: var(--text-secondary);
            cursor: pointer;
            padding: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            transition: var(--transition);
            margin-right: 12px;
        }
        
        .hamburger-button:hover {
            background-color: rgba(118, 185, 0, 0.2);
            color: var(--accent-primary);
        }
        
        .hamburger-button svg {
            width: 24px;
            height: 24px;
        }
        
        /* Dropdown menu */
        .dropdown-menu {
            position: absolute;
            top: 60px;
            left: 10px;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
            min-width: 200px;
            z-index: 1000;
            opacity: 0;
            transform: translateY(-10px);
            pointer-events: none;
            transition: opacity 0.2s ease, transform 0.2s ease;
        }
        
        .dropdown-menu.show {
            opacity: 1;
            transform: translateY(0);
            pointer-events: all;
        }
        
        .dropdown-item {
            display: flex;
            align-items: center;
            gap: 12px;
            width: 100%;
            padding: 12px 16px;
            background: none;
            border: none;
            color: var(--text-primary);
            cursor: pointer;
            font-size: 14px;
            transition: var(--transition);
            text-align: left;
        }
        
        .dropdown-item:first-child {
            border-radius: 8px 8px 0 0;
        }
        
        .dropdown-item:last-child {
            border-radius: 0 0 8px 8px;
        }
        
        .dropdown-item:hover {
            background-color: rgba(118, 185, 0, 0.1);
            color: var(--accent-primary);
        }
        
        .dropdown-item svg {
            width: 18px;
            height: 18px;
            flex-shrink: 0;
        }
        
        .dropdown-item span {
            flex: 1;
        }
        
        /* Dropdown divider */
        .dropdown-divider {
            height: 1px;
            background-color: var(--border-color);
            margin: 8px 0;
        }
        
        /* Dropdown version info */
        .dropdown-version {
            padding: 12px 16px;
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            font-style: italic;
            user-select: none;
        }
        
        .dropdown-version span {
            opacity: 0.7;
        }
        
        /* Debug console */
        .debug-console {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            max-height: 200px;
            background: rgba(10, 10, 15, 0.95);
            border-top: 1px solid var(--border-color);
            color: #00ff00;
            font-family: 'Courier New', monospace;
            font-size: 11px;
            overflow-y: auto;
            z-index: 9999;
            padding: 8px;
            display: none;
        }
        
        .debug-console.show {
            display: block;
        }
        
        .debug-console-line {
            margin: 2px 0;
            white-space: pre-wrap;
        }
        
        .debug-info {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--border-color);
            border-radius: 4px;
            padding: 4px 8px;
            font-size: 10px;
            color: var(--text-secondary);
            z-index: 9998;
            opacity: 0.5;
            cursor: pointer;
        }
        
        .debug-info:hover {
            opacity: 1;
        }
    </style>
</head>
<body>
    <header>
        <button class="hamburger-button" id="hamburgerButton" title="Menu">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="3" y1="12" x2="21" y2="12"></line>
                <line x1="3" y1="6" x2="21" y2="6"></line>
                <line x1="3" y1="18" x2="21" y2="18"></line>
            </svg>
        </button>
        <h1>G-Assist</h1>
        <div class="header-buttons">
            <button class="minimize-button" id="minimizeButton" title="Minimize">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
            </button>
            <button class="close-button" id="closeButton" title="Close (or press Ctrl+Q)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </button>
        </div>
        <div class="dropdown-menu" id="dropdownMenu">
            <button class="dropdown-item" id="settingsMenuItem">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="3"></circle>
                    <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                </svg>
                <span>Settings</span>
            </button>
            <button class="dropdown-item" id="exportMenuItem">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                <span>Export Chat</span>
            </button>
            <div class="dropdown-divider"></div>
            <div class="dropdown-version">
                <span>Version 0.0.2</span>
            </div>
        </div>
    </header>
    <div class="debug-console" id="debugConsole"></div>
    <div class="chat-page">
      <div class="chat-container">
          <div class="messages" id="messages">
              <div class="message system">
                  <div class="message-content">
                      <div class="message-header">
                          <span class="sender">System</span>
                      </div>
                      <div class="text">Welcome to G-Assist. How can I assist you today?</div>
                      <span class="timestamp"></span>
                  </div>
              </div>
          </div>
          <form class="input-area" id="messageForm">
              <button type="button" class="thinking-toggle" id="thinkingToggle" title="Toggle thinking mode">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M9.5 2c-1.82 0-3.53.5-5 1.35C2.99 4.07 2 5.8 2 7.75c0 2.07 1.13 3.87 2.81 4.86.06.38.16.75.29 1.1.36.97.96 1.84 1.73 2.53 0 .91.46 1.76 1.24 2.26.78.5 1.76.5 2.54 0 .78-.5 1.24-1.35 1.24-2.26.77-.69 1.37-1.56 1.73-2.53.13-.35.23-.72.29-1.1C15.87 11.62 17 9.82 17 7.75c0-1.95-.99-3.68-2.5-4.4C13.03 2.5 11.32 2 9.5 2zm0 1.5c1.48 0 2.87.41 4.06 1.13 1.06.64 1.94 1.66 1.94 3.12 0 1.58-.95 2.95-2.31 3.55l-.26.11-.04.28c-.03.24-.1.47-.19.69-.27.68-.73 1.29-1.32 1.75l-.35.27v.85c0 .36-.18.7-.5.9-.32.2-.73.2-1.05 0-.32-.2-.5-.54-.5-.9v-.85l-.35-.27c-.59-.46-1.05-1.07-1.32-1.75-.09-.22-.16-.45-.19-.69l-.04-.28-.26-.11C4.45 10.7 3.5 9.33 3.5 7.75c0-1.46.88-2.48 1.94-3.12C6.63 3.91 8.02 3.5 9.5 3.5z"></path>
                      <circle cx="9.5" cy="8" r="1"></circle>
                      <circle cx="12.5" cy="8" r="1"></circle>
                      <path d="M14.5 14c-.28 0-.5.22-.5.5s.22.5.5.5.5-.22.5-.5-.22-.5-.5-.5zm-10 0c-.28 0-.5.22-.5.5s.22.5.5.5.5-.22.5-.5-.22-.5-.5-.5z"></path>
                  </svg>
              </button>
              <button type="button" class="voice-button" id="voiceButton" title="Voice input">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                      <line x1="12" y1="19" x2="12" y2="23"></line>
                      <line x1="8" y1="23" x2="16" y2="23"></line>
                  </svg>
              </button>
              <input type="text" id="messageInput" placeholder="Type your message here..." autofocus class="message-input">
              <button type="submit" id="sendButton">
                  <svg class="send-icon" viewBox="0 0 24 24">
                      <line x1="22" y1="2" x2="11" y2="13"></line>
                      <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                  </svg>
              </button>
          </form>
          <!-- Status bar removed - using in-chat typing indicator -->
      </div>
      <!-- Settings backdrop overlay -->
      <div class="settings-backdrop hidden" id="settingsBackdrop"></div>
      <!-- Settings panel -->
      <div class="settings-pane hidden">
          <h3>Settings</h3>
          <hr/>
          <div class="settings-container">
            <h5>Microphone</h5>
            <select id="microphoneSelect" class="adapter-input">
                <option value="">Detecting microphones...</option>
            </select>
            <div id="micStatus" class="mic-status"></div>
           </div>
          <div class="settings-container">
            <h5>Assistant Identifier</h5>
            <input type="text" id="assistantIdentifierInput" placeholder="Assistant Identifier (optional)" class="adapter-input" >
           </div>
           <div class="settings-container">
            <h5>Custom System Prompt</h5>
            <textarea id="customSystemPromptInput" placeholder="Custom System Prompt (optional)" class="system-prompt-input"></textarea>
           </div>
      </div>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        // Store console messages before DOM loads
        const consoleBuffer = [];
        const originalConsoleLog = console.log;
        const originalConsoleError = console.error;
        
        console.log = function(...args) {
            originalConsoleLog.apply(console, args);
            consoleBuffer.push({ message: args.join(' '), type: 'log' });
        };
        
        console.error = function(...args) {
            originalConsoleError.apply(console, args);
            consoleBuffer.push({ message: args.join(' '), type: 'error' });
        };
        
        console.log('Script loading...');
        
        // Function to initialize the UI
        function initializeUI() {
            console.log('=== initializeUI called ===');
            
            // Test if we can access DOM elements
            const testButton = document.getElementById('closeButton');
            console.log('Close button element:', testButton ? 'FOUND' : 'NOT FOUND');
            
            // Debug console setup (F12 only, no visible button)
            const debugConsole = document.getElementById('debugConsole');
            console.log('Debug console element:', debugConsole ? 'FOUND' : 'NOT FOUND');
            
            function addDebugLine(message, type = 'log') {
                if (!debugConsole) return;
                const line = document.createElement('div');
                line.className = 'debug-console-line';
                line.style.color = type === 'error' ? '#ff4d4d' : '#00ff00';
                line.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
                debugConsole.appendChild(line);
                debugConsole.scrollTop = debugConsole.scrollHeight;
                // Keep only last 100 lines
                if (debugConsole.children.length > 100) {
                    debugConsole.removeChild(debugConsole.firstChild);
                }
            }
            
            // Override console functions with working version
            console.log = function(...args) {
                originalConsoleLog.apply(console, args);
                addDebugLine(args.join(' '), 'log');
            };
            
            console.error = function(...args) {
                originalConsoleError.apply(console, args);
                addDebugLine(args.join(' '), 'error');
            };
            
            // Add buffered messages
            consoleBuffer.forEach(item => addDebugLine(item.message, item.type));
            
            // Toggle debug console
            function toggleDebugConsole() {
                if (debugConsole) {
                    debugConsole.classList.toggle('show');
                }
            }
            
            // Keyboard shortcut for debug console (F12 only, no button)
            document.addEventListener('keydown', function(e) {
                if (e.key === 'F12') {
                    e.preventDefault();
                    toggleDebugConsole();
                    console.log('Debug console toggled via F12');
                }
            });
            const messageForm = document.getElementById('messageForm');
            const messageInput = document.getElementById('messageInput');
            const assistantIdentifierInput = document.getElementById('assistantIdentifierInput');
            const customSystemPromptInput = document.getElementById('customSystemPromptInput');
            const messagesContainer = document.getElementById('messages');
            const statusText = document.getElementById('status');
            const statusDot = document.getElementById('statusDot');
            const statusBar = document.getElementById('status');
            const settingsPane = document.querySelector('.settings-pane');
            const settingsBackdrop = document.getElementById('settingsBackdrop');
            const thinkingToggle = document.getElementById('thinkingToggle');
            const microphoneSelect = document.getElementById('microphoneSelect');
            const micStatus = document.getElementById('micStatus');
            
            console.log('G-Assist UI initialized');
            
            // Microphone detection and management
            let availableMicrophones = [];
            let selectedMicId = localStorage.getItem('selectedMicrophone') || '';
            
            async function enumerateMicrophones() {
                try {
                    // Request permission first
                    await navigator.mediaDevices.getUserMedia({ audio: true });
                    
                    // Get all devices
                    const devices = await navigator.mediaDevices.enumerateDevices();
                    availableMicrophones = devices.filter(device => device.kind === 'audioinput');
                    
                    console.log('Found microphones:', availableMicrophones.length);
                    
                    // Update UI
                    if (microphoneSelect) {
                        microphoneSelect.innerHTML = '';
                        
                        if (availableMicrophones.length === 0) {
                            microphoneSelect.innerHTML = '<option value="">No microphones detected</option>';
                            voiceButton.disabled = true;
                            voiceButton.title = 'No microphones detected';
                            if (micStatus) {
                                micStatus.textContent = 'No microphones found';
                                micStatus.className = 'mic-status error';
                            }
                        } else {
                            availableMicrophones.forEach((device, index) => {
                                const option = document.createElement('option');
                                option.value = device.deviceId;
                                option.textContent = device.label || `Microphone ${index + 1}`;
                                microphoneSelect.appendChild(option);
                            });
                            
                            // Select previously chosen mic or first one
                            if (selectedMicId && availableMicrophones.find(m => m.deviceId === selectedMicId)) {
                                microphoneSelect.value = selectedMicId;
                            } else {
                                microphoneSelect.value = availableMicrophones[0].deviceId;
                                selectedMicId = availableMicrophones[0].deviceId;
                                localStorage.setItem('selectedMicrophone', selectedMicId);
                            }
                            
                            voiceButton.disabled = false;
                            voiceButton.title = 'Voice input';
                            if (micStatus) {
                                micStatus.textContent = `${availableMicrophones.length} microphone(s) detected`;
                                micStatus.className = 'mic-status success';
                            }
                        }
                    }
                } catch (error) {
                    console.error('Microphone enumeration error:', error);
                    if (microphoneSelect) {
                        microphoneSelect.innerHTML = '<option value="">Microphone access denied</option>';
                    }
                    voiceButton.disabled = true;
                    voiceButton.title = 'Microphone access denied';
                    if (micStatus) {
                        micStatus.textContent = 'Microphone access denied. Please grant permission.';
                        micStatus.className = 'mic-status error';
                    }
                }
            }
            
            // Handle microphone selection change
            if (microphoneSelect) {
                microphoneSelect.addEventListener('change', function() {
                    selectedMicId = microphoneSelect.value;
                    localStorage.setItem('selectedMicrophone', selectedMicId);
                    console.log('Selected microphone:', selectedMicId);
                });
            }
            
            // Enumerate microphones on page load
            enumerateMicrophones();
            
            // Thinking toggle state (enabled by default)
            let thinkingEnabled = true;
            // Force the active class to be added
            if (thinkingToggle) {
                thinkingToggle.classList.add('active');
                thinkingToggle.title = 'Thinking mode: ON';
                console.log('Thinking toggle initialized as active:', thinkingToggle.classList.contains('active'));
                
                thinkingToggle.addEventListener('click', function() {
                    thinkingEnabled = !thinkingEnabled;
                    thinkingToggle.classList.toggle('active', thinkingEnabled);
                    thinkingToggle.title = 'Thinking mode: ' + (thinkingEnabled ? 'ON' : 'OFF');
                    console.log('Thinking toggled:', thinkingEnabled);
                });
            } else {
                console.error('Thinking toggle button not found!');
            }
            
            // Settings panel toggle functionality
            function toggleSettings() {
                settingsPane.classList.toggle('hidden');
                settingsBackdrop.classList.toggle('hidden');
            }
            
            // Close settings when clicking backdrop
            settingsBackdrop.addEventListener('click', toggleSettings);
            
            // Minimize button functionality
            const minimizeButton = document.getElementById('minimizeButton');
            if (minimizeButton) {
                console.log('Minimize button found, adding event listener');
                minimizeButton.addEventListener('click', function(e) {
                    e.preventDefault();
                    console.log('Minimize button clicked!');
                    
                    // For pywebview desktop mode
                    if (window.pywebview && window.pywebview.api) {
                        console.log('Calling pywebview.api.minimize_app()');
                        try {
                            window.pywebview.api.minimize_app();
                        } catch (error) {
                            console.error('Error calling minimize_app:', error);
                        }
                    } else {
                        console.log('Minimize not available in browser mode');
                    }
                });
            } else {
                console.error('Minimize button not found!');
            }
            
            // Close button functionality
            const closeButton = document.getElementById('closeButton');
            if (closeButton) {
                console.log('Close button found, adding event listener');
                closeButton.addEventListener('click', function(e) {
                    e.preventDefault();
                    console.log('Close button clicked!');
                    closeButton.title = 'Closing...';
                    
                    // For pywebview desktop mode
                    if (window.pywebview && window.pywebview.api) {
                        console.log('Calling pywebview.api.close_app()');
                        try {
                            window.pywebview.api.close_app();
                        } catch (error) {
                            console.error('Error calling close_app:', error);
                        }
                    } else {
                        console.log('Fallback: calling window.close()');
                        // Fallback for browser mode
                        window.close();
                    }
                });
            } else {
                console.error('Close button not found!');
            }
            
            // Voice recording functionality
            const voiceButton = document.getElementById('voiceButton');
            let mediaRecorder = null;
            let audioChunks = [];
            let isRecording = false;
            
            if (voiceButton) {
                console.log('Voice button found, adding event listener');
                
                voiceButton.addEventListener('click', async function() {
                    if (!isRecording) {
                        // Start recording
                        try {
                            // Use selected microphone if available
                            const constraints = {
                                audio: selectedMicId ? { deviceId: { exact: selectedMicId } } : true
                            };
                            const stream = await navigator.mediaDevices.getUserMedia(constraints);
                            mediaRecorder = new MediaRecorder(stream);
                            audioChunks = [];
                            
                            mediaRecorder.ondataavailable = (event) => {
                                audioChunks.push(event.data);
                            };
                            
                            mediaRecorder.onstop = async () => {
                                voiceButton.classList.remove('recording');
                                voiceButton.title = 'Voice input';
                                
                                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                                
                                // Send to backend for transcription
                                try {
                                    const formData = new FormData();
                                    formData.append('audio', audioBlob, 'recording.wav');
                                    
                                    const apiUrl = `${window.location.protocol}//${window.location.host}/api/transcribe`;
                                    const response = await fetch(apiUrl, {
                                        method: 'POST',
                                        body: formData
                                    });
                                    
                                    const result = await response.json();
                                    
                                    if (result.text) {
                                        // Populate input field with transcribed text
                                        messageInput.value = result.text.trim();
                                        messageInput.focus();
                                        console.log('Transcribed:', result.text);
                                    } else if (result.error) {
                                        console.error('Transcription error:', result.error);
                                        addMessage('system', 'Error: ' + result.error);
                                    }
                                } catch (error) {
                                    console.error('Transcription request failed:', error);
                                    addMessage('system', 'Error: Failed to transcribe audio');
                                }
                                
                                // Stop all tracks
                                stream.getTracks().forEach(track => track.stop());
                            };
                            
                            mediaRecorder.start();
                            isRecording = true;
                            voiceButton.classList.add('recording');
                            voiceButton.title = 'Recording... (click to stop)';
                            console.log('Recording started');
                            
                        } catch (error) {
                            console.error('Microphone access error:', error);
                            addMessage('system', 'Error: Could not access microphone');
                        }
                    } else {
                        // Stop recording
                        if (mediaRecorder && mediaRecorder.state === 'recording') {
                            mediaRecorder.stop();
                            isRecording = false;
                            console.log('Recording stopped');
                        }
                    }
                });
            } else {
                console.error('Voice button not found!');
            }
            
            // Hamburger menu functionality
            const hamburgerButton = document.getElementById('hamburgerButton');
            const dropdownMenu = document.getElementById('dropdownMenu');
            const settingsMenuItem = document.getElementById('settingsMenuItem');
            const exportMenuItem = document.getElementById('exportMenuItem');
            
            if (hamburgerButton && dropdownMenu) {
                console.log('Hamburger menu found, adding event listener');
                
                hamburgerButton.addEventListener('click', function(e) {
                    e.stopPropagation();
                    dropdownMenu.classList.toggle('show');
                    console.log('Hamburger menu toggled:', dropdownMenu.classList.contains('show'));
                });
                
                // Close dropdown when clicking outside
                document.addEventListener('click', function(e) {
                    if (!hamburgerButton.contains(e.target) && !dropdownMenu.contains(e.target)) {
                        dropdownMenu.classList.remove('show');
                    }
                });
                
                // Settings menu item - opens settings pane
                if (settingsMenuItem) {
                    settingsMenuItem.addEventListener('click', function() {
                        dropdownMenu.classList.remove('show');
                        toggleSettings();
                    });
                }
                
                // Export menu item - export chat history
                if (exportMenuItem) {
                    exportMenuItem.addEventListener('click', function() {
                        dropdownMenu.classList.remove('show');
                        exportChatHistory();
                    });
                }
            }
            
            // Export chat history function
            function exportChatHistory() {
                const messagesDiv = document.getElementById('messages');
                if (!messagesDiv) return;
                
                const messages = messagesDiv.querySelectorAll('.message');
                const chatHistory = [];
                
                messages.forEach(msg => {
                    const senderElem = msg.querySelector('.sender');
                    const messageContent = msg.querySelector('.message-content');
                    
                    if (!senderElem || !messageContent) return;
                    
                    const senderText = senderElem.textContent.trim().toLowerCase();
                    
                    // Map sender to OpenAI format roles
                    // Sender text format: "You: ", "G-Assist: ", "System: "
                    let role = 'user';
                    if (senderText.startsWith('you')) {
                        role = 'user';
                    } else if (senderText.startsWith('g-assist')) {
                        role = 'assistant';
                    } else if (senderText.startsWith('system')) {
                        role = 'system';
                    }
                    
                    // Extract content with thinking blocks preserved
                    let content = '';
                    
                    // Check for thinking blocks in the entire message content
                    const thinkingBlocks = messageContent.querySelectorAll('.thinking-block');
                    
                    if (thinkingBlocks.length > 0) {
                        // Message has thinking blocks - preserve them with tags
                        thinkingBlocks.forEach(thinkBlock => {
                            const thinkContent = thinkBlock.textContent.trim();
                            // Skip the "💭 Thinking..." header if present
                            const actualContent = thinkContent.replace(/^💭\s*Thinking\.\.\./, '').trim();
                            if (actualContent) {
                                content += '<think>\n' + actualContent + '\n</think>\n\n';
                            }
                        });
                        
                        // Extract ONLY text nodes and non-thinking-block elements from .text
                        const textElem = messageContent.querySelector('.text');
                        if (textElem) {
                            let regularText = '';
                            
                            function extractTextExcludingThinkingBlocks(node) {
                                for (const child of node.childNodes) {
                                    if (child.nodeType === Node.TEXT_NODE) {
                                        // Plain text node - include it
                                        regularText += child.textContent;
                                    } else if (child.nodeType === Node.ELEMENT_NODE) {
                                        // Element node - check if it's a thinking-block
                                        if (child.classList && child.classList.contains('thinking-block')) {
                                            // Skip thinking blocks entirely
                                            continue;
                                        } else {
                                            // For other elements (code blocks, etc), recurse into them
                                            extractTextExcludingThinkingBlocks(child);
                                        }
                                    }
                                }
                            }
                            
                            extractTextExcludingThinkingBlocks(textElem);
                            const trimmed = regularText.trim();
                            if (trimmed) {
                                content += trimmed;
                            }
                        }
                    } else {
                        // No thinking blocks - just get text content
                        const textElem = messageContent.querySelector('.text');
                        content = textElem ? textElem.textContent.trim() : '';
                    }
                    
                    // Skip system welcome message
                    if (senderText.startsWith('system') && content.includes('Welcome to G-Assist')) {
                        return;
                    }
                    
                    if (content) {
                        chatHistory.push({
                            role: role,
                            content: content
                        });
                    }
                });
                
                console.log('Exporting chat history:', chatHistory.length, 'messages');
                
                // Check if running in pywebview desktop mode
                if (window.pywebview && window.pywebview.api) {
                    // Use Python API to save with file dialog
                    const jsonData = JSON.stringify(chatHistory);
                    window.pywebview.api.save_chat_history(jsonData).then(result => {
                        console.log('Save result:', result);
                    });
                } else {
                    // Browser mode - use download link
                    const jsonData = JSON.stringify(chatHistory, null, 2);
                    const blob = new Blob([jsonData], { type: 'application/json' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    const timestamp = new Date().toISOString().replace(/:/g, '-').split('.')[0];
                    a.download = `gassist-chat-${timestamp}.json`;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    URL.revokeObjectURL(url);
                }
            }
            
            // Ctrl+Q keyboard shortcut for closing
            document.addEventListener('keydown', function(e) {
                if (e.ctrlKey && e.key === 'q') {
                    e.preventDefault();
                    console.log('Ctrl+Q pressed, closing app');
                    if (window.pywebview && window.pywebview.api) {
                        window.pywebview.api.close_app();
                    } else {
                        window.close();
                    }
                }
            });
            
            function isJSON(str) {
                try {
                    JSON.parse(str);
                    return true;
                } catch (e) {
                    return false;
                }
            }
            
            function syntaxHighlightJSON(json) {
                // Syntax highlight JSON string
                json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
                return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
                    let cls = 'json-number';
                    if (/^"/.test(match)) {
                        if (/:$/.test(match)) {
                            cls = 'json-key';
                        } else {
                            cls = 'json-string';
                        }
                    } else if (/true|false/.test(match)) {
                        cls = 'json-boolean';
                    } else if (/null/.test(match)) {
                        cls = 'json-null';
                    }
                    return '<span class="' + cls + '">' + match + '</span>';
                });
            }
            
            function formatContent(text) {
                // Check for complete <think>...</think> pairs
                const completeThinkRegex = /<think>([\s\S]*?)<\/think>/g;
                const hasCompleteThinkTags = completeThinkRegex.test(text);
                
                // Check for incomplete <think> (no closing tag yet - streaming in progress)
                const openThinkPos = text.indexOf('<think>');
                const closeThinkPos = text.indexOf('</think>');
                const hasIncompleteThink = openThinkPos !== -1 && (closeThinkPos === -1 || closeThinkPos < openThinkPos);
                
                if (hasCompleteThinkTags || hasIncompleteThink) {
                    // Create a container for mixed content
                    const container = document.createElement('div');
                    
                    // Process complete thinking blocks first
                    completeThinkRegex.lastIndex = 0;
                    let lastIndex = 0;
                    let match;
                    
                    while ((match = completeThinkRegex.exec(text)) !== null) {
                        // Add text before the thinking block
                        const beforeText = text.substring(lastIndex, match.index);
                        if (beforeText.trim()) {
                            const textSpan = document.createElement('span');
                            textSpan.textContent = beforeText;
                            container.appendChild(textSpan);
                        }
                        
                        // Add the complete thinking block
                        const thinkingBlock = document.createElement('div');
                        thinkingBlock.className = 'thinking-block';
                        const pre = document.createElement('pre');
                        pre.textContent = match[1].trim();
                        thinkingBlock.appendChild(pre);
                        container.appendChild(thinkingBlock);
                        
                        lastIndex = match.index + match[0].length;
                    }
                    
                    // Handle remaining text (might contain incomplete <think>)
                    const afterText = text.substring(lastIndex);
                    
                    // Check if remaining text has incomplete <think> tag
                    const incompleteThinkPos = afterText.indexOf('<think>');
                    if (incompleteThinkPos !== -1) {
                        // Add text before <think>
                        const beforeThink = afterText.substring(0, incompleteThinkPos);
                        if (beforeThink.trim()) {
                            const textSpan = document.createElement('span');
                            textSpan.textContent = beforeThink;
                            container.appendChild(textSpan);
                        }
                        
                        // Add incomplete thinking block (streaming in progress)
                        const incompleteContent = afterText.substring(incompleteThinkPos + 7); // Skip '<think>'
                        const thinkingBlock = document.createElement('div');
                        thinkingBlock.className = 'thinking-block';
                        const pre = document.createElement('pre');
                        pre.textContent = incompleteContent.trim() || '...'; // Show ellipsis if empty
                        thinkingBlock.appendChild(pre);
                        container.appendChild(thinkingBlock);
                    } else if (afterText.trim()) {
                        // No incomplete think tag, check if it's JSON or plain text
                        if (isJSON(afterText.trim())) {
                            try {
                                const parsed = JSON.parse(afterText.trim());
                                const formatted = JSON.stringify(parsed, null, 2);
                                const codeBlock = document.createElement('div');
                                codeBlock.className = 'code-block';
                                const pre = document.createElement('pre');
                                pre.innerHTML = syntaxHighlightJSON(formatted);
                                codeBlock.appendChild(pre);
                                container.appendChild(codeBlock);
                            } catch (e) {
                                const textSpan = document.createElement('span');
                                textSpan.textContent = afterText;
                                container.appendChild(textSpan);
                            }
                        } else {
                            const textSpan = document.createElement('span');
                            textSpan.textContent = afterText;
                            container.appendChild(textSpan);
                        }
                    }
                    
                    return container;
                }
                
                // Check if the text is JSON (no thinking blocks)
                if (isJSON(text)) {
                    try {
                        const parsed = JSON.parse(text);
                        const formatted = JSON.stringify(parsed, null, 2);
                        const codeBlock = document.createElement('div');
                        codeBlock.className = 'code-block';
                        const pre = document.createElement('pre');
                        pre.innerHTML = syntaxHighlightJSON(formatted);
                        codeBlock.appendChild(pre);
                        return codeBlock;
                    } catch (e) {
                        // If parsing fails, return as text
                        return text;
                    }
                }
                return text;
            }
            
            function showTypingIndicator() {
                const typingDiv = document.createElement('div');
                typingDiv.className = 'message assistant typing';
                typingDiv.id = 'typing-indicator';
                
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content';
                
                const headerDiv = document.createElement('div');
                headerDiv.className = 'message-header';
                
                const sender = document.createElement('span');
                sender.className = 'sender';
                sender.textContent = 'G-Assist';
                headerDiv.appendChild(sender);
                
                const indicatorDiv = document.createElement('div');
                indicatorDiv.className = 'typing-indicator';
                
                for (let i = 0; i < 3; i++) {
                    const dot = document.createElement('span');
                    indicatorDiv.appendChild(dot);
                }
                
                contentDiv.appendChild(headerDiv);
                contentDiv.appendChild(indicatorDiv);
                typingDiv.appendChild(contentDiv);
                
                messagesContainer.appendChild(typingDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            function hideTypingIndicator() {
                const typingIndicator = document.getElementById('typing-indicator');
                if (typingIndicator) {
                    typingIndicator.remove();
                }
            }
            
            messageForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const message = messageInput.value.trim();
                const assistant_identifier = assistantIdentifierInput.value.trim();
                const custom_system_prompt = customSystemPromptInput.value.trim();
                if (!message) return;
                
                // Disable input and send button
                messageInput.disabled = true;
                const sendButton = document.getElementById('sendButton');
                if (sendButton) sendButton.disabled = true;
                
                // Add user message
                addMessage('user', message);
                messageInput.value = '';
                
                // Show typing indicator
                showTypingIndicator();
                
                try {
                    // Use streaming endpoint (dynamically use current port)
                    const apiUrl = `${window.location.protocol}//${window.location.host}/api/send-message-stream`;
                    const response = await fetch(apiUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ message, assistant_identifier, custom_system_prompt, thinking_enabled: thinkingEnabled })
                    });
                    
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let assistantText = '';
                    let assistantMessageAdded = false;
                    
                    while (true) {
                        const { value, done } = await reader.read();
                        if (done) break;
                        
                        const chunk = decoder.decode(value, { stream: true });
                        // Split by actual newline character (char code 10)
                        const lines = chunk.split(/\n/);
                        
                        for (const line of lines) {
                            const trimmedLine = line.trim();
                            if (trimmedLine && trimmedLine.startsWith('data: ')) {
                                const jsonStr = trimmedLine.substring(6).trim();
                                if (!jsonStr) continue;
                                try {
                                    const data = JSON.parse(jsonStr);
                                    
                                    if (data.chunk) {
                                        // Hide typing indicator on first chunk
                                        if (!assistantMessageAdded) {
                                            hideTypingIndicator();
                                            assistantMessageAdded = true;
                                            addMessage('assistant', '');
                                        }
                                        
                                        // Append chunk
                                        assistantText += data.chunk;
                                        
                                        // Update the last assistant message with formatted content
                                        const messages = messagesContainer.querySelectorAll('.message.assistant:not(.typing)');
                                        const lastMessage = messages[messages.length - 1];
                                        if (lastMessage) {
                                            const textSpan = lastMessage.querySelector('.text');
                                            if (textSpan) {
                                                // Clear existing content
                                                textSpan.innerHTML = '';
                                                // Format content (handles thinking blocks, JSON, etc.)
                                                const formatted = formatContent(assistantText);
                                                if (typeof formatted === 'string') {
                                                    textSpan.textContent = formatted;
                                                } else {
                                                    textSpan.appendChild(formatted);
                                                }
                                            }
                                        }
                                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                    } else if (data.tool_call) {
                                        // Handle tool call response
                                        console.log('Received tool_call:', data.tool_call);
                                        hideTypingIndicator();
                                        
                                        // Always add a new message for tool calls
                                        const formatted = formatContent(data.tool_call);
                                        
                                        // Create message manually to ensure it's added
                                        const messageDiv = document.createElement('div');
                                        messageDiv.className = 'message assistant';
                                        
                                        const contentDiv = document.createElement('div');
                                        contentDiv.className = 'message-content assistant';
                                        
                                        const sender = document.createElement('span');
                                        sender.className = 'sender';
                                        sender.textContent = 'G-Assist: ';
                                        contentDiv.appendChild(sender);
                                        
                                        const textSpan = document.createElement('span');
                                        textSpan.className = 'text';
                                        if (typeof formatted === 'string') {
                                            textSpan.textContent = formatted;
                                        } else {
                                            textSpan.appendChild(formatted);
                                        }
                                        contentDiv.appendChild(textSpan);
                                        
                                        const timestamp = document.createElement('span');
                                        timestamp.className = 'timestamp';
                                        timestamp.textContent = new Date().toLocaleTimeString();
                                        contentDiv.appendChild(timestamp);
                                        
                                        messageDiv.appendChild(contentDiv);
                                        messagesContainer.appendChild(messageDiv);
                                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                        
                                        assistantMessageAdded = true;
                                    } else if (data.done) {
                                        hideTypingIndicator();
                                        // Re-enable input and send button
                                        messageInput.disabled = false;
                                        if (sendButton) sendButton.disabled = false;
                                        messageInput.focus();
                                    } else if (data.error) {
                                        console.error('Server error:', data.error);
                                        hideTypingIndicator();
                                        addMessage('system', 'Error: ' + data.error);
                                        // Re-enable input and send button
                                        messageInput.disabled = false;
                                        if (sendButton) sendButton.disabled = false;
                                        messageInput.focus();
                                    }
                                } catch (parseError) {
                                    // Silently ignore parse errors for incomplete chunks
                                }
                            }
                        }
                    }
                } catch (error) {
                    console.error('Error:', error);
                    hideTypingIndicator();
                    addMessage('system', 'Error communicating with G-Assist: ' + error.message);
                    // Re-enable input and send button
                    messageInput.disabled = false;
                    if (sendButton) sendButton.disabled = false;
                    messageInput.focus();
                }
            });
            function getScalesForData(chunkData) {
                let axes = {};

                if (chunkData?.length > 0) {
                    chunkData.forEach((chartData, index) => {
                        const xAxisName = 'x' + ((index !== 0) ? index : '');
                        const yAxisName = 'y' + ((index !== 0) ? index : '');
                        if (index === 0) {
                            axes = {
                                ...axes,
                                x: {
                                    title: {
                                        display: true,
                                        text: (chartData.xUnit !== '%') ? chartData.xUnit : ''
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
                                        text: (chartData.yUnit !== '%') ? chartData.yUnit : ''
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
                                            text: (chartData.xUnit !== '%') ? chartData.xUnit : ''
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
                                            text: (chartData.yUnit !== '%') ? chartData.yUnit : ''
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
                messageDiv.className = 'message ' + type;
                
                // Create the inner container with bounding box styling
                const contentDiv = document.createElement('div');
                contentDiv.className = 'message-content ' + type;
                
                // Create and append the sender element
                const sender = document.createElement('span');
                sender.className = 'sender';
                sender.textContent = type === 'user' ? 'You: ' : type === 'assistant' ? 'G-Assist: ' : 'System: ';
                contentDiv.appendChild(sender);
                
                // Create and append the text element
                const textSpan = document.createElement('span');
                textSpan.className = 'text';
                // Format content (JSON as code block, text as-is)
                const formatted = formatContent(text);
                if (typeof formatted === 'string') {
                    textSpan.textContent = formatted;
                } else {
                    textSpan.appendChild(formatted);
                }
                contentDiv.appendChild(textSpan);
                        
                // Create and append the chart element
                if(chart !== '') {
                    const chartDiv = document.createElement('div');
                    const chartCanvas = document.createElement('canvas');
                    chartId = 'chart-' + Math.floor(Math.random() * 1000000);
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
                                xAxisID: (index !== 0 && chartInfo.xUnit !== chartData[0].xUnit) ? ('x' + index) : 'x',
                                yAxisID: (index !== 0 && chartInfo.yUnit !== chartData[0].yUnit) ? ('y' + index) : 'y',
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
                                              label += ' ' + chartData[context.datasetIndex].yUnit;
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
        }
        
        // Run initialization immediately if DOM is already loaded, otherwise wait
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOM loaded via event listener');
                initializeUI();
            });
        } else {
            // DOM already loaded, run immediately
            console.log('DOM already loaded, initializing immediately');
            console.log('Document ready state:', document.readyState);
            initializeUI();
        }
        
        console.log('Script executed, waiting for initialization...');
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

def open_browser():
    """Open the default web browser after a short delay to ensure Flask is ready"""
    time.sleep(1.5)  # Wait for Flask to start
    webbrowser.open('http://127.0.0.1:5000')

def check_single_instance():
    """Check if another instance is already running"""
    import os
    import psutil
    import tempfile
    
    # Use temp directory for lock file (works in both dev and exe)
    lock_file = os.path.join(tempfile.gettempdir(), 'gassist_desktop.lock')
    
    # Check if lock file exists
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process is still running
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    # Check if it's actually our process
                    if 'python' in proc.name().lower() or 'g-assist' in proc.name().lower():
                        print("\n" + "="*60)
                        print("ERROR: Another instance of G-Assist is already running!")
                        print("="*60)
                        print(f"\nRunning instance PID: {pid}")
                        print("Please close the existing instance before starting a new one.\n")
                        
                        # Show GUI message box for --noconsole mode
                        try:
                            import tkinter as tk
                            from tkinter import messagebox
                            root = tk.Tk()
                            root.withdraw()  # Hide the main window
                            messagebox.showerror(
                                "G-Assist Already Running",
                                "Another instance of G-Assist is already running.\n\n"
                                f"Running instance PID: {pid}\n\n"
                                "Please close the existing instance before starting a new one."
                            )
                            root.destroy()
                        except:
                            pass  # If GUI fails, console message already printed
                        
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    # Process died or we can't access it, remove stale lock
                    os.remove(lock_file)
            else:
                # Stale lock file, remove it
                os.remove(lock_file)
        except (ValueError, IOError):
            # Invalid lock file, remove it
            try:
                os.remove(lock_file)
            except:
                pass
    
    # Create lock file with current PID
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
    except IOError as e:
        print(f"\nWarning: Could not create lock file: {e}")
    
    return True

def cleanup_lock_file():
    """Remove the lock file on exit"""
    import os
    import tempfile
    lock_file = os.path.join(tempfile.gettempdir(), 'gassist_desktop.lock')
    try:
        if os.path.exists(lock_file):
            os.remove(lock_file)
    except:
        pass

def show_splash_screen():
    """Show a splash screen while the app is loading"""
    import tkinter as tk
    
    splash = tk.Tk()
    splash.withdraw()  # Hide first to position before showing
    splash.overrideredirect(True)  # Remove window decorations
    
    # Set dark background matching app theme
    splash.configure(bg='#0a0a0f')
    
    # Calculate center position
    window_width = 400
    window_height = 200
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    
    splash.geometry(f'{window_width}x{window_height}+{x}+{y}')
    
    # Add G-Assist title
    title_label = tk.Label(
        splash,
        text='G-Assist',
        font=('Segoe UI', 32, 'bold'),
        fg='#00ff88',
        bg='#0a0a0f'
    )
    title_label.pack(pady=(50, 20))
    
    # Add loading message
    loading_label = tk.Label(
        splash,
        text='Launching...',
        font=('Segoe UI', 12),
        fg='#a0a0a0',
        bg='#0a0a0f'
    )
    loading_label.pack()
    
    # Add a subtle border
    splash.config(highlightbackground='#2a2a2f', highlightthickness=1)
    
    splash.deiconify()  # Show the window
    splash.update()
    
    return splash

def start_desktop_mode():
    """Start in desktop mode with native window (requires pywebview)
    Returns: 'success', 'duplicate', or 'missing_deps'
    """
    # Show splash screen immediately
    splash = None
    try:
        splash = show_splash_screen()
    except:
        pass  # If splash fails, continue without it
    
    # Check for single instance
    if not check_single_instance():
        if splash:
            splash.destroy()
        return 'duplicate'  # Another instance is running
    
    # Register cleanup on exit
    import atexit
    atexit.register(cleanup_lock_file)
    
    try:
        import webview
    except ImportError:
        print("\nError: pywebview not installed")
        print("Install with: pip install pywebview")
        print("For Windows CEF support: pip install pywebview[cef]")
        print("\nFalling back to browser mode...")
        if splash:
            splash.destroy()
        cleanup_lock_file()
        return 'missing_deps'  # Missing dependencies, can fall back
    
    print("\nStarting desktop mode...")
    
    # Use fixed port 5000
    port = 5000
    
    # API class for JavaScript to interact with Python
    class Api:
        def __init__(self, window_ref):
            self.window = window_ref
            
        def minimize_app(self):
            """Minimize the application window"""
            try:
                if self.window:
                    self.window.minimize()
                return "Window minimized"
            except Exception as e:
                return f"Error minimizing: {str(e)}"
        
        def close_app(self):
            """Close the application window"""
            import sys
            try:
                # Destroy the window first
                if self.window:
                    self.window.destroy()
            except:
                pass
            # Then exit the application
            sys.exit(0)
        
        def save_chat_history(self, chat_data):
            """Save chat history to a file with a save dialog"""
            try:
                from datetime import datetime
                import json
                import os
                
                # Generate default filename with timestamp
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                default_filename = f"gassist-chat-{timestamp}.json"
                
                # Get user's Documents folder as default directory
                documents_dir = os.path.expanduser('~/Documents')
                
                # Open file save dialog
                result = self.window.create_file_dialog(
                    webview.SAVE_DIALOG,
                    directory=documents_dir,
                    save_filename=default_filename,
                    file_types=('JSON Files (*.json)',)
                )
                
                # result can be None, a string, or a tuple
                if result:
                    # Handle different return types
                    if isinstance(result, tuple) or isinstance(result, list):
                        file_path = result[0] if len(result) > 0 else None
                    else:
                        file_path = result
                    
                    if file_path:
                        # Ensure .json extension
                        if not file_path.endswith('.json'):
                            file_path += '.json'
                        
                        # Parse and save the chat data
                        chat_obj = json.loads(chat_data)
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(chat_obj, f, indent=2, ensure_ascii=False)
                        
                        print(f"[Python] Chat history saved to: {file_path}")
                        print(f"[Python] Saved {len(chat_obj)} messages")
                        return f"Saved {len(chat_obj)} messages to:\n{file_path}"
                    else:
                        return "No file path selected"
                else:
                    return "Save cancelled"
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"[Python] Error saving file: {error_details}")
                return f"Error saving file: {str(e)}"
        
        def open_devtools(self):
            """Open developer tools"""
            try:
                # For pywebview, we need to access the window object
                if webview.windows:
                    # This will toggle dev tools if supported
                    return "DevTools toggled"
                return "No window available"
            except Exception as e:
                return f"Error: {str(e)}"
    
    # Start Flask with waitress in background thread
    flask_thread = threading.Thread(
        target=lambda: serve(app, host='127.0.0.1', port=port, threads=4, _quiet=True),
        daemon=True
    )
    flask_thread.start()
    
    # Wait for Flask to start
    time.sleep(2)
    
    # Create native window (phone-like dimensions, borderless)
    print("Creating native window...")
    api = Api(None)  # Create API first with None window reference
    window = webview.create_window(
        'G-Assist',
        f'http://127.0.0.1:{port}',
        width=473,
        height=932,
        resizable=True,
        frameless=True,
        min_size=(375, 667),
        background_color='#0a0a0f',
        js_api=api
    )
    api.window = window  # Set the window reference after creation
    
    print("=" * 60)
    print(f"G-Assist Desktop is running on port {port}!")
    print("=" * 60 + "\n")
    
    # Close splash screen before starting webview
    if splash:
        try:
            splash.destroy()
        except:
            pass
    
    # Start the webview (blocking)
    webview.start(debug=False)
    return 'success'

def main():
    """Main entry point - supports both browser and desktop modes"""
    import argparse
    
    parser = argparse.ArgumentParser(description='G-Assist GUI')
    parser.add_argument('--desktop', action='store_true', 
                       help='Run in desktop mode with native window (requires pywebview)')
    parser.add_argument('--browser', action='store_true',
                       help='Run in browser mode (default)')
    args = parser.parse_args()
    
    # Print instructions
    print("\n" + "="*60)
    print("G-Assist Interface")
    print("="*60)
    
    # Try desktop mode if requested
    if args.desktop:
        result = start_desktop_mode()
        if result == 'success':
            return  # Desktop mode successful
        elif result == 'duplicate':
            # Another instance is running, exit without starting browser
            return
        # If result is 'missing_deps', fall through to browser mode
    
    # Browser mode (default)
    print("\nStarting server and opening browser...")
    print("\n    http://127.0.0.1:5000\n")
    print("="*60 + "\n")
    
    # Open browser in a separate thread
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start the Flask server with waitress
    print("Server running on http://127.0.0.1:5000")
    serve(app, host='127.0.0.1', port=5000, threads=4)

if __name__ == "__main__":
    main()
