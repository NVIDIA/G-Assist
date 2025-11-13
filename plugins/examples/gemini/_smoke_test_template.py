import subprocess
import time
import sys

try:
    # Launch plugin and check it doesn't crash on startup
    # Use venv Python explicitly to ensure dependencies are available
    python_exe = '.venv/Scripts/python.exe' if sys.platform == 'win32' else '.venv/bin/python'
    proc = subprocess.Popen([python_exe, 'gemini.py'], 
                           stdin=subprocess.PIPE,
                           stdout=subprocess.PIPE, 
                           stderr=subprocess.PIPE,
                           text=True)
    
    # Wait for plugin to initialize
    time.sleep(0.5)
    
    # ENHANCED: Try sending a simple shutdown command to test command handling
    test_command = "{'tool_calls': [{'func': 'shutdown'}]}\n"
    try:
        proc.stdin.write(test_command)
        proc.stdin.flush()
        time.sleep(0.5)
    except Exception as e:
        # Command send failed, but that's ok - we just want to see if plugin stays alive
        pass
    
    # Check if plugin is still running (didn't crash from command)
    exit_code = proc.poll()
    
    # Kill the plugin
    try:
        proc.kill()
    except:
        pass
    
    try:
        proc.wait(timeout=1)
    except:
        pass
    
    # Get any stderr output
    try:
        _, stderr = proc.communicate(timeout=0.5)
    except:
        stderr = ""
    
    # If exit_code is None, plugin was still running (PASS)
    # If exit_code is not None, plugin crashed (FAIL)
    if exit_code is None or exit_code == 0:
        # Success - plugin started and handled commands without crashing
        sys.exit(0)
    else:
        # Plugin crashed during startup or command handling
        if stderr:
            print(f'Plugin crashed with code {exit_code}', file=sys.stderr)
            print(stderr, file=sys.stderr)
        else:
            print(f'Plugin exited with code {exit_code}', file=sys.stderr)
        sys.exit(1)
        
except Exception as e:
    print(f'Smoke test error: {e}', file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)

