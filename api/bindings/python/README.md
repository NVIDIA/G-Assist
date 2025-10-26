# G-Assist Python Binding

Transform your Python applications into powerful AI-enabled experiences with G-Assist! This binding makes it incredibly easy to integrate G-Assist's capabilities into your Python projects. We've abstracted away the complexity of state machines and callbacks, making everything beautifully synchronous and straightforward.

## What Can It Do?
- Send commands to G-Assist and receive responses with just a few lines of code
- Synchronous, blocking calls for easier programming
- Simple, clean API that gets out of your way
- Easy integration into any Python project

## Before You Start
Make sure you have:
- Python 3.x installed on your computer
- pip package manager
- G-Assist core services installed on your system
- Visual C++ Build Tools (Option 1 or 2 below)
- NVIDIA NVAPI header files from [NVIDIA GitHub](https://github.com/NVIDIA/nvapi) (if you choose to build the project)
  - Files should be placed in the [./api/bindings/python/](./api/bindings/python/) directory  

### Required Downloads
1. **Option 1: Visual Studio (Recommended for Developers)**
   - Download [Visual Studio Community](https://visualstudio.microsoft.com/vs/community/)
   - During installation, select:
     - "Desktop development with C++"
     - "Python development" (optional, but recommended)
   
   **Tip**: This option is best if you plan to do any development work

2. **Option 2: Visual C++ Runtime Only**
   - Download the x64 version from Microsoft: [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
   - Install it before running any G-Assist Python applications
   - Restart your computer if needed

   **Tip**: Choose this option if you only need to run the application

3. **Python Requirements**
```bash
pip install -r requirements.txt
```

**Tip**: The "Could not find module" error often means Visual C++ components are missing or need to be updated.

## Getting Started

### Step 1: Install the Package
From the directory where the setup.py exists, run:
```bash
pip install .
```

### Step 2: Basic Usage
Here's all you need to get started:
```python
from rise import rise

# Register your client
rise.register_rise_client()

# Send a command and get response
response = rise.send_rise_command('What is my GPU?')

# Print the response
print(response)
"""
Response: Your GPU is an NVIDIA GeForce RTX 5090 with a Driver version of 572.83.
"""
```

## Interactive Chat Example

Want to build a more interactive experience? Check out this complete chat application that includes animated thinking bubbles and colored output!

```python
from rise import rise
import time
from colorama import Fore, Style, init  # type: ignore
import sys
import threading

def thinking_bubble(stop_event):
    while not stop_event.is_set():
        for _ in range(3):
            if stop_event.is_set():
                break
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write('\b\b\b   \b\b\b')  # Erase the dots

def main():
    rise.register_rise_client()

    while True:
        # Get user input
        user_prompt = input(Fore.CYAN + "ME: " + Style.RESET_ALL)
        stop_event = threading.Event()  # Event to signal the thinking bubble to stop
        thinking_thread = threading.Thread(
            target=thinking_bubble, args=(stop_event,))
        thinking_thread.start()  # Start the thinking dots in a separate thread
        response = rise.send_rise_command(user_prompt)
        stop_event.set()  # Signal the thinking thread to stop
        thinking_thread.join()  # Wait for the thread to finish
        print(Fore.YELLOW + "RISE: " + response)

if __name__ == "__main__":
    main()
```

## G-Assist Desktop GUI

Experience G-Assist through our modern, native desktop application! This GUI connects directly to the Python bindings for maximum performance and real-time streaming responses.

### Features
- Modern, dark-themed interface with NVIDIA branding
- **Real-time streaming responses** - see text as it's generated
- **Thinking mode** with animated bubbles showing AI reasoning
- **Voice input support** via WAV file upload
- **TTFT (Time To First Token) metrics** displayed for every response
- **Native desktop experience** using pywebview (no browser required)
- Chat history export to JSON
- Customizable settings (microphone, system prompts)

### Quick Start

#### Development Mode
```bash
# Install required packages
pip install .

# Launch the application
python rise-gui-desktop-direct.py
```

#### Building Standalone Executable
```bash
# Build the executable (includes all dependencies)
python build_desktop_direct.py

# Run the built application
.\dist_direct\G-Assist-Direct.exe
```

### Architecture

The desktop GUI uses a **direct binding architecture** for optimal performance:

```
┌─────────────────────────────┐
│  rise-gui-desktop-direct.py │  ← Main Application
│  (Python + HTML/CSS/JS)     │
└──────────────┬──────────────┘
               │ Direct API calls
               ↓
┌─────────────────────────────┐
│   rise.py (Python Binding)  │  ← Python Wrapper
└──────────────┬──────────────┘
               │ ctypes
               ↓
┌─────────────────────────────┐
│  python_binding.dll (C++)   │  ← Native Bridge
└──────────────┬──────────────┘
               │ NVAPI
               ↓
┌─────────────────────────────┐
│      RISE Engine (C++)      │  ← G-Assist Core
└─────────────────────────────┘
```

**Key Benefits:**
- **Zero network overhead** - No Flask server, no HTTP requests
- **True streaming** - Text appears instantly as the AI generates it
- **Low latency** - Direct function calls via pywebview's JavaScript bridge
- **Single process** - Everything runs in one efficient desktop application

### Requirements
- Python 3.x with packages from requirements.txt
- pywebview (automatically installed)
- Modern Windows OS (Windows 10/11)
- Visual C++ Runtime (see installation section above)

### UI Features

#### Real-Time Streaming
Watch responses appear word-by-word as the AI generates them - no waiting for complete responses!

#### Thinking Mode
Enable "Thinking Mode" from the + menu to see the AI's reasoning process in formatted bubbles.

#### TTFT Metrics
Every response displays its Time To First Token (TTFT) - the critical latency metric showing how quickly the AI starts responding.

Example: `TTFT: 0.234s`

#### Voice Input
Click the + button and select "Load WAV File" to transcribe and process audio input.

**Tip**: The GUI automatically handles microphone detection and will show available options in Settings.

## Screenshots

### Desktop GUI in Action
![G-Assist Desktop GUI](rise-gui-example.png)

**What you'll see:**
- Dark-themed chat interface with NVIDIA green accents
- Real-time streaming responses with thinking bubbles
- TTFT metrics displayed below each response
- Microphone icon and input controls at the bottom
- Hamburger menu for settings and options

## Troubleshooting Tips
- **Commands not working?** Make sure G-Assist core services are running
- **Installation issues?** Verify your Python version and pip installation

## Need Help?
If you run into any issues:
1. Verify that G-Assist core services are running
2. Check your Python environment setup
3. Try restarting your application

## License
This project is licensed under the Apache License 2.0 - see the LICENSE file for details.
