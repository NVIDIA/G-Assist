# Corsair iCUE Plugin for G-Assist (V2)

Smart control for all your Corsair devices through G-Assist. This plugin uses Protocol V2 with auto-discovery - just tell it what you want and it figures out the rest!

## Features

**🖱️ Mouse DPI Control**
- Set DPI with a single command - no device selection needed
- "Set my mouse DPI to 800"
- "Change mouse sensitivity to 1600"

**💡 Per-Device RGB Lighting**
- Separate commands for each device type for reliable targeting
- Auto-detects all connected Corsair devices
- "Turn my keyboard lights red"
- "Set mouse to blue"
- "Change headset lighting to off"
- "Make all my Corsair stuff green"

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
- Keyboards (K70, K95, K100, etc.)
- Mice (M65, Dark Core, Sabre, Scimitar, etc.)
- Headsets (VOID, Virtuoso, HS-series, etc.)
- Mousepads (MM800, MM700)
- Fan Controllers (Commander Pro, Lighting Node)
- Coolers (H100i, H150i, Elite Capellix)
- RAM (Dominator, Vengeance RGB)
- Headset Stands (ST100)
- Motherboards, GPUs, and more

## Installation

### Prerequisites
- Windows 10/11
- [Corsair iCUE Software](https://www.corsair.com/us/en/s/downloads) installed and running
- G-Assist installed

### Quick Deploy (Pre-built)

Use the setup script from the `plugins/examples/` folder:

```batch
cd plugins\examples
setup.bat corsair-new -deploy
```

This will:
1. Copy runtime DLLs to `libs/` folder
2. Deploy the pre-built `g-assist-plugin-corsair.exe`, `manifest.json`, and DLLs to G-Assist

### Build from Source

If you want to modify and rebuild:

1. **Setup** (copies SDK headers and prepares build environment):
   ```batch
   cd plugins\examples
   setup.bat corsair-new
   ```

2. **Build** with Visual Studio:
   ```batch
   cd corsair-new
   msbuild corsair.sln /p:Configuration=Release /p:Platform=x64
   ```
   Or open `corsair.sln` in Visual Studio 2022 and build Release|x64.

3. **Deploy** (after building):
   ```batch
   cd plugins\examples
   setup.bat corsair-new -deploy
   ```

### Manual Install

If not using the setup script, copy to `%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\corsair-new\`:
- `g-assist-plugin-corsair.exe`
- `manifest.json`
- `libs\iCUESDK.x64_2019.dll` (from `iCUESDK\redist\x64\`)
- `libs\iCUEAutomationSDK.dll` (from `AutomationSDK\redist\x64\`)

## Usage Examples

```
User: "Set my mouse DPI to 800"
→ Set CORSAIR M65 RGB DPI to 800.

User: "Turn my keyboard red"
→ Set CORSAIR K70 RGB to red.

User: "Change mouse to blue"
→ Set CORSAIR M65 RGB to blue.

User: "Set headset lighting off"
→ Turned off lighting on CORSAIR VOID RGB WIRELESS.

User: "Turn all lights green"
→ Set 4 devices to green: CORSAIR K70 RGB, CORSAIR M65 RGB, CORSAIR VOID RGB WIRELESS, CORSAIR MM800.

User: "Set headset EQ to bass boost"  
→ Set VOID RGB WIRELESS EQ to 'Bass Boost'.

User: "Switch to my gaming profile"
→ Switched to profile 'Gaming'.

User: "What devices do I have?"
→ Corsair Devices:
   - CORSAIR K70 RGB (keyboard)
   - CORSAIR M65 RGB (mouse)
   - CORSAIR VOID RGB WIRELESS (headset)
   - CORSAIR MM800 (mousemat)
   
   Profiles: Default, Gaming, Work
```

## Available Commands

### Lighting Commands (Per-Device-Type)
| Command | Description |
|---------|-------------|
| `corsair_set_keyboard_lighting` | Set keyboard LED color |
| `corsair_set_mouse_lighting` | Set mouse LED color |
| `corsair_set_headset_lighting` | Set headset LED color |
| `corsair_set_mousemat_lighting` | Set mousemat LED color |
| `corsair_set_fan_lighting` | Set fan controller/fan LED color |
| `corsair_set_cooler_lighting` | Set AIO/cooler LED color |
| `corsair_set_ram_lighting` | Set RAM/memory LED color |
| `corsair_set_gpu_lighting` | Set GPU LED color |
| `corsair_set_motherboard_lighting` | Set motherboard LED color |
| `corsair_set_headset_stand_lighting` | Set headset stand LED color |
| `corsair_set_all_lighting` | Set ALL devices to the same color |

### Other Commands
| Command | Description |
|---------|-------------|
| `corsair_set_mouse_dpi` | Set mouse DPI (100-26000) |
| `corsair_set_headset_eq` | Set headset equalizer preset |
| `corsair_set_profile` | Switch iCUE profile |
| `corsair_get_profiles` | List available profiles |
| `corsair_get_devices` | List connected devices |

### Supported Colors
`red`, `green`, `blue`, `cyan`, `magenta`, `yellow`, `white`, `black`, `orange`, `purple`, `pink`, `gold`, `teal`, `gray`/`grey`, or `off` to turn off lighting.

## iCUE Setup

For the plugin to work, enable SDK access in iCUE:

1. Open iCUE Settings
2. Toggle **iCUE SDK** to ON

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Unable to connect to iCUE" | Ensure iCUE is running and iCUE SDK is enabled in settings |
| "No Corsair keyboard found" | Ensure your keyboard is connected and visible in iCUE |
| DPI not changing | Some mice don't support DPI control via SDK - set DPI directly in iCUE |
| Lighting not changing | Disable Windows Dynamic Lighting in Settings → Personalization → Dynamic Lighting |

## Project Structure

```
corsair-new/
├── g-assist-plugin-corsair.exe  # Pre-built executable (delay-load DLLs)
├── manifest.json                # Plugin manifest for G-Assist
├── main.cpp                     # Source code
├── corsair.sln                  # Visual Studio solution
├── corsair.vcxproj              # Visual Studio project
├── iCUESDK/                     # Corsair iCUE SDK
│   ├── include/                 # Headers
│   ├── lib/x64/                 # Link libraries
│   └── redist/x64/              # Runtime DLLs
├── AutomationSDK/               # Corsair Automation SDK
│   ├── include/                 # Headers
│   ├── lib/x64/                 # Link libraries
│   └── redist/x64/              # Runtime DLLs
├── json/                        # nlohmann/json (header-only)
└── libs/                        # Runtime DLLs (created by setup.bat)
```

## Technical Details

- **Protocol**: V2 (JSON-RPC 2.0 with length-prefix framing)
- **SDKs**: iCUE SDK v4, Automation SDK
- **Language**: C++20
- **DLL Loading**: Delay-load with `libs/` subdirectory search path

## License

Apache License 2.0 - see [LICENSE](LICENSE)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)
