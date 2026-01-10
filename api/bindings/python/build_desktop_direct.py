"""Build G-Assist Desktop - Direct API version (no Flask!)"""
import subprocess
import sys
import os
import shutil
import re

print("="*60)
print("Building G-Assist Desktop - Direct API Version")
print("="*60)

# Install rise package
print("\nInstalling rise package...")
subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."])

def bump_desktop_gui_version():
    """Automatically bump the version string inside the desktop GUI before packaging."""
    gui_path = os.path.join(os.path.dirname(__file__), "rise-gui-desktop-direct.py")
    try:
        with open(gui_path, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        print(f"WARNING: Unable to read GUI script for version bump: {exc}")
        return

    match = re.search(r"Version (\d+)\.(\d+)\.(\d+)", content)
    if not match:
        print("WARNING: Could not locate a semantic Version X.Y.Z string in GUI file; skipping bump.")
        return

    major, minor, patch = map(int, match.groups())
    old_version = f"{major}.{minor}.{patch}"
    new_version = f"{major}.{minor}.{patch + 1}"

    updated_content = re.sub(r"Version \d+\.\d+\.\d+", f"Version {new_version}", content)

    if updated_content == content:
        print(f"INFO: GUI version already set to {old_version}; no bump applied.")
        return

    try:
        with open(gui_path, "w", encoding="utf-8") as fh:
            fh.write(updated_content)
        print(f"\nBumped desktop GUI version: {old_version} -> {new_version}")
    except OSError as exc:
        print(f"WARNING: Failed to write updated version back to GUI script: {exc}")

# Find DLL
from rise import rise
rise_path = os.path.dirname(rise.__file__)
dll_path = os.path.join(rise_path, "python_binding.dll")

if not os.path.exists(dll_path):
    print(f"ERROR: python_binding.dll not found at {dll_path}")
    sys.exit(1)

print(f"Found DLL: {dll_path}")

# Clean
print("\nCleaning...")
for item in ["build_direct", "dist_direct", "*.spec"]:
    if os.path.exists(item):
        try:
            if os.path.isdir(item):
                shutil.rmtree(item)
            else:
                os.remove(item)
        except:
            pass

# Build with minimal dependencies
print("\nBuilding...")
bump_desktop_gui_version()
cmd = [
    sys.executable, "-m", "PyInstaller",
    "--name=G-Assist-Direct",
    "--onefile",
    "--noconsole",
    f"--add-data={dll_path};rise",
    f"--add-data={rise_path};rise",
    "--hidden-import=rise",
    "--hidden-import=rise.rise",
    "--hidden-import=webview",
    "--hidden-import=logging",
    "--collect-all=webview",
    "--noconfirm",
    "--workpath=build_direct",
    "--distpath=dist_direct",
    "rise-gui-desktop-direct.py"
]

try:
    subprocess.check_call(cmd)
    print("\n" + "="*60)
    print("[OK] Build completed!")
    print("="*60)
    print(f"\nExecutable: {os.path.abspath('dist_direct/G-Assist-Direct.exe')}")
    print(f"Log file: {os.path.join(os.environ['TEMP'], 'gassist_desktop_direct.log')}")
    print("\nFeatures:")
    print("  - Direct Python API (no Flask/HTTP)")
    print("  - WAV file processing")
    print("  - Real-time transcription display")
    print("  - Much simpler and faster!")
except subprocess.CalledProcessError as e:
    print(f"\nERROR: Build failed: {e}")
    sys.exit(1)
