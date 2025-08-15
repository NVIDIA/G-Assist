#!/usr/bin/env python3
"""
Logitech G C++ Plugin Installer
This script builds the C++ plugin using Visual Studio and installs it to the NVIDIA G-Assist adapters directory.
Requires administrator privileges to install to %PROGRAMDATA%.

IMPORTANT: This installer executable must be placed in the same directory as the Visual Studio solution files.
"""

import os
import sys
import subprocess
import shutil
import ctypes
import json
from pathlib import Path

def is_admin():
    """Check if the script is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def elevate_privileges():
    """Restart the script with administrator privileges."""
    if is_admin():
        return False  # Already running as admin
    
    # Get the script path
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        script_path = sys.executable
    else:
        # Running as Python script
        script_path = sys.argv[0]
    
    # Use ShellExecute to run as administrator
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,  # hwnd
            "runas",  # operation
            script_path,  # file
            None,  # parameters
            None,  # directory
            1  # show command
        )
        
        if result > 32:  # Success
            print("Restarting with administrator privileges...")
            sys.exit(0)
        else:
            return False
    except Exception as e:
        print(f"Failed to elevate privileges: {e}")
        return False

def verify_admin_and_permissions():
    """Verify administrator privileges and test write permissions."""
    if not is_admin():
        return False, "Not running as Administrator"
    
    # Test write permissions to ProgramData adapters directory
    test_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / "NVIDIA Corporation" / "nvtopps" / "rise" / "adapters"
    
    try:
        # Try to create the directory
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Try to create a test file
        test_file = test_dir / "test_write_permission.tmp"
        test_file.write_text("test")
        test_file.unlink()  # Clean up
        
        return True, "Administrator privileges and write permissions verified"
    except PermissionError as e:
        return False, f"Write permission denied: {e}"
    except Exception as e:
        return False, f"Permission test failed: {e}"

def get_installer_directory():
    """Get the directory where the installer executable is located."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable
        return Path(sys.executable).parent
    else:
        # Running as Python script
        return Path(__file__).parent

def detect_plugin_name():
    """Detect the plugin name from the directory structure or manifest."""
    installer_dir = get_installer_directory()
    
    # Method 1: Use the directory name as the primary plugin name
    plugin_name = installer_dir.name
    
    # Method 2: Try to read from manifest.json if it has a name field (backup)
    manifest_file = installer_dir / "manifest.json"
    if manifest_file.exists():
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
                if 'name' in manifest:
                    print(f"Note: Using plugin name '{manifest['name']}' from manifest.json instead of directory name '{plugin_name}'")
                    return manifest['name']
        except (json.JSONDecodeError, KeyError):
            pass
    
    return plugin_name

def run_command(cmd, cwd=None, check=True):
    """Run a command and return the result."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    if check and result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result

def check_visual_studio():
    """Check if Visual Studio is available."""
    # Check for MSBuild in common locations
    possible_paths = [
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\MSBuild\Current\Bin\MSBuild.exe",
        r"C:\Program Files\Microsoft Visual Studio\2022\Professional\MSBuild\Current\Bin\MSBuild.exe",
        r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\MSBuild\Current\Bin\MSBuild.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\MSBuild\Current\Bin\MSBuild.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Current\Bin\MSBuild.exe",
    ]
    
    for path in possible_paths:
        if Path(path).exists():
            return path
    
    # Try to find MSBuild in PATH
    try:
        result = subprocess.run(['msbuild', '/version'], capture_output=True, text=True)
        if result.returncode == 0:
            return 'msbuild'
    except FileNotFoundError:
        pass
    
    return None

def build_cpp_plugin(plugin_name):
    """Build the C++ plugin using Visual Studio/MSBuild."""
    print("Building C++ plugin...")
    
    installer_dir = get_installer_directory()
    solution_file = installer_dir / f"{plugin_name}.sln"
    
    if not solution_file.exists():
        print(f"ERROR: Visual Studio solution file not found: {solution_file}")
        print("Please ensure you have the complete plugin source code.")
        return False
    
    # Check for MSBuild
    msbuild_path = check_visual_studio()
    if not msbuild_path:
        print("ERROR: Visual Studio/MSBuild not found.")
        print("Please install Visual Studio 2022 or ensure MSBuild is in your PATH.")
        print("You can download Visual Studio from: https://visualstudio.microsoft.com/")
        return False
    
    print(f"Found MSBuild: {msbuild_path}")
    
    try:
        # Build the solution in Release configuration
        if msbuild_path == 'msbuild':
            cmd = f'msbuild "{solution_file}" /p:Configuration=Release /p:Platform=x64'
        else:
            cmd = f'"{msbuild_path}" "{solution_file}" /p:Configuration=Release /p:Platform=x64'
        
        run_command(cmd, cwd=installer_dir)
        print("C++ plugin built successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Build failed: {e}")
        print("\nThis is likely due to missing dependencies. Please check:")
        print("1. Visual Studio 2022 with C++ development tools")
        print("2. Required SDKs:")
        if plugin_name == "corsair":
            print("   - iCUE SDK v4.0.84 (extract to 'iCUESDK' folder)")
            print("   - Download from: https://github.com/CorsairOfficial/cue-sdk/releases")
        elif plugin_name == "logiled":
            print("   - LED Illumination SDK 9.00 (extract to project directory)")
            print("   - Download from: https://www.logitechg.com/en-us/innovation/developer-lab.html")
        print("3. JSON for Modern C++ library (extract to 'json' folder)")
        print("   - Download from: https://github.com/nlohmann/json/releases")
        
        # Check if there's already a built executable
        executable_name = f"g-assist-plugin-{plugin_name}.exe"
        possible_locations = [
            installer_dir / "x64" / "Release" / executable_name,
            installer_dir / "Release" / executable_name,
            installer_dir / "Debug" / executable_name,
            installer_dir / executable_name,
        ]
        
        existing_executable = None
        for location in possible_locations:
            if location.exists():
                existing_executable = location
                break
        
        if existing_executable:
            print(f"\nFound existing built executable: {existing_executable}")
            print("Using existing executable for installation.")
            return True
        
        print("\nTo install dependencies:")
        print("1. Download the required SDKs")
        print("2. Extract them to the project directory")
        print("3. Run the installer again")
        print("\nOr build the plugin manually in Visual Studio and run the installer again.")
        
        return False

def install_cpp_plugin(plugin_name):
    """Install the C++ plugin to the NVIDIA G-Assist adapters directory."""
    print("Installing C++ plugin...")
    
    # Define target directory (adapters instead of plugins for C++ plugins)
    target_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / "NVIDIA Corporation" / "nvtopps" / "rise" / "adapters"
    
    print(f"Target directory: {target_dir}")
    
    # Create target directory if it doesn't exist
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        print(f"Target directory created/verified: {target_dir}")
    except PermissionError as e:
        print(f"ERROR: Cannot create target directory: {e}")
        print("Please ensure you're running as Administrator and the directory is writable.")
        raise
    
    # Copy plugin files from the installer directory
    installer_dir = get_installer_directory()
    
    # Look for the built executable
    executable_name = f"g-assist-plugin-{plugin_name}.exe"
    possible_locations = [
        installer_dir / "x64" / "Release" / executable_name,
        installer_dir / "Release" / executable_name,
        installer_dir / "Debug" / executable_name,
        installer_dir / executable_name,
    ]
    
    executable_path = None
    for location in possible_locations:
        if location.exists():
            executable_path = location
            break
    
    if not executable_path:
        raise FileNotFoundError(f"Plugin executable not found. Looked in: {[str(p) for p in possible_locations]}")
    
    print(f"Found plugin executable: {executable_path}")
    
    # Copy the entire plugin folder to the adapters directory
    target_plugin_dir = target_dir / plugin_name
    
    # Create target directory if it doesn't exist
    target_plugin_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy/replace files in the plugin directory
    try:
        print(f"Updating {plugin_name} files in {target_plugin_dir}...")
        
        # Copy the executable
        target_executable = target_plugin_dir / executable_name
        shutil.copy2(executable_path, target_executable)
        print(f"  Updated: {executable_name}")
        
        # Copy manifest.json if it exists
        manifest_source = installer_dir / "manifest.json"
        if manifest_source.exists():
            manifest_target = target_plugin_dir / "manifest.json"
            shutil.copy2(manifest_source, manifest_target)
            print(f"  Updated: manifest.json")
        
        print(f"Successfully updated {plugin_name} files")
        
    except PermissionError as e:
        print(f"ERROR: Cannot update plugin files: {e}")
        print("Please ensure you're running as Administrator and close any applications using the plugin.")
        raise
    except Exception as e:
        print(f"ERROR: Failed to update plugin files: {e}")
        raise
    
    print(f"Plugin installed successfully to {target_dir}")

def main():
    """Main installation process."""
    # Detect plugin name
    plugin_name = detect_plugin_name()
    
    print(f"=== G-Assist {plugin_name} C++ Plugin Installer ===")
    print("This installer will:")
    print("1. Build the C++ plugin using Visual Studio/MSBuild")
    print("2. Install the plugin to NVIDIA G-Assist adapters directory")
    print()
    
    try:
        # Get the installer directory
        installer_dir = get_installer_directory()
        print(f"Installer directory: {installer_dir}")
        print(f"Detected plugin name: {plugin_name}")
        
        # Verify required files exist
        required_files = [f"{plugin_name}.sln", f"{plugin_name}.vcxproj", "manifest.json"]
        missing_files = []
        
        for file in required_files:
            if not (installer_dir / file).exists():
                missing_files.append(file)
        
        if missing_files:
            print(f"ERROR: Missing required files: {', '.join(missing_files)}")
            print(f"Please ensure the installer executable is in the same directory as the Visual Studio project files.")
            print(f"Required files: {', '.join(required_files)}")
            input("Press Enter to exit...")
            sys.exit(1)
        
        # Step 1: Build C++ plugin (no admin needed)
        if not build_cpp_plugin(plugin_name):
            print("Build failed. Please check the error messages above.")
            input("Press Enter to exit...")
            sys.exit(1)
        
        # Step 2: Check admin privileges only for installation
        print("\nChecking administrator privileges for installation...")
        admin_ok, admin_message = verify_admin_and_permissions()
        if not admin_ok:
            print(f"ERROR: {admin_message}")
            print("\nAttempting to restart with administrator privileges for installation...")
            
            if elevate_privileges():
                print("Please approve the UAC prompt to continue installation.")
                print("The installer will restart automatically with elevated privileges.")
            else:
                print("\nAutomatic elevation failed. Please try:")
                print("1. Right-click the installer and select 'Run as Administrator'")
                print("2. If that doesn't work, try running Command Prompt as Administrator and run the installer from there")
                print("3. Check if your antivirus is blocking the installer")
                print("4. Ensure the NVIDIA G-Assist adapters directory is not read-only")
                input("Press Enter to exit...")
                sys.exit(1)
            
            # If we get here, elevation was successful and we're restarting
            return
        
        print("✓ Administrator privileges and permissions verified")
        
        # Step 3: Install plugin (requires admin)
        install_cpp_plugin(plugin_name)
        
        print("\n=== Installation Complete! ===")
        print(f"The G-Assist {plugin_name} C++ plugin has been successfully installed.")
        print("You can now use it with NVIDIA G-Assist.")
        print("\nInstallation successful! Window will close automatically in 3 seconds...")
        import time
        time.sleep(3)
        return
        
    except Exception as e:
        print(f"\nERROR: Installation failed: {e}")
        print("Please check the error messages above and try again.")
        # Keep window open on error so user can read the error
        print("\nPress Enter to exit...")
        input()

if __name__ == "__main__":
    main() 