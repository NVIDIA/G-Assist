# Gemini Plugin - Tethered Mode Migration

## Overview

Updated the Google Gemini plugin to use the tethered plugin architecture (Phases 1-3).

---

## Summary

✅ **Full tethered mode support** (Phases 1-3)  
✅ **Interactive setup wizard** for API key acquisition  
✅ **User input passthrough** during onboarding  
✅ **Heartbeat monitoring** for health checks  
✅ **Clean awaiting_input protocol**  

---

## Changes Made

### 1. manifest.json

**Added tethered mode configuration:**
```json
{
  "persistent": true,       // Changed from false - keep running
  "tethered": true,         // NEW: Enable tethered mode
  "tether_config": {
    "heartbeat_interval": 5,
    "heartbeat_timeout": 20,
    "onboarding_timeout": 60,
    "allow_passthrough": true
  }
}
```

**Why:**
- `persistent: true` - Keep plugin running between requests
- `tethered: true` - Enable heartbeat monitoring
- Shorter onboarding timeout (60s) - Gemini doesn't need long setup
- `allow_passthrough: true` - Support future interactive features

---

### 2. gemini.py

#### Added Interactive Setup Wizard

**New Function: `execute_setup_wizard()`**

Guides users through getting their Google Gemini API key:

1. Opens Google AI Studio in browser (https://aistudio.google.com/app/apikey)
2. Opens the API key file in Notepad for user to paste
3. Waits for user to type "done" via passthrough
4. Verifies the API key works
5. Initializes the Gemini client
6. Completes setup

**Setup Flow:**
```
[YOU]: search google for latest news

_google>_ GOOGLE GEMINI PLUGIN - FIRST TIME SETUP
_google>_ [Instructions to get API key]
_google>_ Opening Google AI Studio...

[YOU]: done

_google>_ [OK] Google Gemini plugin is configured and ready!

[YOU]: search google for latest news
_google>_ [Gemini response with news]
```

#### Added Tethered Mode Functions

**Imports:**
```python
import threading
import time
```

**Helper Functions:**
- `send_heartbeat(state)` - Send silent heartbeat to engine
- `send_status_message(message)` - Send visible status updates
- `send_state_change(new_state)` - Notify state transitions
- `start_continuous_heartbeat(state, interval, show_dots)` - Background heartbeat thread
- `stop_continuous_heartbeat()` - Clean shutdown

**Updated Response Generators:**
```python
def generate_success_response(message=None, awaiting_input=False):
    return {'success': True, 'awaiting_input': awaiting_input, ...}

def generate_failure_response(message=None, awaiting_input=False):
    return {'success': False, 'awaiting_input': awaiting_input, ...}

def generate_message_response(message, awaiting_input=False):
    return {'success': True, 'message': message, 'awaiting_input': awaiting_input}
```

#### Main Loop Updates

**Heartbeat Start:**
```python
# Start heartbeat on plugin launch
start_continuous_heartbeat(state="ready", interval=5, show_dots=False)
```

**User Input Passthrough:**
```python
# Handle user input messages
if input.get('msg_type') == 'user_input':
    user_input_text = input.get('content', '')
    response = generate_message_response(f"Received: {user_input_text}", awaiting_input=False)
    write_response(response)
    continue
```

**Termination Handling:**
```python
# Handle termination messages
if input.get('msg_type') == 'terminate':
    response = generate_message_response(f"[OK] Plugin terminating", awaiting_input=False)
    write_response(response)
    stop_continuous_heartbeat()
    break
```

**END Token Stripping:**
```python
# Remove <<END>> token before JSON parsing
END_TOKEN = '<<END>>'
if retval.endswith(END_TOKEN):
    retval = retval[:-len(END_TOKEN)]
```

**Cleanup on Shutdown:**
```python
if cmd == SHUTDOWN_COMMAND:
    stop_continuous_heartbeat()
    break
```

---

## Benefits

### Phase 1: Heartbeat Protocol
✅ Engine monitors Gemini plugin health  
✅ Automatic restart if plugin hangs  
✅ Configurable timeouts

### Phase 2: Status Messages
✅ Can send progress updates for long queries  
✅ Visual feedback during processing  
✅ State management support

### Phase 3: User Input Passthrough
✅ Ready for future interactive features  
✅ Termination support (cancel long queries)  
✅ Clean protocol with `awaiting_input` field

---

## Backward Compatibility

✅ **Existing behavior preserved** - all commands work as before  
✅ **No breaking changes** - default `awaiting_input=false`  
✅ **Optional features** - heartbeats and status are opt-in per response

---

## Usage

### Normal Query (Non-Interactive)
```python
def execute_query_gemini_command(params, context, system_info):
    result = query_gemini(params['query'])
    # Normal completion, exit passthrough
    return generate_success_response(result, awaiting_input=False)
```

### Long Query with Progress (Future Enhancement)
```python
def execute_long_query(params):
    send_status_message("Analyzing complex query...")
    
    # Do work...
    result = complex_analysis()
    
    # Done, exit passthrough
    return generate_success_response(result, awaiting_input=False)
```

### Interactive Mode (Future Enhancement)
```python
def interactive_mode():
    send_status_message("Interactive mode started...")
    
    # Return with awaiting_input=true
    return generate_success_response(
        "I'm ready! Type your questions...",
        awaiting_input=True  # Stay in passthrough
    )
```

---

## Testing

1. **Rebuild Gemini plugin:**
   ```bash
   cd C:\Users\local-risaac\Documents\G-Assist\plugins\examples\gemini
   .\build.bat
   ```

2. **Test normal query:**
   ```
   [YOU]: what's the weather in tokyo?
   _google>_ The weather in Tokyo...
   [YOU]: ← Prompt appears normally
   ```

3. **Test persistence:**
   - Plugin stays running between queries
   - Heartbeats keep connection alive
   - Faster subsequent queries (no startup delay)

---

## Files Modified

1. **manifest.json** - Added tethered configuration
2. **gemini.py** - Added tethered mode functions and handlers

**Lines Added:** ~150 lines  
**Status:** ✅ Ready for testing

---

**Date:** November 1, 2025  
**Migrated From:** Spotify plugin tethered architecture  
**Status:** Complete

