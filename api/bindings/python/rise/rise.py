"""
G-Assist (RISE) Python Binding Module

This module provides a Python interface to the RISE (Runtime Inference System Engine) API.
It handles communication with the RISE backend through a DLL/shared library interface,
manages asynchronous callbacks, and provides a simplified interface for sending commands
and receiving responses.

The module includes:
- Content type enumerations for RISE communication
- Callback handling for asynchronous responses
- Progress tracking for downloads and installations
- CTypes structures for C/C++ interop
- Core functionality for RISE client registration and command sending

Dependencies:
    - ctypes: For C/C++ interoperability
    - tqdm: For progress bar visualization
    - json: For command serialization
"""

import ctypes
from enum import IntEnum
import os
import time
import sys
import json
from tqdm import tqdm
from typing import Optional, Dict, Any

# Global variables for state management
global nvapi
global callback_settings
callback = None
response = ''
chart = ''
response_done = False
ready = False
progress_bar = None


class NV_RISE_CONTENT_TYPE(IntEnum):
    """
    Enumeration of content types supported by the RISE API.
    
    These types determine how the content should be processed and displayed:
    - TEXT: Standard text communication
    - GRAPH: Graphical content
    - CUSTOM_BEHAVIOR: Special behavior handlers
    - INSTALLING: Installation status
    - PROGRESS_UPDATE: Progress information
    - READY: System ready status
    - DOWNLOAD_REQUEST: Download initiation
    - RESERVED: Reserved for experimental features (e.g., streaming ASR PoC)
    """
    NV_RISE_CONTENT_TYPE_INVALID = 0
    NV_RISE_CONTENT_TYPE_TEXT = 1
    NV_RISE_CONTENT_TYPE_GRAPH = 2
    NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR = 3
    NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR_RESULT = 4
    NV_RISE_CONTENT_TYPE_INSTALLING = 5
    NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE = 6
    NV_RISE_CONTENT_TYPE_READY = 7
    NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST = 8
    NV_RISE_CONTENT_TYPE_UPDATE_INFO = 9
    NV_RISE_CONTENT_TYPE_RESERVED = 10  # Reserved for experimental features (streaming ASR PoC)


class NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1(ctypes.Structure):
    """Base structure for callback settings."""
    _fields_ = [("pCallbackParam", ctypes.c_void_p),
                ("rsvd", ctypes.c_uint8 * 64)]


class NV_RISE_CALLBACK_DATA_V1(ctypes.Structure):
    """Structure containing callback data from RISE."""
    _fields_ = [("super", NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1),
                ("contentType", ctypes.c_int),
                ("content", ctypes.c_char * 4096),
                ("completed", ctypes.c_int)]


class NV_REQUEST_RISE_SETTINGS_V1(ctypes.Structure):
    """Structure for RISE request settings."""
    _fields_ = [("version", ctypes.c_int),
                ("contentType", ctypes.c_int),
                ("content", ctypes.c_char * 4096),
                ("completed", ctypes.c_uint8),
                ("reserved", ctypes.c_uint8 * 32)]


# Define callback function type
NV_RISE_CALLBACK_V1 = ctypes.CFUNCTYPE(
    None, ctypes.POINTER(NV_RISE_CALLBACK_DATA_V1))


class NV_RISE_CALLBACK_SETTINGS_V1(ctypes.Structure):
    """Structure for RISE callback settings configuration."""
    _fields_ = [("version", ctypes.c_int),
                ("super", NV_CLIENT_CALLBACK_SETTINGS_SUPER_V1),
                ("callback", NV_RISE_CALLBACK_V1),
                ("reserved", ctypes.c_uint8 * 32)]


def base_function_callback(data_ptr: ctypes.POINTER(NV_RISE_CALLBACK_DATA_V1)) -> None:
    """
    Primary callback function for handling RISE responses.

    This function processes various types of responses from RISE including ready status,
    text responses, download requests, and progress updates. It manages the global state
    and progress bar updates.

    Args:
        data_ptr: Pointer to the callback data structure containing response information

    Global State:
        response: Accumulates text responses
        response_done: Flags when a response is complete
        ready: Indicates RISE system readiness
        progress_bar: Manages download/installation progress visualization
    """
    global response, response_done, ready, progress_bar, chart

    data = data_ptr.contents
    if data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_READY:
        if data.completed == 1:
           ready = True
           print('RISE is ready')
           if progress_bar is not None:
               progress_bar.close()
           return

    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT:
        chunk = data.content.decode('utf-8')
        # For text responses: accumulate all chunks
        if chunk:
            response += chunk  # APPEND chunks, don't replace
        print(f"[Callback] Received TEXT chunk: '{chunk}' (completed={data.completed})", flush=True)
        if data.completed == 1:
            response_done = True
    
    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR:
        chunk = data.content.decode('utf-8')
        response += chunk
        print(f"[Callback] Received CUSTOM_BEHAVIOR chunk: '{chunk}' (completed={data.completed})", flush=True)
        if data.completed == 1:
            response_done = True
    
    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_CUSTOM_BEHAVIOR_RESULT:
        chunk = data.content.decode('utf-8')
        response += chunk
        print(f"[Callback] Received CUSTOM_BEHAVIOR_RESULT chunk: '{chunk}' (completed={data.completed})", flush=True)
        if data.completed == 1:
            response_done = True
    
    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_GRAPH:
        chart += data.content.decode('utf-8')

        if data.completed == 1:
            response_done = True

    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST:
        intiate_rise_install()
        progress_bar = tqdm(total=100, desc="Downloading")

    elif data.contentType == NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_PROGRESS_UPDATE:
        data_content = data.content.decode('utf-8')
        if progress_bar is None:
            progress_bar = tqdm(total=100, desc="Progress")
        if data_content.isdigit():
            progress_bar.n = int(data_content)
            progress_bar.refresh()
        else:
            progress_bar.close()
            print(data_content)


# Initialize DLL/shared library path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LIB_PATH = os.path.join(SCRIPT_DIR, "python_binding.dll")
try:
    nvapi = ctypes.CDLL(LIB_PATH)
except OSError as e:
    if "vcruntime" in str(e).lower() or "msvcp" in str(e).lower() or "cannot load" in str(e).lower():
        print("\n❌ Missing Visual C++ Redistributable (x64)")
        print("Download and install it from:")
        print("https://aka.ms/vs/17/release/vc_redist.x64.exe\n")
        sys.exit(1)
    else:
        raise  # re-raise unexpected errors
    
# Configure API function signatures
nvapi.register_rise_callback.argtypes = [ctypes.POINTER(NV_RISE_CALLBACK_SETTINGS_V1)]
nvapi.register_rise_callback.restype = ctypes.c_int
nvapi.request_rise.argtypes = [ctypes.POINTER(NV_REQUEST_RISE_SETTINGS_V1)]
nvapi.request_rise.restype = ctypes.c_int

callback_settings = NV_RISE_CALLBACK_SETTINGS_V1()


def register_rise_client() -> None:
    """
    Register the client with the RISE service.

    Initializes the connection to RISE and sets up the callback mechanism.
    Waits until RISE signals ready status before returning.

    Raises:
        AttributeError: If there's an error accessing the RISE API
    """
    global nvapi, callback_settings, callback, ready

    try:
        callback_settings.callback = NV_RISE_CALLBACK_V1(base_function_callback)
        callback_settings.version = ctypes.sizeof(NV_RISE_CALLBACK_SETTINGS_V1) | (1 << 16)

        ret = nvapi.register_rise_callback(ctypes.byref(callback_settings))
        if ret != 0:
            print('Registration Failed')
            return

        while not ready:
            time.sleep(1)

    except AttributeError as e:
        print(f"An error occurred: {e}")


def send_rise_command(command: str, assistant_identifier: str = '', custom_system_prompt: str = '', thinking_enabled: bool = False) -> Optional[dict]:
    """
    Send a command to RISE and wait for the response.

    Formats the command as a JSON object with a prompt, context, and client_config,
    sends it to RISE, and waits for the complete response.

    Args:
        command: The text command to send to RISE
        assistant_identifier: Optional assistant identifier for client_config
        custom_system_prompt: Optional custom system prompt for client_config
        thinking_enabled: Optional flag to enable thinking mode (adds <think> tags)

    Returns:
        Optional[dict]: The response from RISE, or None if an error occurs

    Raises:
        AttributeError: If there's an error accessing the RISE API
    """
    global nvapi, response_done, response, chart

    try:
        command_obj = {
            'prompt': command,
            'context_assist': {},
            'client_config': {}
        }

        if (assistant_identifier != ''): 
            command_obj['client_config']['assistant_identifier'] = assistant_identifier

        if(custom_system_prompt != ''):
            command_obj['client_config']['custom_system_prompt'] = custom_system_prompt
        
        # Add thinking_enabled to client_config
        command_obj['client_config']['thinking_enabled'] = thinking_enabled

        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.content = json.dumps(command_obj).encode('utf-8')
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT
        content.version = ctypes.sizeof(NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 1

        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'Send RISE command failed with {ret}')
            return None

        while not response_done:
            time.sleep(1)

        response_done = False
        completed_response = response
        completed_chart = chart
        response = ''
        chart = ''
        return {'completed_response': completed_response,'completed_chart': completed_chart}

    except AttributeError as e:
        print(f"An error occurred: {e}")
        return None


def send_audio_chunk(audio_base64: str, chunk_id: int, sample_rate: int = 16000) -> Optional[dict]:
    """
    Send an audio chunk to the engine for streaming ASR (PoC).
    
    Uses NV_RISE_CONTENT_TYPE_RESERVED with base64-encoded audio data.
    Content format: "<chunk_id>:<sample_rate>:<base64_pcm_data>"
    
    Args:
        audio_base64: Base64-encoded PCM audio data
        chunk_id: Sequential chunk number
        sample_rate: Sample rate of the audio (Hz)
        
    Returns:
        Optional[dict]: The response from RISE (may contain partial ASR result)
    """
    global nvapi, response_done, response
    
    try:
        # Format: "CHUNK:<id>:<sample_rate>:<base64_data>"
        payload = f"CHUNK:{chunk_id}:{sample_rate}:{audio_base64}"
        
        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.content = payload.encode('utf-8')
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT
        content.version = ctypes.sizeof(NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 0  # Not completed - more chunks coming
        
        print(f'[ASR_POC] Sending chunk {chunk_id} via nvapi.request_rise()...', flush=True)
        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'[ASR_POC] Send audio chunk {chunk_id} failed with error {ret}', flush=True)
            return None
        
        print(f'[ASR_POC] Chunk {chunk_id} sent successfully, waiting for response...', flush=True)
        
        # Wait for response from engine/SURA (no timeout - wait as long as needed)
        # Engine blocks on SURA's response, so we must wait for full round-trip
        wait_start = time.time()
        while not response_done:
            time.sleep(0.01)
            elapsed = time.time() - wait_start
            if elapsed > 5.0 and int(elapsed) % 5 == 0:  # Log every 5 seconds if waiting too long
                print(f'[ASR_POC] Still waiting for chunk {chunk_id} response... ({elapsed:.1f}s)', flush=True)
        
        wait_time = time.time() - wait_start
        
        response_done = False
        chunk_response = response
        response = ''
        
        response_preview = chunk_response[:100] if chunk_response else '(empty)'
        print(f'[ASR_POC] Chunk {chunk_id} response received after {wait_time:.3f}s: "{response_preview}"', flush=True)
        
        return {'chunk_response': chunk_response}
        
    except Exception as e:
        print(f"[ASR_POC] Error sending audio chunk: {e}")
        return None


def send_audio_stop() -> Optional[dict]:
    """
    Send stop signal to finalize audio recording session.
    
    Uses NV_RISE_CONTENT_TYPE_RESERVED with "STOP:" content.
    
    Returns:
        Optional[dict]: The final response from RISE
    """
    global nvapi, response_done, response
    
    try:
        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.content = b"STOP:"
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_TEXT
        content.version = ctypes.sizeof(NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 0
        
        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'[ASR_POC] Send audio stop failed with {ret}')
            return None
        
        # Wait for final response (increased timeout for final transcription)
        # Note: Engine sends multiple callback batches for STOP:
        # 1. Empty ACKs (first response_done)
        # 2. ASR_INTERIM with full transcription
        # 3. ASR_FINAL with full transcription
        # We MUST wait for ASR_FINAL specifically!
        timeout = 10.0  # Longer timeout for final transcription
        start_time = time.time()
        max_wait_after_final = 0.5  # Wait 500ms after receiving ASR_FINAL to ensure no more updates
        
        last_final_time = None
        final_response = ''
        interim_response = ''
        
        while (time.time() - start_time) < timeout:
            if response_done:
                # Got a completed message - check if it has text
                if response:
                    if 'ASR_FINAL:' in response:
                        # Got the FINAL transcription - this is what we want!
                        final_response = response
                        last_final_time = time.time()
                        print(f"[ASR_POC] Got ASR_FINAL text: {response[:100]}...", flush=True)
                    elif 'ASR_INTERIM:' in response:
                        # Got interim - keep it as backup but keep waiting for FINAL
                        interim_response = response
                        print(f"[ASR_POC] Got ASR_INTERIM text (waiting for FINAL): {response[:100]}...", flush=True)
                
                # Reset for next batch
                response_done = False
            
            # If we got ASR_FINAL and waited long enough, we're done
            if last_final_time and (time.time() - last_final_time) > max_wait_after_final:
                break
            
            time.sleep(0.01)
        
        # Use final response if available, otherwise fall back to interim
        result = final_response if final_response else interim_response
        
        response = ''  # Clear for next request
        
        return {'final_response': result}
        
    except Exception as e:
        print(f"[ASR_POC] Error sending audio stop: {e}")
        return None


def intiate_rise_install() -> None:
    """
    Initiate the RISE installation process.

    Sends a download request to begin the RISE installation.
    Progress is tracked through the callback mechanism.

    Raises:
        AttributeError: If there's an error accessing the RISE API
    """
    global nvapi

    try:
        content = NV_REQUEST_RISE_SETTINGS_V1()
        content.contentType = NV_RISE_CONTENT_TYPE.NV_RISE_CONTENT_TYPE_DOWNLOAD_REQUEST
        content.version = ctypes.sizeof(NV_REQUEST_RISE_SETTINGS_V1) | (1 << 16)
        content.completed = 1
        
        ret = nvapi.request_rise(content)
        if ret != 0:
            print(f'Send RISE INSTALL failed with {ret}')
            return

    except AttributeError as e:
        print(f"An error occurred: {e}")
