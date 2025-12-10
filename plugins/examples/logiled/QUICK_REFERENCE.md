# LogiLED Plugin - Quick Reference Guide

## 🚀 Quick Start

### For Developers (Building from Source)
```bash
# 1. Build the full installer
build_installer.bat

# 2. Run as Administrator
plugin-installer.exe
```

### For Distribution (Pre-built Plugin)
```bash
# 1. Build the copy installer
build_copy_installer.bat

# 2. Distribute with pre-built files
# Users run: plugin-copy-installer.exe as Administrator
```

---

## 📋 Files Overview

| File | Purpose | When to Use |
|------|---------|-------------|
| `manifest.json` | Plugin metadata with enhanced descriptions | Always included |
| `installer.py` | Full build + install script | Building from source |
| `plugin-copy-installer.py` | Lightweight install script | Pre-built plugins |
| `build_installer.bat` | Creates plugin-installer.exe | Development |
| `build_copy_installer.bat` | Creates plugin-copy-installer.exe | Distribution |

---

## 🔐 Security Features

### What's Protected
- ✅ Plugin executable (`.exe`)
- ✅ Manifest file (`manifest.json`)
- ✅ Configuration file (`config.json`)
- ✅ All files in plugin directory

### Permission Model
| User Type | Read | Execute | Modify | Delete |
|-----------|------|---------|--------|--------|
| Regular User | ✅ | ✅ | ❌ | ❌ |
| Administrator | ✅ | ✅ | ✅ | ✅ |

### Security Guarantee
- Installation **fails** if ACL cannot be applied
- Insecure files are **automatically removed**
- No partial/insecure installations possible

---

## 🛠️ Installation Paths

### Plugin Location
```
%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\adapters\logiled\
```

### Required Files in Installation
```
logiled/
├── g-assist-plugin-logiled.exe  (required)
├── manifest.json                 (required)
└── config.json                   (optional)
```

---

## 📝 Manifest Enhancements

### Before
```json
{
  "name": "logi_change_keyboard_lights",
  "description": "Changes the color of the keyboard's LEDs",
  "properties": {
    "color": {
      "type": "string",
      "description": "the color"
    }
  }
}
```

### After
```json
{
  "name": "logi_change_keyboard_lights",
  "description": "Changes the RGB color of Logitech keyboard LEDs. Controls all zones and lighting effects on supported Logitech G keyboards. Use this when the user wants to change keyboard backlight color, set keyboard RGB lighting, or customize keyboard illumination.",
  "tags": [
    "lighting", "keyboard", "Logiled", "Logitech", "logi",
    "RGB", "backlight", "illumination", "keyboard color", "LED"
  ],
  "properties": {
    "color": {
      "type": "string",
      "description": "[required] The color to set the keyboard LEDs. Common values: 'red', 'green', 'blue', 'cyan', 'magenta', 'yellow', 'white', 'orange', 'purple', 'pink', 'teal', 'ice_blue', 'crimson', 'gold', 'neon_green', 'off' (turns off lighting). Common query phrases: 'change to [color]', 'set [color]', 'make it [color]', 'turn [color]'. Examples: 'Change keyboard to blue' (color='blue'), 'Set keyboard lighting to red' (color='red'), 'Turn keyboard off' (color='off')."
    }
  },
  "required": ["color"]
}
```

**Benefits:**
- Better AI understanding
- More accurate command routing
- Natural language examples included

---

## 🎯 Command Examples

Users can now use these natural language commands:

### Keyboard
- "Change my keyboard to blue"
- "Set keyboard lighting to red"  
- "Turn keyboard off"
- "Make keyboard green"

### Mouse
- "Change mouse to purple"
- "Set mouse lighting to cyan"
- "Turn mouse off"

### Headset
- "Change headset to pink"
- "Set headphones to orange"
- "Turn headset off"

---

## 🔧 Configuration Options

Edit `config.json` in installation directory:

```json
{
  "features": {
    "use_setup_wizard": false,      // Show setup wizard on first run
    "setup_complete": true,          // Skip setup (already configured)
    "restore_on_shutdown": true,     // Restore original colors on exit
    "allow_keyboard": true,          // Enable keyboard control
    "allow_mouse": true,             // Enable mouse control
    "allow_headset": true            // Enable headset control
  }
}
```

---

## 🐛 Troubleshooting

### Installer Issues

| Problem | Solution |
|---------|----------|
| "Not running as Administrator" | Right-click installer → Run as administrator |
| "Visual Studio not found" | Install VS 2022 or use copy installer |
| "Failed to apply security" | Check Windows security logs, ensure NTFS filesystem |
| "Plugin not found" | Ensure executable exists before running copy installer |

### Runtime Issues

| Problem | Solution |
|---------|----------|
| Commands not working | Enable "Allow programs to control lighting" in G HUB |
| Device not responding | Verify device supports LED SDK 9.00 |
| Plugin not loading | Check installation path, restart G-Assist |
| Permission errors | Reinstall using installer (applies ACL correctly) |

---

## 📊 Comparison with Other Plugins

### Similar to mod.io Plugin
- ✅ ACL security implementation
- ✅ Two installer options (full/copy)
- ✅ Enhanced manifest descriptions
- ✅ Automatic privilege elevation
- ✅ Security-first installation

### Different from Python Plugins
- ❌ No virtual environment needed
- ❌ No PyInstaller required (for plugin itself)
- ✅ Direct Windows API integration
- ✅ Installed to `adapters` directory (not `plugins`)

---

## 🔄 Update Process

### Updating from Old Version

1. **Uninstall old version:**
   ```
   Delete: %PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\adapters\logiled\
   ```

2. **Install new version:**
   ```bash
   plugin-installer.exe
   # (run as Administrator)
   ```

3. **Verify:**
   - Check files are in installation directory
   - Restart G-Assist
   - Test a command

### Updating Security Only

If plugin works but needs ACL security applied:

```bash
# Run copy installer on existing installation
plugin-copy-installer.exe
# (run as Administrator)
```

This will re-apply ACL without rebuilding.

---

## 📦 Distribution Checklist

Before distributing to users:

- [ ] Build plugin in Release mode
- [ ] Test plugin functionality
- [ ] Create copy installer executable
- [ ] Test installer on clean system
- [ ] Verify ACL security is applied
- [ ] Include README and documentation
- [ ] Package files together

**Distribution Package:**
```
logiled-distribution/
├── plugin-copy-installer.exe
├── g-assist-plugin-logiled.exe
├── manifest.json
├── README.md
├── LICENSE
└── ATTRIBUTIONS.md
```

---

## 🎓 Developer Notes

### ACL Implementation Details

The security implementation uses Windows APIs:
- `advapi32.dll` - Security APIs
- `kernel32.dll` - Error handling
- SID lookups for current user and Administrators
- DACL creation and application
- Recursive file permission setting

### Key Functions

```python
create_restricted_security_descriptor()  # Creates ACL
set_plugin_acl_permissions(dir)         # Applies to directory
remove_existing_dacl(file)              # Cleans before applying
set_file_acl_permissions(file, sd)      # Applies to file
```

### Error Handling

All security functions return `(bool, Optional[str])`:
- `(True, None)` - Success
- `(False, error_message)` - Failure with details

On failure, installation is rolled back automatically.

---

## 📚 Additional Resources

- [ARCHITECTURE_UPDATE_SUMMARY.md](ARCHITECTURE_UPDATE_SUMMARY.md) - Full change details
- [README.md](README.md) - Complete user guide
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [LICENSE](LICENSE) - Apache 2.0 license

---

## ✅ Success Indicators

Installation succeeded if you see:
```
✓ Administrator privileges and permissions verified
✓ Security restrictions applied successfully
=== Installation Complete! ===
```

Plugin working if:
- G-Assist recognizes commands
- Logitech devices respond to color changes
- No errors in G-Assist logs

---

## 🆘 Getting Help

1. Check troubleshooting section above
2. Review installation logs
3. Verify all prerequisites installed
4. Test with manual installation
5. Check NVIDIA G-Assist logs
6. Review Windows Event Viewer for security errors

---

*Last Updated: December 10, 2025*
*Architecture Version: Latest (matches mod.io plugin)*

