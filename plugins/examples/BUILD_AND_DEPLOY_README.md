# Build and Deploy All Plugins

This directory contains scripts to automatically build and deploy all G-Assist plugins.

## Quick Start

### Option 1: Simple Batch File (Recommended)

Just double-click or run:

```cmd
build_and_deploy_all.bat
```

This will:
1. Run `setup.bat` for each plugin (install dependencies)
2. Run `build.bat` for each plugin (build executables)
3. Deploy all files to `C:\ProgramData\NVIDIA Corporation\nvtopps\rise\plugins\`

### Option 2: PowerShell Script (Advanced)

For more control, use the PowerShell script directly:

```powershell
.\build_and_deploy_all.ps1
```

## Advanced Usage

### Skip Setup (if dependencies already installed)

```powershell
.\build_and_deploy_all.ps1 -SkipSetup
```

Or via batch file:
```cmd
build_and_deploy_all.bat -SkipSetup
```

### Build Specific Plugins Only

```powershell
.\build_and_deploy_all.ps1 -PluginNames @('weather', 'stock', 'discord')
```

### Custom Deployment Location

```powershell
.\build_and_deploy_all.ps1 -DeploymentRoot "D:\MyPlugins"
```

### Build from Different Directory

```powershell
.\build_and_deploy_all.ps1 -PluginsRoot "C:\MyPlugins\examples"
```

## What Gets Built

The script automatically detects all plugin directories that contain:
- `build.bat` (required)
- `setup.bat` (optional)

Python-based plugins:
- ✅ discord
- ✅ ifttt
- ✅ nanoleaf
- ✅ openrgb
- ✅ spotify
- ✅ stock
- ✅ twitch
- ✅ weather
- ✅ gemini

C++ plugins (skipped by this script):
- ⏭️ corsair
- ⏭️ logiled

## Output

The script provides:
- ✅ Color-coded status for each plugin
- 📊 Summary table with results
- ⚠️ Warnings for locked executables (will update on next restart)
- ❌ Error details for failed builds

## Troubleshooting

### "Executable is locked"

If a plugin is currently running, the script will:
- ✅ Update manifest.json and config.json
- ⚠️ Skip the .exe file (will be updated on next plugin restart)

### "Build failed"

Check the output for specific errors. Common issues:
- Missing Python dependencies (run without `-SkipSetup`)
- Python not in PATH
- Virtual environment issues

### "Permission denied"

Run PowerShell or Command Prompt as Administrator if deploying to `C:\ProgramData\`.

## Examples

### Full rebuild of everything:
```cmd
build_and_deploy_all.bat
```

### Quick rebuild (skip setup):
```cmd
build_and_deploy_all.bat -SkipSetup
```

### Build only weather and stock plugins:
```powershell
.\build_and_deploy_all.ps1 -PluginNames @('weather', 'stock')
```

### Build and deploy to custom location:
```powershell
.\build_and_deploy_all.ps1 -DeploymentRoot "D:\TestPlugins" -SkipSetup
```

## Script Features

- ✅ Auto-detects all plugins
- ✅ Runs setup and build for each
- ✅ Handles locked executables gracefully
- ✅ Color-coded output
- ✅ Detailed summary table
- ✅ Exit codes for CI/CD integration
- ✅ Supports custom plugin selection
- ✅ Supports custom deployment paths

## Exit Codes

- `0` - All plugins built and deployed successfully
- `1` - One or more plugins failed to build

## Notes

- The script automatically creates deployment directories if they don't exist
- Skipped plugins (C++ plugins without build.bat) don't count as failures
- The script uses `cmd /c` to run batch files for better compatibility
- All paths support spaces and special characters

