# G-Assist Plugin Template - C++

Start building your own G-Assist plugin with this C++ template! This template provides everything you need to create powerful G-Assist plugins. Whether you're building a device controller, a game integration, or something entirely new, this template will help you get started quickly.

## What Can It Do?
- Provides a complete foundation for G-Assist plugin development
- Includes all necessary boilerplate code and structures
- Seamlessly integrates with G-Assist's plugin system
- Easy to understand and customize
- Ready for your creative ideas

## Before You Start
Make sure you have:
- Windows PC
- Visual Studio 2022
- G-Assist installed on your system
- Basic knowledge of C++

💡 **Tip**: This template is designed to be modular - you can easily add your own features while maintaining compatibility with G-Assist!

## Installation Guide

### Step 1: Get the Files
```bash
git clone --recurse-submodules <repository-url>
cd cpp-template
```
This downloads the template and all necessary files to your computer.

### Step 2: Get Required Dependencies
Download [JSON for Modern C++ v3.11.3](https://github.com/nlohmann/json/releases/download/v3.11.3/include.zip)

### Step 3: Set Up Dependencies
```bash
# Extract JSON library
mkdir json && tar -xf path\to\include.zip -C json
```

### Step 4: Build It
1. Open the solution in Visual Studio 2022
2. Select your build configuration (Debug/Release)
3. Build the solution (F7 or Build → Build Solution)

### Step 5: Install the Plugin
1. Create this folder (if it doesn't exist):
   ```
   %PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\adapters\myplugin
   ```
   💡 **Tip**: Copy and paste this path directly into File Explorer's address bar!

2. Copy these files to the folder you just created:
   - `cpp-template.exe` (from your build output folder)
   - `manifest.json` (from project root)

## How to Customize
Start customizing your plugin by:
- Modifying the command handlers in `commands.cpp`
- Adding your own features in new source files
- Updating `manifest.json` with your plugin's information
- Implementing your own response logic

💡 **Tip**: Check out our other plugin examples to see how to implement specific features!

## Troubleshooting Tips
- **Build failing?** Make sure JSON library is extracted to the correct location
- **Plugin not loading?** Double-check the installation folder path
- **Commands not working?** Verify your manifest.json is properly configured
- **Compilation errors?** Make sure all required headers are included

## Want to Contribute?
We'd love your help making this template even better! Feel free to submit issues and pull requests.

## License
This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Need Help?
If you run into any issues:
1. Check the troubleshooting section above
2. Review our plugin development documentation
3. Join our developer community for support
4. File an issue on our GitHub repository
