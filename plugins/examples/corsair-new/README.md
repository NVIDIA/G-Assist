# Corsair iCUE Plugin for G-Assist (V2)

Smart control for all your Corsair devices through G-Assist. This plugin uses Protocol V2 with auto-discovery - just tell it what you want and it figures out the rest!

## Features

**🖱️ Mouse DPI Control**
- Set DPI with a single command - no device selection needed
- "Set my mouse DPI to 800"
- "Change mouse sensitivity to 1600"

**💡 Smart RGB Lighting**
- Control any or all devices with one command
- Auto-detects all connected Corsair devices
- "Turn my keyboard lights red"
- "Set all lights to blue"
- "Change mouse lighting to off"

**🎧 Headset EQ**
- Auto-discovers your headset and available presets
- "Set headset EQ to bass boost"
- "Change equalizer to FPS mode"

**📋 Profile Switching**
- Switch iCUE profiles instantly
- "Activate my gaming profile"
- "Switch to work profile"

## Supported Devices

Any device compatible with iCUE SDK v4 and Automation SDK:
- Keyboards (K-series, etc.)
- Mice (Sabre, Dark Core, etc.)
- Headsets (HS-series, Void, etc.)
- Mousepads, Fan Controllers, Coolers, RAM, and more

## Installation

### Prerequisites
- Windows 10/11
- [Corsair iCUE Software](https://www.corsair.com/us/en/s/downloads) installed and running
- G-Assist installed
- Visual Studio 2022 (to build)

### Build

1. Clone/download this repository
2. Open `corsair.sln` in Visual Studio 2022
3. Build in Release|x64 configuration

### Install

Copy to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\corsair\`:
- `g-assist-plugin-corsair.exe`
- `manifest.json`
- `iCUESDK.x64_2019.dll` (from `iCUESDK\redist\x64\`)
- `iCUEAutomationSDK.dll` (from `AutomationSDK\redist\x64\`)

## Usage Examples

```
User: "Set my mouse DPI to 800"
→ Set CORSAIR M65 RGB DPI to 800.

User: "Turn all lights blue"
→ Set 4 devices lighting to blue.

User: "Change keyboard to red"
→ Set K70 RGB lighting to red.

User: "Set headset EQ to bass boost"  
→ Set VOID RGB WIRELESS EQ to 'Bass Boost'.

User: "Switch to my gaming profile"
→ Activated iCUE profile 'Gaming'.

User: "What devices do I have?"
→ Found 4 Corsair device(s):
   - CORSAIR K70 RGB (keyboard)
   - CORSAIR M65 RGB (mouse)
   - CORSAIR VOID RGB WIRELESS (headset)
   - CORSAIR MM800 (mousemat)
   
   Available profiles: Default, Gaming, Work
```

## Available Commands

| Command | Description |
|---------|-------------|
| `corsair_set_mouse_dpi` | Set mouse DPI (100-26000) |
| `corsair_set_lighting` | Set device lighting color |
| `corsair_set_headset_eq` | Set headset equalizer preset |
| `corsair_set_profile` | Switch iCUE profile |
| `corsair_get_devices` | List connected devices |

## iCUE Setup

For the plugin to work, configure iCUE:

1. Open iCUE Settings → Plugins & Integrations
2. Enable SDK access
3. Grant permissions to the plugin when prompted

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Unable to connect to iCUE" | Ensure iCUE is running and SDK permissions are granted |
| "No Corsair mouse found" | Connect a Corsair mouse with DPI control |
| DPI not changing | Check if mouse supports DPI control in iCUE |
| Lighting not changing | Disable Windows Dynamic Lighting in Settings |

## Technical Details

- **Protocol**: V2 (JSON-RPC 2.0 with length-prefix framing)
- **SDKs**: iCUE SDK v4, Automation SDK
- **Language**: C++20

## License

Apache License 2.0 - see [LICENSE](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
