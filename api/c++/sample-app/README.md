### 💻 Sample Application
Want to see G-Assist in action? Try our sample app:

```bash
cd SampleApp
```

**Requirements:**
- Windows 10/11
- NVIDIA GPU
- NVIDIA driver 572.83+
- Visual Studio 2019+ (if building from source)

Choose from:
- [Download pre-built binary](SampleApp/RISE_sample_app.exe)
- [Build from source](SampleApp/README.md)

### APIs to Access G-Assist
#### Register to Receive G-Assist Updates
 Informs G-Assist of a client's presence by registering a callback to the client processes. Registration also triggers models and adapters downloads for later use.
``` C++
NVAPI_INTERFACE NvAPI_RegisterRiseCallback(__in NV_RISE_CALLBACK_SETTINGS* pCallbackSettings)
```
#### Send G-Assist Requests
G-Assist clients send requests to G-Assist to run inference on their behalf

``` C++
NVAPI_INTERFACE NvAPI_RequestRise(__in NV_REQUEST_RISE_SETTINGS* requestContent)
```

To help, we've created a python binding to jumpstart your development. 
```
cd plugins\bindings\python-bindings
```
or a ready-made sample app 

# RISE NvTOPPS Sample Application

A sample implementation demonstrating NVIDIA RISE (Runtime Inference System Engine) functionality using NvTOPPS. This application provides a testing environment for RISE's chat capabilities.

## Prerequisites

### Required Components
1. **NVIDIA API Files**
   - Source: [NVIDIA GitHub](https://github.com/NVIDIA/nvapi)
   - Required files:
     - All `.h` header files
     - `nvapi64.lib`
     - `nvapi.h`

2. **JSON Library**
   - Source: [nlohmann/json](https://github.com/nlohmann/json/tree/develop/include/nlohmann)
   - Required: Complete `nlohmann` directory

3. **File Setup**
   - Copy all required files to the [RISE_sample_app](\RISE_sample_app) directory
   - Ensure `main.cpp` and all dependencies are in the same location

### System Requirements
- Windows 10/11
- NVIDIA GPU
- RISE-compatible NVIDIA driver (version 572.83 or newer)
- Visual Studio 2019 or later (for building from source)

## Installation Options

### Option 1: Pre-built Binary
1. Download the pre-compiled executable from [Sample App](\RISE_sample_app.exe)
2. Ensure you have a RISE-compatible driver installed
3. Run the executable directly

### Option 2: Building from Source
1. Clone or download this repository
2. Verify all prerequisites are met
3. Open `RISE_sample_app.sln` in Visual Studio
4. Configure the build:
   - Verify file locations
   - Select build configuration (Debug/Release)
   - Ensure platform target matches your system
5. Build the solution (F7 or Build → Build Solution)

## Usage Guide

### Initial Setup
1. Install NVIDIA driver (minimum version 572.83)
2. Verify RISE components are present on your system

### Running the Application
1. Launch `RISE_sample_app.exe`
2. First-time launch:
   - Application will automatically check for RISE components
   - Missing components will be installed automatically with progress updates
   - Wait for installation and initialization to complete

### Using the Chat Interface
1. Application will establish connection to RISE backend
2. Type your queries in the chat interface
3. Press Enter to send messages
4. Wait for AI responses

### Troubleshooting
- If the application fails to start:
  - Verify driver version
  - Check all required files are present
  - Ensure GPU is RISE-compatible
- If chat doesn't respond:
  - Check internet connectivity
  - Verify RISE services are running
  - Restart the application

## Development Notes
- Built using NVIDIA NVAPI SDK
- Implements NvTOPPS for RISE communication
- Uses nlohmann/json for JSON parsing

## Support
For issues or questions:
- Check NVIDIA developer forums
- Review RISE documentation
- Contact NVIDIA support

## License
Apache 2.0 License