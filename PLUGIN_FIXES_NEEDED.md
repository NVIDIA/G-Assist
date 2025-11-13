# G-Assist Plugins - Required Fixes

## Summary
All Python plugins need fixes for:
1. **Crash prevention** when API keys/tokens are missing or empty
2. **User onboarding** with setup wizards (like Gemini plugin)
3. **Absolute paths** for config files (not relative paths)
4. **Proper error handling** with detailed logging

## Status

### ✅ FIXED: Stock Plugin
- ✅ Uses absolute paths for config
- ✅ Has setup wizard with instructions
- ✅ Won't crash on missing API key
- ✅ Handles user input passthrough
- ✅ Detailed logging

### ⚠️ NEEDS FIXING

#### 1. Discord Plugin (`discord/plugin.py`)
**Issues:**
- Uses relative path for log file (line 11): `os.environ.get("USERPROFILE", ".")`
- Will crash if `BOT_TOKEN` or `CHANNEL_ID` are empty strings (lines 163-164)
- Creates sample config but no user guidance
- No setup wizard

**Required Fixes:**
```python
# 1. Add absolute path for logs (like stock plugin):
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "discord")
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'discord-plugin.log')

# 2. Add setup wizard function (copy from stock plugin pattern)
# 3. Check if BOT_TOKEN/CHANNEL_ID are valid before using them
# 4. Add user input passthrough handling
# 5. Add SETUP_COMPLETE flag
```

#### 2. IFTTT Plugin (`ifttt/plugin.py`)
**Issues:**
- Likely has similar issues to Discord
- Check for API key handling

**Required Fixes:**
- Review and apply stock plugin pattern

#### 3. Nanoleaf Plugin (`nanoleaf/plugin.py`)
**Issues:**
- Likely needs API token handling
- Check for crash on missing token

**Required Fixes:**
- Review and apply stock plugin pattern

#### 4. Spotify Plugin (`spotify/plugin.py`)
**Issues:**
- OAuth tokens in `auth.json`
- Complex auth flow - needs special handling
- Check for crash on missing/expired tokens

**Required Fixes:**
- Review OAuth handling
- Add token refresh logic
- Apply stock plugin pattern for setup

#### 5. Twitch Plugin (`twitch/plugin.py`)
**Issues:**
- OAuth tokens needed
- Check for crash on missing tokens

**Required Fixes:**
- Review and apply stock plugin pattern

#### 6. Weather Plugin (`weather/plugin.py`)
**Issues:**
- Likely needs weather API key
- Check for crash on missing key

**Required Fixes:**
- Review and apply stock plugin pattern

#### 7. OpenRGB Plugin (`openrgb/plugin.py`)
**Issues:**
- No API key needed (local RGB control)
- But check for crashes if OpenRGB server not running

**Required Fixes:**
- Add graceful error handling if OpenRGB not available
- Don't crash - show helpful message

#### 8. Corsair Plugin (C++) (`corsair/`)
**Issues:**
- C++ plugin - different architecture
- Check for crashes if Corsair iCUE not installed

**Required Fixes:**
- Add graceful error handling
- Check if iCUE SDK available

#### 9. Logiled Plugin (C++) (`logiled/`)
**Issues:**
- C++ plugin - different architecture
- Check for crashes if Logitech Gaming Software not installed

**Required Fixes:**
- Add graceful error handling
- Check if Logitech LED SDK available

## Template Fix Pattern (Python Plugins)

### 1. Add Absolute Paths
```python
# Get the directory where the plugin is deployed
PLUGIN_DIR = os.path.join(os.environ.get("PROGRAMDATA", "."), "NVIDIA Corporation", "nvtopps", "rise", "plugins", "PLUGIN_NAME")
CONFIG_FILE = os.path.join(PLUGIN_DIR, 'config.json')

# Save log in plugin directory
os.makedirs(PLUGIN_DIR, exist_ok=True)
LOG_FILE = os.path.join(PLUGIN_DIR, 'plugin-name.log')
```

### 2. Add Setup State
```python
SETUP_COMPLETE = False
API_KEY = None

# Load config
try:
    with open(CONFIG_FILE, "r") as config_file:
        config = json.load(config_file)
    API_KEY = config.get("API_KEY_NAME", "")
    if API_KEY and len(API_KEY) > 10:
        SETUP_COMPLETE = True
        logger.info(f"Successfully loaded API key from {CONFIG_FILE}")
    else:
        logger.warning(f"API key is empty or invalid in {CONFIG_FILE}")
        API_KEY = None
except FileNotFoundError:
    logger.error(f"Config file not found at {CONFIG_FILE}")
    API_KEY = None
except Exception as e:
    logger.error(f"Error loading config: {e}")
    API_KEY = None
```

### 3. Add Setup Wizard
```python
def execute_setup_wizard() -> Response:
    """Guide user through API key setup."""
    global SETUP_COMPLETE, API_KEY
    
    # Check if API key was added
    try:
        with open(CONFIG_FILE, "r") as config_file:
            config = json.load(config_file)
        new_key = config.get("API_KEY_NAME", "")
        if new_key and len(new_key) > 10:
            API_KEY = new_key
            SETUP_COMPLETE = True
            return {
                'success': True,
                'message': "✓ API key configured! You can now use the plugin.",
                'awaiting_input': False
            }
    except:
        pass
    
    # Show setup instructions
    message = f"""
PLUGIN NAME - FIRST TIME SETUP
==============================

Welcome! Let's get your API key.

YOUR TASK:
   1. Visit: https://api-provider.com/signup
   2. Sign up and get your API key
   3. Open this file: {CONFIG_FILE}
   4. Replace empty quotes with your key
   5. Save the file

After saving, send me ANY message (like "done") and I'll verify it!
"""
    
    return {
        'success': True,
        'message': message,
        'awaiting_input': True
    }
```

### 4. Update Initialize Command
```python
def execute_initialize_command() -> Response:
    """Initialize the plugin."""
    logger.info("Initializing plugin...")
    
    # Check if setup is needed
    if not SETUP_COMPLETE or not API_KEY:
        return execute_setup_wizard()
    
    return generate_success_response("Plugin initialized successfully.")
```

### 5. Add User Input Handling in Main Loop
```python
# Handle user input passthrough messages
if isinstance(input, dict) and input.get('msg_type') == 'user_input':
    user_input_text = input.get('content', '')
    logger.info(f'[INPUT] Received user input passthrough: "{user_input_text}"')
    
    # Check if setup is needed
    global SETUP_COMPLETE, API_KEY
    if not SETUP_COMPLETE:
        logger.info("[WIZARD] User input during setup - checking API key")
        response = execute_setup_wizard()
        write_response(response)
        continue
```

### 6. Check Setup Before Function Execution
```python
if cmd in commands:
    if cmd in ['initialize', 'shutdown']:
        response = commands[cmd]()
    else:
        # Check if setup is needed before executing functions
        if not SETUP_COMPLETE or not API_KEY:
            logger.info('[COMMAND] API key not configured - starting setup wizard')
            response = execute_setup_wizard()
        else:
            params = tool_call.get(PARAMS_PROPERTY, {})
            response = commands[cmd](params, context, system_info)
```

## Priority Order

1. **HIGH**: Discord, IFTTT, Nanoleaf, Spotify, Twitch, Weather (all need API keys)
2. **MEDIUM**: OpenRGB (local service, but needs error handling)
3. **LOW**: Corsair, Logiled (C++ plugins, different architecture)

## Testing Checklist

For each plugin after fixes:
- [ ] Plugin doesn't crash with empty config
- [ ] Setup wizard appears on first use
- [ ] Setup wizard re-checks config after user input
- [ ] Plugin works normally after API key is added
- [ ] Logs are written to correct location
- [ ] Config file is read from correct location

## Notes

- **Gemini plugin** is the gold standard - it has proper onboarding
- **Stock plugin** now matches Gemini's pattern
- All other Python plugins should follow this same pattern
- C++ plugins need different approach (check SDK availability, don't crash)

