# G-Assist Plugin Template - C++
_G-Assist Plugin Template - C++_ is a template to write a G-Assist plugin in C++.

## Quick Start
1. Clone the _G-Assist Plugin Template - C++_
2. Download and extract _[JSON for Modern C++ version 3.11.3](https://github.com/nlohmann/json/releases/download/v3.11.3/include.zip)_ to the project's root directory
    - Location: https://github.com/nlohmann/json/releases/tag/v3.11.3 > `include.zip`
3. Open and build the _Visual Studio 2022_ solution

## Setup
```
git clone https://github.com/nvidia/g-assist/templates/cpp-template
cd cpp-template
mkdir json && tar -xf path\to\include.zip -C json
```

## Build
1. Open the _Visual Studio 2022_ solution
2. Select target build [Debug, Release]
3. From the Menu Bar, select `Build` > `Build Solution`

## Run as a Plugin
1. Copy the built files: 
    - Copy the `cpp-template.exe` file from the output folder
    - Copy the `manifest.json` file from the project root directory
2. Move the files to the plugin directory `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\adapters\myplugin`
