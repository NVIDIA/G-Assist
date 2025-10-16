"""
Build script to create a standalone G-Assist Desktop executable with native window
"""
import os
import sys
import subprocess
import shutil

def main():
    print("=" * 60)
    print("Building G-Assist Desktop Executable (Native Window)")
    print("=" * 60)
    
    # Check if PyInstaller is installed
    try:
        import PyInstaller
        print(f"[OK] PyInstaller found: {PyInstaller.__version__}")
    except ImportError:
        print("[!] PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("[OK] PyInstaller installed successfully")
    
    # Install dependencies
    print("\nInstalling dependencies...")
    dependencies = ["pywebview", "waitress", "psutil"]
    for dep in dependencies:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
            print(f"[OK] {dep} installed")
        except:
            print(f"[WARNING] {dep} installation failed, but continuing...")
    
    # Ensure the rise package is installed
    print("\nInstalling rise package in development mode...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", "."])
    print("[OK] Rise package installed")
    
    # Find the python_binding.dll location
    import rise
    rise_path = os.path.dirname(rise.__file__)
    dll_path = os.path.join(rise_path, "python_binding.dll")
    
    if not os.path.exists(dll_path):
        print(f"[ERROR] python_binding.dll not found at {dll_path}")
        sys.exit(1)
    
    print(f"[OK] Found python_binding.dll at: {dll_path}")
    
    # Clean previous builds
    print("\nCleaning previous builds...")
    for dir_name in ["build", "dist_desktop"]:
        if os.path.exists(dir_name):
            try:
                shutil.rmtree(dir_name)
                print(f"  Removed {dir_name}/")
            except:
                print(f"  Could not remove {dir_name}/ (may be in use)")
    
    if os.path.exists("G-Assist-Desktop.spec"):
        os.remove("G-Assist-Desktop.spec")
        print("  Removed G-Assist-Desktop.spec")
    
    # Build PyInstaller command - Desktop mode with --desktop flag
    print("\nBuilding desktop executable with PyInstaller...")
    
    pyinstaller_args = [
        "pyinstaller",
        "--name=G-Assist-Desktop",
        "--onefile",  # Single executable file
        "--noconsole",  # No console window (GUI only)
        "--icon=NONE",  # Add icon path here if you have one
        f"--add-data={dll_path};rise",  # Include the DLL
        f"--add-data={rise_path};rise",  # Include the rise package
        "--add-data=rise-gui.py;.",  # Include rise-gui.py for the launcher
        "--hidden-import=rise",
        "--hidden-import=rise.rise",
        "--hidden-import=flask",
        "--hidden-import=flask_cors",
        "--hidden-import=waitress",
        "--hidden-import=tqdm",
        "--hidden-import=colorama",
        "--hidden-import=webview",
        "--hidden-import=webview.platforms.winforms",
        "--hidden-import=clr",
        "--hidden-import=System",
        "--hidden-import=json",
        "--hidden-import=threading",
        "--hidden-import=inspect",
        "--hidden-import=re",
        "--hidden-import=argparse",
        "--hidden-import=importlib.util",
        "--hidden-import=logging",
        "--hidden-import=warnings",
        "--hidden-import=psutil",
        "--hidden-import=tempfile",
        "--hidden-import=atexit",
        "--collect-all=flask",
        "--collect-all=flask_cors",
        "--collect-all=webview",
        "--collect-all=pythonnet",
        "--collect-all=waitress",
        "--noconfirm",  # Overwrite output directory without confirmation
        "--distpath=dist_desktop",
        "rise-gui-desktop-launcher.py"
    ]
    
    print(f"  Command: {' '.join(pyinstaller_args)}")
    print()
    
    try:
        subprocess.check_call(pyinstaller_args)
        print("\n" + "=" * 60)
        print("[OK] Build completed successfully!")
        print("=" * 60)
        print(f"\nExecutable location: {os.path.abspath('dist_desktop/G-Assist-Desktop.exe')}")
        print("\nThis executable:")
        print("  - Runs in a native desktop window (no browser)")
        print("  - Includes all dependencies and the rise module")
        print("  - Can be run on any Windows machine without Python")
        print("\nTo run:")
        print("  Simply double-click the executable")
        print("\nNote: If webview doesn't work, it will fall back to browser mode")
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] Build failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

