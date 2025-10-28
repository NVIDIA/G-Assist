"""
G-Assist Desktop - Direct Pywebview API (No Flask!)
Uses pywebview's JavaScript-Python bridge for direct communication
"""
import sys
import os
import json
import tempfile
import logging
import struct
import base64
import wave

# Setup logging
log_file = os.path.join(tempfile.gettempdir(), 'gassist_desktop_direct.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import RISE binding
try:
    from rise import rise
    logger.info("Initializing RISE client...")
    rise.register_rise_client()
    logger.info("RISE client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize RISE: {e}")
    import traceback
    logger.error(traceback.format_exc())
    sys.exit(1)

# Pywebview API - Direct JavaScript→Python bridge (NO HTTP!)
class DesktopAPI:
    """Direct API for JavaScript to call Python functions"""
    
    def __init__(self, window_ref=None):
        self.window = window_ref
        self.audio_session = {'chunks_sent': 0, 'total_samples': 0}
    
    # Window control methods
    def minimize_app(self):
        """Minimize window"""
        try:
            if self.window:
                self.window.minimize()
            return {"status": "minimized"}
        except Exception as e:
            return {"error": str(e)}
    
    def close_app(self):
        """Close application"""
        import threading
        def do_close():
            try:
                if self.window:
                    self.window.destroy()
            except:
                pass
            sys.exit(0)
        # Run in a thread to avoid blocking
        threading.Thread(target=do_close, daemon=True).start()
        return {"status": "closing"}
    
    # Audio streaming methods (Direct - No Flask!)
    def process_wav_file(self, file_path):
        """Process entire WAV file and return transcription - DIRECT API"""
        try:
            logger.info(f"[DIRECT] Processing WAV file: {file_path}")
            
            # Read WAV file
            with wave.open(file_path, 'rb') as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                framerate = wav.getframerate()
                n_frames = wav.getnframes()
                
                logger.info(f"[DIRECT] WAV: {channels}ch, {sample_width}B/sample, {framerate}Hz, {n_frames} frames")
                
                # Read audio data
                audio_data = wav.readframes(n_frames)
                
                # Convert to float32
                if sample_width == 2:  # 16-bit PCM
                    pcm_data = struct.unpack(f'<{n_frames * channels}h', audio_data)
                    pcm_float = [float(s) / 32768.0 for s in pcm_data]
                else:
                    return {"error": f"Unsupported sample width: {sample_width}"}
                
                # Convert stereo to mono
                if channels == 2:
                    pcm_float = [(pcm_float[i] + pcm_float[i+1]) / 2.0 
                                 for i in range(0, len(pcm_float), 2)]
            
            logger.info(f"[DIRECT] Total samples: {len(pcm_float)} ({len(pcm_float)/framerate:.2f}s)")
            
            # Send in chunks
            chunk_size = 700
            chunk_id = 0
            last_transcription = ""
            
            for i in range(0, len(pcm_float), chunk_size):
                chunk = pcm_float[i:i+chunk_size]
                chunk_id += 1
                
                # Convert to bytes and base64
                chunk_bytes = struct.pack(f'<{len(chunk)}f', *chunk)
                chunk_base64 = base64.b64encode(chunk_bytes).decode('utf-8')
                
                # Send chunk directly
                result = rise.send_audio_chunk(chunk_base64, chunk_id, framerate)
                
                # Extract transcription
                if result and 'chunk_response' in result:
                    response_text = result['chunk_response'].strip()
                    if response_text:
                        if response_text.startswith("ASR_INTERIM:"):
                            last_transcription = response_text[len("ASR_INTERIM:"):].strip()
                            logger.info(f"[DIRECT] Interim[{chunk_id}]: {last_transcription}")
                        elif response_text.startswith("ASR_FINAL:"):
                            last_transcription = response_text[len("ASR_FINAL:"):].strip()
                            logger.info(f"[DIRECT] Final[{chunk_id}]: {last_transcription}")
            
            # Send STOP signal
            logger.info("[DIRECT] Sending STOP signal...")
            stop_result = rise.send_audio_stop()
            if stop_result and 'final_response' in stop_result:
                final_text = stop_result['final_response'].strip()
                if final_text:
                    if final_text.startswith("ASR_FINAL:"):
                        last_transcription = final_text[len("ASR_FINAL:"):].strip()
                    elif final_text.startswith("ASR_INTERIM:"):
                        last_transcription = final_text[len("ASR_INTERIM:"):].strip()
                    logger.info(f"[DIRECT] Final result: {last_transcription}")
            
            return {
                "status": "success",
                "text": last_transcription,
                "chunks_sent": chunk_id,
                "duration_seconds": len(pcm_float) / framerate
            }
            
        except Exception as e:
            logger.error(f"[DIRECT] Error processing WAV: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}
    
    def send_audio_chunk(self, chunk_base64, chunk_id, sample_rate):
        """Send audio chunk - DIRECT API"""
        try:
            result = rise.send_audio_chunk(chunk_base64, chunk_id, sample_rate)
            
            response_data = {'chunk_id': chunk_id}
            if result and 'chunk_response' in result:
                response_text = result['chunk_response'].strip()
                if response_text:
                    if response_text.startswith("ASR_INTERIM:"):
                        response_data['text'] = response_text[len("ASR_INTERIM:"):].strip()
                    elif response_text.startswith("ASR_FINAL:"):
                        response_data['text'] = response_text[len("ASR_FINAL:"):].strip()
                        response_data['is_final'] = True
            
            return response_data
        except Exception as e:
            logger.error(f"[DIRECT] Chunk error: {e}")
            return {'error': str(e)}
    
    def send_audio_stop(self):
        """Send stop signal - DIRECT API"""
        try:
            import time
            python_start = time.time()
            stop_result = rise.send_audio_stop()
            python_got_result = time.time()
            
            response_data = {}
            if stop_result and 'final_response' in stop_result:
                final_text = stop_result['final_response'].strip()
                logger.info(f"[DIRECT] send_audio_stop() received: '{final_text}'")
                
                if final_text:
                    if final_text.startswith("ASR_FINAL:"):
                        stripped = final_text[len("ASR_FINAL:"):].strip()
                        response_data['final_text'] = stripped
                        logger.info(f"[DIRECT] Returning final_text: '{stripped}'")
                    elif final_text.startswith("ASR_INTERIM:"):
                        stripped = final_text[len("ASR_INTERIM:"):].strip()
                        response_data['final_text'] = stripped
                        logger.info(f"[DIRECT] Returning final_text (from interim): '{stripped}'")
                    else:
                        logger.warning(f"[DIRECT] No ASR prefix found in: '{final_text}'")
            
            python_return = time.time()
            logger.info(f"[DIRECT] Python processing time: {(python_return - python_got_result)*1000:.1f}ms (total: {(python_return - python_start)*1000:.1f}ms)")
            return response_data
        except Exception as e:
            logger.error(f"[DIRECT] Stop error: {e}")
            return {'error': str(e)}
    
    def send_message(self, message, assistant_id="", system_prompt="", thinking=False):
        """Send message to RISE - DIRECT API"""
        try:
            logger.info(f"[DIRECT] Sending message: {message[:50]}...")
            result = rise.send_rise_command(message, assistant_id, system_prompt, thinking)
            
            if result and 'completed_response' in result:
                return {
                    "status": "success",
                    "response": result['completed_response'],
                    "chart": result.get('completed_chart', '')
                }
            return {"status": "success", "response": str(result)}
        except Exception as e:
            logger.error(f"[DIRECT] Message error: {e}")
            return {"error": str(e)}
    
    def send_message_stream_start(self, message, assistant_id="", system_prompt="", thinking=False):
        """Start streaming message to RISE - runs in background thread"""
        try:
            logger.info(f"[DIRECT] Starting streaming message: {message[:50]}...")
            
            # CRITICAL: Reset global rise module variables BEFORE starting thread!
            # Otherwise JavaScript polling sees stale response_done=True from previous request
            rise.response_done = False
            rise.response = ""
            rise.chart = ""
            
            # Reset streaming state and track start time
            import time
            self.streaming_active = True
            self.streaming_response = ""
            self.streaming_done = False
            self.streaming_error = None
            self.streaming_start_time = time.time()  # Track when we start
            self.streaming_first_token_time = None  # Will be set when first token arrives
            
            # Start the command in a background thread
            def run_command():
                try:
                    result = rise.send_rise_command(message, assistant_id, system_prompt, thinking)
                    # Store the final response before it gets cleared
                    if result and 'completed_response' in result:
                        self.streaming_response = result['completed_response']
                    else:
                        self.streaming_response = str(result)
                    self.streaming_done = True
                except Exception as e:
                    logger.error(f"[DIRECT] Streaming error: {e}")
                    self.streaming_error = str(e)
                    self.streaming_done = True
            
            import threading
            thread = threading.Thread(target=run_command, daemon=True)
            thread.start()
            
            return {"status": "started", "start_time": self.streaming_start_time}
        except Exception as e:
            logger.error(f"[DIRECT] Stream start error: {e}")
            return {"error": str(e)}
    
    def get_stream_update(self):
        """Poll for streaming response updates - returns current response text"""
        try:
            import time
            # Get current response directly from rise module's global variable
            # But use our stored copy if streaming is done (rise.response gets cleared)
            if hasattr(self, 'streaming_done') and self.streaming_done and hasattr(self, 'streaming_response'):
                current_response = self.streaming_response
            else:
                current_response = rise.response
            
            # Calculate TTFT when first token arrives
            ttft = None
            if current_response and hasattr(self, 'streaming_start_time'):
                if not hasattr(self, 'streaming_first_token_time') or self.streaming_first_token_time is None:
                    # First token just arrived!
                    self.streaming_first_token_time = time.time()
                    ttft = self.streaming_first_token_time - self.streaming_start_time
                    logger.info(f"[TTFT] Time to first token: {ttft:.3f}s")
                    print(f"[TTFT] Time to first token: {ttft:.3f}s", flush=True)
                else:
                    # Already calculated, return the same value
                    ttft = self.streaming_first_token_time - self.streaming_start_time
            
            result = {
                "status": "success",
                "text": current_response,
                "done": self.streaming_done if hasattr(self, 'streaming_done') else rise.response_done,
                "error": self.streaming_error if hasattr(self, 'streaming_error') else None,
                "ttft": ttft  # Time to first token in seconds
            }
            
            # Debug log when done
            if result["done"]:
                print(f"[DEBUG] Returning DONE update - text length: {len(current_response)}, TTFT: {ttft}", flush=True)
            
            return result
        except Exception as e:
            logger.error(f"[DIRECT] Stream update error: {e}")
            return {"error": str(e)}
    
    def save_chat_history(self, chat_data):
        """Save chat with file dialog"""
        try:
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            default_filename = f"gassist-chat-{timestamp}.json"
            documents_dir = os.path.expanduser('~/Documents')
            
            result = self.window.create_file_dialog(
                webview.SAVE_DIALOG,
                directory=documents_dir,
                save_filename=default_filename,
                file_types=('JSON Files (*.json)',)
            )
            
            if result:
                file_path = result[0] if isinstance(result, (tuple, list)) else result
                if file_path:
                    if not file_path.endswith('.json'):
                        file_path += '.json'
                    
                    chat_obj = json.loads(chat_data)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(chat_obj, f, indent=2, ensure_ascii=False)
                    
                    logger.info(f"Chat saved: {file_path} ({len(chat_obj)} messages)")
                    return f"Saved {len(chat_obj)} messages"
            
            return "Save cancelled"
        except Exception as e:
            logger.error(f"Save error: {e}")
            return f"Error: {str(e)}"

def get_html():
    """Full UI from rise-gui.py with direct API modifications"""
    html = '''
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
            margin-bottom: 16px;
            padding: 12px;
            padding-bottom: 24px;
            display: flex;
            flex-direction: column;
            gap: 20px;
            scrollbar-width: thin;
            scrollbar-color: var(--accent-primary) var(--bg-secondary);
            scroll-behavior: smooth;
        }
        
        .messages::-webkit-scrollbar {
            width: 4px;
        }
        
        .messages::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .messages::-webkit-scrollbar-thumb {
            background-color: var(--accent-primary);
            border-radius: 3px;
        }
        
        .messages::-webkit-scrollbar-thumb:hover {
            background-color: var(--accent-secondary);
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
        
        .ttft-metric {
            color: var(--accent-secondary);
            font-size: 0.7rem;
            font-weight: 500;
            margin-top: 8px;
            padding: 4px 8px;
            background: rgba(118, 185, 0, 0.1);
            border-radius: 4px;
            display: inline-block;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        
        .ttft-metric::before {
            content: '⚡ ';
        }
        
        .text {
            word-break: break-word;
            white-space: pre-wrap;
        }
        
        .text pre {
            background-color: #1e1e1e;
            border: 1px solid #333;
            border-radius: 6px;
            padding: 12px;
            margin: 8px 0;
            overflow-x: auto;
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            font-size: 0.85rem;
            line-height: 1.5;
            color: #76b900;
        }
        
        .text code {
            font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
            color: #76b900;
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
            content: "Thinking...";
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
        
        /* Thinking bubble styles */
        .thinking-bubble {
            background: rgba(118, 185, 0, 0.1);
            border-left: 3px solid var(--accent-secondary);
            padding: 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        
        .thinking-bubble strong {
            color: var(--accent-secondary);
            display: block;
            margin-bottom: 8px;
        }
        
        .thinking-bubble pre {
            margin: 0;
            white-space: pre-wrap;
            color: var(--text-primary);
        }
        
        .thinking-active {
            animation: pulse-thinking 1.5s ease-in-out infinite;
        }
        
        @keyframes pulse-thinking {
            0%, 100% { 
                background: rgba(118, 185, 0, 0.1);
                border-left-color: var(--accent-secondary);
            }
            50% { 
                background: rgba(118, 185, 0, 0.2);
                border-left-color: #a0d965;
            }
        }
        
        .cursor-blink {
            animation: blink 1s step-start infinite;
            color: var(--accent-secondary);
        }
        
        @keyframes blink {
            50% { opacity: 0; }
        }
        
        .input-area {
            display: flex;
            flex: 1 1 auto;
            min-width: 0;
            max-width: calc(100% - 100px);
            margin-bottom: 0;
            background-color: var(--input-bg);
            border-radius: var(--border-radius);
            padding: 8px;
            box-shadow: var(--shadow);
            align-items: flex-end;
            gap: 8px;
            overflow: hidden;
        }
        
        input {
            flex: 1;
            padding: 12px 16px;
            border: none;
            background: transparent;
            color: var(--text-primary);
            font-size: 1rem;
            outline: none;
            font-family: inherit;
        }
        
        textarea {
            flex: 1;
            padding: 12px 16px;
            border: none;
            background: transparent;
            color: var(--text-primary);
            font-size: 1rem;
            outline: none;
            resize: none;
            overflow-y: hidden;
            height: 44px;
            max-height: 300px;
            font-family: inherit;
            line-height: 1.4;
            white-space: pre-wrap;
            word-wrap: break-word;
        }
        
        input::placeholder, textarea::placeholder {
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
            flex: 1;
            min-width: 0;
            max-width: 100%;
            width: 100%;
            box-sizing: border-box;
            transition: all 0.3s ease;
            resize: none;
            min-height: 40px;
            max-height: 120px;
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-width: thin;
            scrollbar-color: var(--accent-primary) transparent;
            border: none;
            background: transparent;
            color: var(--text-primary);
            font-family: inherit;
            font-size: 1rem;
            outline: none;
            word-wrap: break-word;
            white-space: pre-wrap;
        }
        
        .message-input.multiline {
            overflow-y: auto;
        }
        
        .message-input::-webkit-scrollbar {
            width: 6px;
        }
        
        .message-input::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .message-input::-webkit-scrollbar-thumb {
            background-color: var(--accent-primary);
            border-radius: 3px;
            border: 1px solid var(--accent-secondary);
        }
        
        .message-input::-webkit-scrollbar-thumb:hover {
            background-color: var(--accent-secondary);
        }
        
        textarea:focus {
            border: 1px solid var(--accent-primary);
            box-shadow: 0 0 10px rgba(118, 185, 0, 0.2);
        }
        
        .message-input.processing {
            background: linear-gradient(90deg, 
                var(--input-bg) 0%, 
                rgba(76, 175, 80, 0.1) 50%, 
                var(--input-bg) 100%);
            background-size: 200% 100%;
            animation: shimmer 2s ease-in-out infinite;
            font-style: italic;
        }
        
        @keyframes shimmer {
            0% { background-position: -200% 0; }
            100% { background-position: 200% 0; }
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
        
        /* Ensure all SVG icons preserve aspect ratio and don't deform */
        button svg,
        .input-menu-item svg,
        .dropdown-item svg {
            flex-shrink: 0;
            display: block;
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
        
        /* Test button (next to voice button) */
        .test-button {
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
        
        .test-button:hover {
            border-color: #4CAF50;
            color: #4CAF50;
            transform: translateY(-1px);
        }
        
        .test-button.testing {
            background-color: #4CAF50;
            border-color: #4CAF50;
            color: white;
            animation: pulse-testing 1.5s ease-in-out infinite;
        }
        
        @keyframes pulse-testing {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .test-button svg {
            width: 18px;
            height: 18px;
        }
        
        .test-button:disabled {
            opacity: 0.4;
            cursor: not-allowed;
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
        
        /* Close button - NO HOVER EFFECTS */
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
            font-size: 28px;
            line-height: 1;
            font-weight: 300;
            font-family: Arial, sans-serif;
            width: 40px;
            height: 40px;
            flex-shrink: 0;
        }
        
        .close-button:hover {
            /* EXPLICITLY DISABLED - Override global button:hover */
            background-color: transparent !important;
            color: var(--text-secondary) !important;
            transform: none !important;
        }
        
        .close-button svg {
            width: 20px;
            height: 20px;
        }
        
        /* Minimize button - NO HOVER EFFECTS */
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
            font-size: 28px;
            line-height: 0.5;
            font-weight: bold;
            font-family: Arial, sans-serif;
            width: 40px;
            height: 40px;
            flex-shrink: 0;
            transform: translateY(-10px);
        }
        
        .minimize-button:hover {
            /* EXPLICITLY DISABLED - Override global button:hover */
            background-color: transparent !important;
            color: var(--text-secondary) !important;
            transform: none !important;
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
        
        /* Hamburger menu button - NO HOVER EFFECTS */
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
            margin-right: 12px;
            font-size: 20px;
            line-height: 1;
            font-weight: normal;
        }
        
        .hamburger-button:hover {
            /* EXPLICITLY DISABLED - Override global button:hover */
            background-color: transparent !important;
            color: var(--text-secondary) !important;
            transform: none !important;
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
            background-color: rgba(118, 185, 0, 0.2);
            color: #000000;
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

        /* New styles for input menu */
        .input-wrapper {
            display: flex;
            gap: 12px;
            align-items: flex-end;
            padding: 12px 16px;
            background-color: var(--bg-primary);
            flex-shrink: 0;
            width: 100%;
            box-sizing: border-box;
        }

        .input-menu-container {
            position: relative;
            display: flex;
            align-items: center;
            flex-shrink: 0;
        }
        
        .input-plus-button {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background-color: var(--accent-primary);
            color: var(--bg-primary);
            border: none;
            cursor: pointer;
            font-size: 24px;
            font-weight: bold;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: background-color 0.2s ease, transform 0.2s ease;
            flex-shrink: 0;
            padding: 0;
            line-height: 1;
        }
        
        .input-plus-button:hover {
            background-color: var(--accent-secondary);
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(118, 185, 0, 0.3);
        }
        
        .input-plus-button:active {
            transform: scale(0.95);
        }

        .input-menu-dropdown {
            position: absolute;
            bottom: 100%;
            left: 0;
            background-color: var(--bg-secondary);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.5);
            min-width: 180px;
            z-index: 1000;
            opacity: 0;
            transform: translateY(10px);
            pointer-events: none;
            transition: opacity 0.2s ease, transform 0.2s ease;
            display: none;
            margin-bottom: 8px;
        }
        
        .input-menu-dropdown.show {
            display: block;
            opacity: 1;
            transform: translateY(0);
            pointer-events: all;
        }

        .input-menu-item {
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

        .input-menu-item:first-child {
            border-radius: 8px 8px 0 0;
        }

        .input-menu-item:last-child {
            border-radius: 0 0 8px 8px;
        }

        .input-menu-item:hover {
            background-color: rgba(118, 185, 0, 0.2);
            color: #000000;
        }

        .input-menu-item svg {
            width: 18px;
            height: 18px;
            flex-shrink: 0;
        }
        
        .checkbox-icon {
            margin-right: 4px;
        }
        
        .checkbox-icon .checkmark {
            stroke: var(--accent-secondary);
            stroke-width: 2;
        }
        
        .input-menu-item:hover .checkbox-icon .checkmark {
            stroke: #000000;
        }

        .input-menu-item span {
            flex: 1;
        }

        .voice-button-right {
            width: 40px;
            height: 40px;
            min-width: 40px;
            flex-shrink: 0;
            border-radius: 50%;
            background: none;
            border: none;
            color: var(--accent-primary);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s ease, transform 0.2s ease, opacity 0.2s ease;
            flex-shrink: 0;
            opacity: 1;
            font-size: 24px;
        }
        
        .voice-button-right:hover:not(:disabled) {
            color: var(--accent-secondary);
            transform: translateY(-2px);
            filter: brightness(1.2);
        }
        
        .voice-button-right:disabled {
            cursor: not-allowed;
            opacity: 0.7;
        }
        
        .voice-button-right svg {
            width: 24px;
            height: 24px;
            stroke: currentColor;
        }
    </style>
</head>
<body>
    <header>
        <button class="hamburger-button" id="hamburgerButton" title="Menu">☰</button>
        <h1>G-Assist</h1>
        <div class="header-buttons">
            <button class="minimize-button" id="minimizeButton" title="Minimize">_</button>
            <button class="close-button" id="closeButton" title="Close (or press Ctrl+Q)">×</button>
        </div>
        <div class="dropdown-menu" id="dropdownMenu">
            <button class="dropdown-item" id="settingsMenuItem">Settings</button>
            <button class="dropdown-item" id="exportMenuItem">Export</button>
            <div class="dropdown-divider"></div>
            <div class="dropdown-version">
                <span>Version 0.0.4</span>
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
          <div class="input-wrapper">
              <div class="input-menu-container">
                  <button type="button" class="input-plus-button" id="inputMenuButton" title="Options">+</button>
                  <div class="input-menu-dropdown" id="inputMenuDropdown">
                      <button type="button" class="input-menu-item" id="testButton" title="Load WAV file">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                              <polyline points="14 2 14 8 20 8"></polyline>
                              <path d="M12 18v-6"></path>
                              <path d="M9 15l3 3 3-3"></path>
                          </svg>
                          <span>Load WAV File</span>
                      </button>
                      <button type="button" class="input-menu-item" id="thinkingToggle" title="Toggle thinking mode">
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="18" height="18" class="checkbox-icon" id="thinkingCheckbox">
                              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                              <polyline points="9 11 12 14 22 4" class="checkmark" style="display: none;"></polyline>
                          </svg>
                          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                              <path d="M9.5 2c-1.82 0-3.53.5-5 1.35C2.99 4.07 2 5.8 2 7.75c0 2.07 1.13 3.87 2.81 4.86.06.38.16.75.29 1.10.36.97.96 1.84 1.73 2.53 0 .91.46 1.76 1.24 2.26.78.5 1.76.5 2.54 0 .78-.5 1.24-1.35 1.24-2.26.77-.69 1.37-1.56 1.73-2.53.13-.35.23-.72.29-1.10C15.87 11.62 17 9.82 17 7.75c0-1.95-.99-3.68-2.5-4.4C13.03 2.5 11.32 2 9.5 2zm0 1.5c1.48 0 2.87.41 4.06 1.13 1.06.64 1.94 1.66 1.94 3.12 0 1.58-.95 2.95-2.31 3.55l-.26.11-.04.28c-.03.24-.1.47-.19.69-.27.68-.73 1.29-1.32 1.75l-.35.27v.85c0 .36-.18.7-.5.9-.32.2-.73.2-1.05 0-.32-.2-.5-.54-.5-.9v-.85l-.35-.27c-.59-.46-1.05-1.07-1.32-1.75-.09-.22-.16-.45-.19-.69l-.04-.28-.26-.11C4.45 10.7 3.5 9.33 3.5 7.75c0-1.46.88-2.48 1.94-3.12C6.63 3.91 8.02 3.5 9.5 3.5z"></path>
                              <circle cx="9.5" cy="8" r="1"></circle>
                              <circle cx="12.5" cy="8" r="1"></circle>
                              <path d="M14.5 14c-.28 0-.5.22-.5.5s.22.5.5.5.5-.22.5-.5-.22-.5-.5-.5zm-10 0c-.28 0-.5.22-.5.5s.22.5.5.5.5-.22.5-.5-.22-.5-.5-.5z"></path>
                          </svg>
                          <span>Thinking</span>
                      </button>
                  </div>
              </div>
              <form class="input-area" id="messageForm">
                  <input type="file" id="testAudioInput" accept=".wav" style="display:none">
                  <textarea id="messageInput" placeholder="" autofocus class="message-input" rows="1"></textarea>
              </form>
              <button type="button" class="voice-button-right" id="voiceButtonRight" title="Voice recording" style="display: flex;">
                  <svg viewBox="0 0 24 24" fill="none" stroke="#76b900" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" width="24" height="24">
                      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path>
                      <path d="M19 10v2a7 7 0 0 1-14 0v-2"></path>
                      <line x1="12" y1="19" x2="12" y2="23"></line>
                      <line x1="8" y1="23" x2="16" y2="23"></line>
                  </svg>
              </button>
          </div>
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
            <button id="refreshMicsBtn" style="margin-top: 10px; width: 100%;">Refresh Microphones</button>
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
        console.log('SCRIPT TAG 1 STARTING - processWavDirect definition');
        
        // Process WAV using direct API - SIMPLIFIED WITH PROMISES
        window.processWavDirect = function(arrayBuffer, messageInput) {
            console.log('[DIRECT] Processing WAV...');
            
            var view = new DataView(arrayBuffer);
            var sampleRate = view.getUint32(24, true);
            var numChannels = view.getUint16(22, true);
            var bitsPerSample = view.getUint16(34, true);
            
            console.log('[DIRECT] ' + sampleRate + 'Hz, ' + numChannels + 'ch, ' + bitsPerSample + 'bit');
            
            var dataStart = 44;
            var dataSize = view.getUint32(40, true);
            var totalSamples = dataSize / (bitsPerSample / 8) / numChannels;
            
            var pcmFloat = [];
            for (var i = 0; i < totalSamples; i++) {
                var offset = dataStart + i * numChannels * (bitsPerSample / 8);
                var sample = 0;
                
                if (bitsPerSample === 16) {
                    sample = view.getInt16(offset, true) / 32768.0;
                    if (numChannels === 2 && offset + 2 < arrayBuffer.byteLength) {
                        var sample2 = view.getInt16(offset + 2, true) / 32768.0;
                        sample = (sample + sample2) / 2.0;
                    }
                }
                pcmFloat.push(sample);
            }
            
            console.log('[DIRECT] ' + pcmFloat.length + ' samples extracted');
            
            messageInput.value = '';
            
            // Send chunks sequentially using promise chain with proper timing
            var chunkSize = 700;
            var chunkId = 0;
            var chunkDurationMs = (chunkSize / sampleRate) * 1000;
            var promise = Promise.resolve();
            
            for (var i = 0; i < pcmFloat.length; i += chunkSize) {
                (function(startIdx) {
                    promise = promise.then(function() {
                        // Add delay to simulate real-time streaming at proper sample rate
                        return new Promise(function(resolve) {
                            setTimeout(function() {
                                var chunk = pcmFloat.slice(startIdx, startIdx + chunkSize);
                                chunkId++;
                                
                                var float32 = new Float32Array(chunk);
                                var bytes = new Uint8Array(float32.buffer);
                                var binary = '';
                                for (var j = 0; j < bytes.length; j++) {
                                    binary += String.fromCharCode(bytes[j]);
                                }
                                var base64 = btoa(binary);
                                
                                window.pywebview.api.send_audio_chunk(base64, chunkId, sampleRate).then(function(result) {
                                    if (result && result.text) {
                                        messageInput.value = result.text;
                                        messageInput.style.height = 'auto';
                                        messageInput.style.height = messageInput.scrollHeight + 'px';
                                        messageInput.scrollTop = messageInput.scrollHeight;
                                        console.log('[DIRECT] Chunk ' + chunkId + ' (' + chunkDurationMs.toFixed(1) + 'ms): "' + result.text + '"');
                                    }
                                });
                                
                                resolve();
                            }, chunkDurationMs);
                        });
                    });
                })(i);
            }
            
            return promise.then(function() {
                console.log('[DIRECT] Before STOP - messageInput.value: "' + messageInput.value + '"');
                // Store the last interim text to show immediately
                var lastInterimText = messageInput.value;
                return window.pywebview.api.send_audio_stop();
            }).then(function(finalResult) {
                var jsReceiveTime = Date.now();
                console.log('[DIRECT] JS received finalResult at ' + jsReceiveTime + ':', finalResult);
                if (finalResult && finalResult.final_text) {
                    console.log('[DIRECT] Setting messageInput.value to: "' + finalResult.final_text + '"');
                    messageInput.value = finalResult.final_text;
                    messageInput.style.height = 'auto';
                    messageInput.style.height = messageInput.scrollHeight + 'px';
                    var jsDisplayTime = Date.now();
                    console.log('[DIRECT] UI updated at ' + jsDisplayTime + ' (delay: ' + (jsDisplayTime - jsReceiveTime) + 'ms)');
                }
            });
        };
        
        // Global WAV file handler  
        window.handleWavFile = function(input) {
            var file = input.files[0];
                    if (!file) return;
                    
            console.log('[WAV] File selected:', file.name);
                    
                    if (!file.name.toLowerCase().endsWith('.wav')) {
                alert('Please select a WAV file');
                        return;
                    }
                    
            var messageInput = document.getElementById('messageInput');
            if (!messageInput) {
                console.error('messageInput not found');
                return;
            }
            
            var originalPlaceholder = messageInput.placeholder;
            messageInput.placeholder = 'Processing audio...';
                    messageInput.disabled = true;
            
            file.arrayBuffer().then(function(arrayBuffer) {
                return window.processWavDirect(arrayBuffer, messageInput);
            }).then(function() {
                console.log('[WAV] Processing complete');
                messageInput.disabled = false;
                        messageInput.placeholder = originalPlaceholder;
                messageInput.focus();
                input.value = '';
            }).catch(function(error) {
                console.error('[WAV] Error:', error);
                alert('Error processing WAV: ' + error.message);
                        messageInput.disabled = false;
                messageInput.placeholder = originalPlaceholder;
                        messageInput.focus();
                input.value = '';
            });
        };
        
        console.log('SCRIPT TAG 1 COMPLETED - handleWavFile defined');

    </script>
    <script>
        console.log('SCRIPT TAG 2 LOADED');
        window.thinkingEnabled = true;
        
        // Initialize checkbox state for thinking mode
        document.addEventListener('DOMContentLoaded', function() {
            var checkbox = document.getElementById('thinkingCheckbox');
            var thinkingBtn = document.getElementById('thinkingToggle');
            if (checkbox && window.thinkingEnabled) {
                var checkmark = checkbox.querySelector('.checkmark');
                if (checkmark) {
                    checkmark.style.display = 'block';
                }
                if (thinkingBtn) {
                    thinkingBtn.classList.add('active');
                }
            }
        });
        
        // Microphone enumeration function
        window.enumerateMicrophones = function() {
            console.log('Enumerate called');
            var sel = document.getElementById('microphoneSelect');
            var stat = document.getElementById('micStatus');
            var voiceBtn = document.getElementById('voiceButtonRight');
            
            if (!navigator.mediaDevices) {
                console.log('No mediaDevices');
                if (sel) sel.innerHTML = '<option>Not available</option>';
                if (stat) stat.textContent = 'Use WAV files instead';
                if (voiceBtn) {
                    voiceBtn.disabled = true;
                    voiceBtn.title = 'Microphone not available';
                }
                return;
            }
            
            navigator.mediaDevices.enumerateDevices().then(function(devices) {
                console.log('Got devices:', devices.length);
                var mics = [];
                for (var i = 0; i < devices.length; i++) {
                    if (devices[i].kind === 'audioinput') {
                        mics.push(devices[i]);
                    }
                }
                console.log('Mics:', mics.length);
                
                if (sel) {
                    sel.innerHTML = '';
                    if (mics.length === 0) {
                        sel.innerHTML = '<option>No mics found</option>';
                                        } else {
                        for (var j = 0; j < mics.length; j++) {
                            var opt = document.createElement('option');
                            opt.value = mics[j].deviceId;
                            opt.textContent = mics[j].label || ('Mic ' + (j+1));
                            sel.appendChild(opt);
                        }
                    }
                }
                
                if (stat) stat.textContent = mics.length + ' mic(s) found';
                
                // Disable voice button if no mics
                if (voiceBtn) {
                    if (mics.length === 0) {
                        voiceBtn.disabled = true;
                        voiceBtn.title = 'No microphones available - use WAV files instead';
                } else {
                        voiceBtn.disabled = false;
                        voiceBtn.title = 'Voice input';
                    }
                }
            }).catch(function(err) {
                console.error('Mic error:', err);
                if (sel) sel.innerHTML = '<option>Not available</option>';
                if (stat) stat.textContent = 'Use WAV files';
                if (voiceBtn) {
                    voiceBtn.disabled = true;
                    voiceBtn.title = 'Microphone error - use WAV files instead';
                }
            });
        };
        
        console.log('enumerateMicrophones defined');
            
            // Toggle thinking mode button handler
            window.toggleThinkingMode = function() {
                var btn = document.getElementById('thinkingToggle');
                var checkbox = document.getElementById('thinkingCheckbox');
                if (btn) {
                    btn.classList.toggle('active');
                    window.thinkingEnabled = btn.classList.contains('active');
                    btn.title = 'Thinking mode: ' + (window.thinkingEnabled ? 'ON' : 'OFF');
                    console.log('Thinking toggled:', window.thinkingEnabled);
                    
                    // Toggle checkmark visibility
                    if (checkbox) {
                        var checkmark = checkbox.querySelector('.checkmark');
                        if (checkmark) {
                            checkmark.style.display = window.thinkingEnabled ? 'block' : 'none';
                        }
                    }
                }
                var dropdown = document.getElementById('inputMenuDropdown');
                if (dropdown) {
                    dropdown.classList.remove('show');
                }
            };
            
            // Open settings panel
            window.openSettings = function() {
                var menu = document.getElementById('dropdownMenu');
                if (menu) menu.classList.remove('show');
                
                var pane = document.querySelector('.settings-pane');
                if (pane) pane.classList.remove('hidden');
                
                var backdrop = document.getElementById('settingsBackdrop');
                if (backdrop) backdrop.classList.remove('hidden');
            };
            
            // Close settings panel
            window.closeSettings = function() {
                var pane = document.querySelector('.settings-pane');
                if (pane) pane.classList.add('hidden');
                
                var backdrop = document.getElementById('settingsBackdrop');
                if (backdrop) backdrop.classList.add('hidden');
            };

            // Format response text with code blocks for think tags and JSON
            // Handles both complete and incomplete (streaming) text
            window.formatResponseText = function(text, isStreaming) {
                console.log('formatResponseText called, isStreaming:', isStreaming, 'text length:', text.length);
                var html = text;
                
                // Escape HTML special characters except for code blocks we'll add
                html = html.replace(/&/g, '&amp;')
                           .replace(/</g, '&lt;')
                           .replace(/>/g, '&gt;')
                           .replace(/"/g, '&quot;')
                           .replace(/'/g, '&#39;');
                
                console.log('After HTML escape, checking for think tags...');
                console.log('Contains &lt;think&gt;:', html.includes('&lt;think&gt;'));
                
                // Handle <think>...</think> blocks
                // First, handle complete blocks
                var completeMatches = 0;
                html = html.replace(/&lt;think&gt;([\\s\\S]*?)&lt;\\/think&gt;/g, function(match, content) {
                    completeMatches++;
                    console.log('Found complete think block #' + completeMatches);
                    return '<div class="thinking-bubble"><strong>💭 THINKING:</strong><pre>' + content + '</pre></div>';
                });
                
                console.log('Complete think blocks found:', completeMatches);
                
                // If streaming, handle incomplete <think> blocks (no closing tag yet)
                if (isStreaming) {
                    console.log('Checking for incomplete think blocks...');
                    html = html.replace(/(&lt;think&gt;)([\\s\\S]*?)$/g, function(match, openTag, content) {
                        // Only format if there's no closing tag after this
                        if (!content.includes('&lt;/think&gt;')) {
                            console.log('Found incomplete think block with content length:', content.length);
                            return '<div class="thinking-bubble thinking-active"><strong>💭 THINKING:</strong><pre>' + content + '<span class="cursor-blink">▌</span></pre></div>';
                        }
                        return match;
                    });
                }
                
                // Detect and wrap JSON objects/arrays in code blocks
                // Match {...} or [...]
                html = html.replace(/(\\{[\\\\s\\\\S]*?\\}|\\[[\\\\s\\\\S]*?\\])/g, function(match) {
                    // Only wrap if it looks like valid JSON (contains colons for objects or is an array)
                    if (match.includes(':') || match.startsWith('[')) {
                        return '<pre><code>' + match + '</code></pre>';
                    }
                    return match;
                });
                
                return html;
            };
            
            // Initialize UI
            function initializeUI() {
                console.log('=== initializeUI called ===');
                
                var messageForm = document.getElementById('messageForm');
                var messageInput = document.getElementById('messageInput');
                var messagesContainer = document.getElementById('messages');
                var dropdownMenu = document.getElementById('dropdownMenu');
                
                if (!messageForm || !messageInput || !messagesContainer) {
                    console.error('ERROR: Required elements not found');
                    return;
                }
                
                console.log('Core UI elements found');
                
                // Setup form submission
                var handleFormSubmit = function(e) {
                    if (e) {
                        e.preventDefault();
                    }
                    console.log('*** FORM SUBMITTED! ***');
                    var message = messageInput.value.trim();
                    if (!message) {
                        console.log('Empty message, ignoring');
                        return;
                    }
                    
                    console.log('Message submitted:', message);
                    messageInput.value = '';
                    messageInput.style.height = 'auto';  // Reset height to default
                    
                    // Add user message to chat
                    var msgDiv = document.createElement('div');
                    msgDiv.className = 'message user';
                    var contentDiv = document.createElement('div');
                    contentDiv.className = 'message-content user';
                    var sender = document.createElement('span');
                    sender.className = 'sender';
                    sender.textContent = 'You: ';
                    var text = document.createElement('span');
                    text.className = 'text';
                    text.textContent = message;
                    contentDiv.appendChild(sender);
                    contentDiv.appendChild(text);
                    msgDiv.appendChild(contentDiv);
                    messagesContainer.appendChild(msgDiv);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    
                    // Add typing indicator
                    var typingDiv = document.createElement('div');
                    typingDiv.className = 'message assistant';
                    typingDiv.id = 'typing-indicator-message';
                    var typingContent = document.createElement('div');
                    typingContent.className = 'message-content assistant';
                    var typingSender = document.createElement('span');
                    typingSender.className = 'sender';
                    typingSender.textContent = 'G-Assist: ';
                    var typingIndicator = document.createElement('div');
                    typingIndicator.className = 'typing-indicator';
                    typingIndicator.innerHTML = '<span></span><span></span><span></span>';
                    typingContent.appendChild(typingSender);
                    typingContent.appendChild(typingIndicator);
                    typingDiv.appendChild(typingContent);
                    messagesContainer.appendChild(typingDiv);
                    messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    
                    // Try to send via streaming API
                    if (window.pywebview && window.pywebview.api) {
                        console.log('Starting streaming API call...');
                        
                        // Start the streaming request first
                        window.pywebview.api.send_message_stream_start(message, '', '', window.thinkingEnabled || false).then(function(result) {
                            console.log('Stream started:', result);
                            
                            // Start polling for updates immediately
                            var lastText = '';
                            var respDiv = null;
                            var respText = null;
                            var respContent = null;
                            var typingRemoved = false;
                            var ttftDisplayed = false;
                            var ttftValue = null;
                            
                            var pollInterval = setInterval(function() {
                                window.pywebview.api.get_stream_update().then(function(update) {
                                    // Debug log the update
                                    console.log('[DEBUG] Update received:', {
                                        hasText: !!update.text,
                                        textLength: update.text ? update.text.length : 0,
                                        ttft: update.ttft,
                                        done: update.done
                                    });
                                    
                                    // Store TTFT when it arrives
                                    if (update && update.ttft !== null && update.ttft !== undefined) {
                                        ttftValue = update.ttft;
                                        console.log('[TTFT] TTFT value stored:', ttftValue, 'seconds');
                                    }
                                    
                                    // If we have text and haven't created the response div yet
                                    if (update && update.text && !respDiv) {
                                        console.log('First text received, removing typing indicator');
                                        
                                        // Remove typing indicator on first text
                                        var typingMsg = document.getElementById('typing-indicator-message');
                                        if (typingMsg) {
                                            typingMsg.remove();
                                            typingRemoved = true;
                                        }
                                        
                                        // Create response div
                                        respDiv = document.createElement('div');
                                        respDiv.className = 'message assistant';
                                        respDiv.id = 'streaming-response-message';
                                        respContent = document.createElement('div');
                                        respContent.className = 'message-content assistant';
                                        var respSender = document.createElement('span');
                                        respSender.className = 'sender';
                                        respSender.textContent = 'G-Assist: ';
                                        respText = document.createElement('span');
                                        respText.className = 'text';
                                        respText.innerHTML = '';
                                        respContent.appendChild(respSender);
                                        respContent.appendChild(respText);
                                        respDiv.appendChild(respContent);
                                        messagesContainer.appendChild(respDiv);
                                    }
                                    
                                    // Update text if we have new content
                                    if (update && update.text && update.text !== lastText && respText) {
                                        // Debug: Check for think tags
                                        if (update.text.includes('<think>') || update.text.includes('&lt;think&gt;')) {
                                            console.log('DEBUG: Found think tag in response!');
                                            console.log('Raw text sample:', update.text.substring(0, 200));
                                        }
                                        
                                        // Update with new text immediately - pass true for isStreaming
                                        var formattedHtml = window.formatResponseText(update.text, true);
                                        respText.innerHTML = formattedHtml;
                                        lastText = update.text;
                                        
                                        // Scroll to bottom
                                        requestAnimationFrame(function() {
                                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                        });
                                    }
                                    
                                    // Check if done
                                    if (update && update.done) {
                                        clearInterval(pollInterval);
                                        console.log('Streaming complete');
                                        console.log('Final text:', update.text);
                                        
                                        // Make sure typing indicator is removed
                                        if (!typingRemoved) {
                                            var typingMsg = document.getElementById('typing-indicator-message');
                                            if (typingMsg) {
                                                typingMsg.remove();
                                            }
                                        }
                                        
                                        // Final format without streaming flag for clean finish
                                        if (respText && update.text) {
                                            var finalHtml = window.formatResponseText(update.text, false);
                                            respText.innerHTML = finalHtml;
                                            
                                            console.log('[TTFT] Attempting to display TTFT...');
                                            console.log('[TTFT] ttftValue:', ttftValue);
                                            console.log('[TTFT] respContent:', respContent);
                                            console.log('[TTFT] ttftDisplayed:', ttftDisplayed);
                                            
                                            // Add TTFT metric display
                                            if (ttftValue !== null && respContent && !ttftDisplayed) {
                                                console.log('[TTFT] Creating TTFT div...');
                                                var ttftDiv = document.createElement('div');
                                                ttftDiv.className = 'ttft-metric';
                                                ttftDiv.textContent = 'TTFT: ' + ttftValue.toFixed(3) + 's';
                                                respContent.appendChild(ttftDiv);
                                                ttftDisplayed = true;
                                                console.log('[TTFT] TTFT div created and appended:', ttftValue.toFixed(3) + 's');
                                            } else {
                                                console.log('[TTFT] TTFT not displayed. Reasons:');
                                                console.log('  - ttftValue is null:', ttftValue === null);
                                                console.log('  - respContent is null:', respContent === null);
                                                console.log('  - already displayed:', ttftDisplayed);
                                            }
                                            
                                            requestAnimationFrame(function() {
                                                messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                            });
                                        }
                                    }
                                    
                                    // Check for errors
                                    if (update && update.error) {
                                        clearInterval(pollInterval);
                                        console.error('Streaming error:', update.error);
                                        
                                        // Remove typing indicator
                                        var typingMsg = document.getElementById('typing-indicator-message');
                                        if (typingMsg) {
                                            typingMsg.remove();
                                        }
                                        
                                        // Show error
                                        if (respText) {
                                            respText.textContent = 'Error: ' + update.error;
                                        }
                                    }
                                }).catch(function(err) {
                                    console.error('Poll error:', err);
                                });
                            }, 50); // Poll every 50ms for very responsive updates
                            
                        }).catch(function(err) {
                            console.error('Stream start error:', err);
                            
                            // Remove typing indicator on error
                            var typingMsg = document.getElementById('typing-indicator-message');
                            if (typingMsg) {
                                typingMsg.remove();
                            }
                        });
                    }
                };
                
                messageForm.onsubmit = handleFormSubmit;
                
                console.log('About to attach click event listener...');
                
                // Centralized event delegation for clicks (removed duplicate onclick handlers)
                document.addEventListener('click', function(evt) {
                    console.log('CLICK EVENT FIRED on:', evt.target);
                    var originalTarget = evt.target;
                    var target = evt.target;
                    
                    // Check if click is outside dropdown menu and close it
                    var dropdownMenu = document.getElementById('dropdownMenu');
                    var hamburgerButton = document.getElementById('hamburgerButton');
                    if (dropdownMenu && dropdownMenu.classList.contains('show')) {
                        if (!dropdownMenu.contains(originalTarget) && !hamburgerButton.contains(originalTarget)) {
                            dropdownMenu.classList.remove('show');
                            console.log('Closed dropdown menu (clicked outside)');
                        }
                    }
                    
                    // Check if click is outside input menu dropdown and close it
                    var inputMenuDropdown = document.getElementById('inputMenuDropdown');
                    var inputMenuButton = document.getElementById('inputMenuButton');
                    if (inputMenuDropdown && inputMenuDropdown.classList.contains('show')) {
                        if (!inputMenuDropdown.contains(originalTarget) && !inputMenuButton.contains(originalTarget)) {
                            inputMenuDropdown.classList.remove('show');
                            console.log('Closed input menu (clicked outside)');
                        }
                    }
                    
                    // Climb up to button if inner icon/text clicked
                    if (target && target.closest) { 
                        var closestButton = target.closest('button');
                        var closestBackdrop = target.closest('.settings-backdrop');
                        target = closestButton || closestBackdrop;
                    }
                    
                    if (!target) return;
                    
                    console.log('Button clicked:', target.id || target.className);
                    
                    // TEST - Simple alert for ANY button
                    if (target.tagName === 'BUTTON') {
                        console.log('BUTTON ELEMENT DETECTED! ID=' + target.id);
                    }
                    
                    // Header
                    if (target.id === 'hamburgerButton') {
                        console.log('Hamburger button handler triggered');
                        if (dropdownMenu) { 
                            dropdownMenu.classList.toggle('show'); 
                            console.log('Dropdown toggled');
                        }
                        return;
                    }
                    if (target.id === 'minimizeButton') {
                        if (window.pywebview && window.pywebview.api) { window.pywebview.api.minimize_app(); }
                        return;
                    }
                    if (target.id === 'closeButton') {
                        if (window.pywebview && window.pywebview.api) { window.pywebview.api.close_app(); } else { window.close(); }
                        return;
                    }
                    if (target.id === 'settingsMenuItem') {
                        window.openSettings();
                        return;
                    }
                    if (target.id === 'exportMenuItem') {
                        // Close dropdown menu first
                        if (dropdownMenu) { dropdownMenu.classList.remove('show'); }
                        // Export chat functionality placeholder
                        alert('Export functionality - to be implemented');
                        return;
                    }
                    if (target.id === 'inputMenuButton') {
                        var dd = document.getElementById('inputMenuDropdown');
                        if (dd) dd.classList.toggle('show');
                        return;
                    }
                    if (target.id === 'testButton') {
                        var finput = document.getElementById('testAudioInput');
                        if (finput) finput.click();
                        var dd2 = document.getElementById('inputMenuDropdown');
                        if (dd2) dd2.classList.remove('show');
                        return;
                    }
                    if (target.id === 'thinkingToggle') {
                        window.toggleThinkingMode();
                        return;
                    }
                    if (target.id === 'voiceButtonRight') {
                        alert('Voice recording disabled - use WAV files');
                        return;
                    }
                    if (target.id === 'refreshMicsBtn') {
                        if (window.enumerateMicrophones) window.enumerateMicrophones();
                        return;
                    }
                    if (target.classList && target.classList.contains('settings-backdrop')) {
                        window.closeSettings();
                        return;
                    }
                });
                
                // Ensure Enter submits the message
                messageInput.onkeydown = function(e) {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleFormSubmit();
                    }
                };
                
                // Enumerate microphones on load
                setTimeout(function() {
                    console.log('Calling enumerateMicrophones on load...');
                    window.enumerateMicrophones();
                }, 500);
                
                // Wire handlers for file input and input menu
                var fileInput = document.getElementById('testAudioInput');
                var voiceBtnRight = document.getElementById('voiceButtonRight');
                
                if (fileInput) {
                    fileInput.onchange = function() { window.handleWavFile(fileInput); };
                }
                
                // Auto-grow and toggle mic/send visibility
                if (messageInput) {
                    messageInput.oninput = function(){
                        var el = messageInput; 
                        el.style.height='auto'; 
                        el.style.height=Math.min(el.scrollHeight,120)+'px';
                        // Keep mic button visible at all times
                    };
                }

                console.log('=== initializeUI COMPLETED ===');
            }
            
            // Run initialization when DOM is ready
            console.log('Document readyState:', document.readyState);
            if (document.readyState === 'loading') {
                console.log('Waiting for DOMContentLoaded...');
                document.addEventListener('DOMContentLoaded', function() {
                    console.log('DOMContentLoaded fired');
                    initializeUI();
                });
            } else {
                console.log('DOM already loaded, calling initializeUI immediately');
                initializeUI();
            }

    </script>
    <script>
        console.log('SCRIPT TAG 2 INITIALIZATION COMPLETE');
    </script>
</body>
</html>
'''
    return html

def get_splash_html():
    """Generate splash screen HTML"""
    return '''
<!DOCTYPE html>
<html>
<head>
    <style>
        body {
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #0a0a0f 0%, #1a1a2e 100%);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            color: #76b900;
        }
        .splash-container {
            text-align: center;
            animation: fadeIn 0.5s ease-in;
        }
        .logo {
            font-size: 48px;
            font-weight: bold;
            margin-bottom: 20px;
            text-shadow: 0 0 20px rgba(118, 185, 0, 0.5);
        }
        .message {
            font-size: 18px;
            color: #ffffff;
            margin-bottom: 30px;
        }
        .spinner {
            width: 50px;
            height: 50px;
            margin: 0 auto;
            border: 4px solid rgba(118, 185, 0, 0.2);
            border-top: 4px solid #76b900;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        .version {
            margin-top: 20px;
            font-size: 12px;
            color: #666;
        }
    </style>
</head>
<body>
    <div class="splash-container">
        <div class="logo">G-ASSIST</div>
        <div class="message">Launching G-Assist...</div>
        <div class="spinner"></div>
        <div class="version">Version 0.0.4</div>
    </div>
</body>
</html>
'''

def main():
    """Main entry point - Desktop only with direct API"""
    try:
        import webview
    except ImportError:
        print("Error: pywebview not installed")
        print("Install with: pip install pywebview")
        sys.exit(1)
    
    logger.info("Starting G-Assist Desktop (Direct API mode)")
    logger.info(f"Log file: {log_file}")
    
    # Create splash screen
    splash = webview.create_window(
        'G-Assist',
        html=get_splash_html(),
        width=400,
        height=300,
        frameless=True,
        on_top=True
    )
    
    # Create API
    api = DesktopAPI()
    
    # Create main window (hidden initially)
    window = webview.create_window(
        'G-Assist Desktop',
        html=get_html(),
        width=520,
        height=932,
        resizable=True,
        frameless=True,
        min_size=(400, 600),
        background_color='#0a0a0f',
        js_api=api,  # Direct Python API!
        hidden=True
    )
    api.window = window
    
    # Function to handle window loading
    def on_loaded():
        logger.info("Main window loaded")
        try:
            # Try to evaluate JavaScript to confirm it's working
            result = window.evaluate_js('console.log("PYTHON: JavaScript is working!"); "test";')
            logger.info(f"JS eval result: {result}")
        except Exception as e:
            logger.error(f"JS eval failed: {e}")
        
        # Close splash and show main window
        import time
        time.sleep(0.5)  # Brief delay for smooth transition
        splash.destroy()
        window.show()
    
    window.events.loaded += on_loaded
    
    logger.info("Window created, starting...")
    webview.start(debug=False)

if __name__ == "__main__":
    main()

