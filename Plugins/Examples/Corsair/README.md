# Corsair Illumination Plugin for G-Assist
The _Corsair Illumination Plugin for G-Assist_ allows a user to change the color of the LEDs found on supported devices.

While devices that support the _iCUE SDK v4.0.84_ should be supported, some devices may not. This code was tested on a limited number of devices.

## Quick Start
1. Clone the _Corsair Illumination Plugin for G-Assist_
2. Download and install _[Corsair iCUE Software](https://www.corsair.com/us/en/s/downloads)_ 
    - Location: https://www.corsair.com/us/en/s/downloads
3. Download and extract _[iCUE SDK v4.0.84](https://github.com/CorsairOfficial/cue-sdk/releases/download/v4.0.84/iCUESDK_4.0.84.zip)_ to the project's root directory
    - Location: https://github.com/CorsairOfficial/cue-sdk/releases/tag/v4.0.84 > `iCUESDK_4.0.85.zip`
4. Download and extract _[JSON for Modern C++ version 3.11.3](https://github.com/nlohmann/json/releases/download/v3.11.3/include.zip)_  to the project's root directory
    - Location https://github.com/nlohmann/json/releases/tag/v3.11.3 > `include.zip`
5. Open and build the _Visual Studio 2022_ solution

## Setup
Download and extract the required header files and libraries into the project directory.

```
git clone https://github.com/nvidia/g-assist/examples/corsair
cd corsair
tar -xf path\to\iCUESDK_4.0.84.zip
mkdir json && tar -xf path\to\include.zip -C json
```

## Build
1. Open the _Visual Studio 2022_ solution
2. Select target build [Debug, Release]
3. From the Menu Bar, select `Build` > `Build Solution`

## Run as a Plugin
1. Copy the built files: 
    - Copy the `g-assist-plugin-corsair.exe` file from the output folder
    - Copy the `manifest.json` file from the project root directory
2. Move the files to the plugin directory `%programdata%\NVIDIA Corporation\nvtopps\rise\adapters\corsair`
