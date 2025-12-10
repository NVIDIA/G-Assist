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
from typing import Tuple, Optional
from ctypes import wintypes, byref

# Windows Security Constants for ACL Permissions
SECURITY_DESCRIPTOR_MIN_LENGTH = 20
SECURITY_DESCRIPTOR_REVISION = 1
DACL_SECURITY_INFORMATION = 0x00000004

# Access Rights Constants
FILE_ALL_ACCESS = 0x1F01FF
FILE_GENERIC_READ = 0x120089
FILE_GENERIC_EXECUTE = 0x1200A0

# Windows API Functions
advapi32 = ctypes.windll.advapi32
kernel32 = ctypes.windll.kernel32

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
    
    # Test write permissions to ProgramData plugins directory
    test_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / "NVIDIA Corporation" / "nvtopps" / "rise" / "plugins"
    
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

def get_current_user_sid():
    """Get the SID of the current user using GetUserName and LookupAccountName."""
    try:
        print("Getting current user SID...")
        
        # Get current username
        username_size = wintypes.DWORD(256)
        username = ctypes.create_string_buffer(username_size.value)
        
        if not advapi32.GetUserNameA(username, byref(username_size)):
            error_code = kernel32.GetLastError()
            print(f"Failed to get username, error code: {error_code}")
            return None
        
        current_username = username.value.decode('utf-8')
        print(f"Current username: {current_username}")
        
        # Get SID for the current user
        sid_size = wintypes.DWORD(0)
        domain_size = wintypes.DWORD(0)
        sid_type = wintypes.DWORD()
        
        # Get required buffer sizes
        result = advapi32.LookupAccountNameW(None, current_username, None, byref(sid_size), 
                                           None, byref(domain_size), byref(sid_type))
        
        if sid_size.value == 0:
            print("SID size is 0, this is unexpected")
            return None
        
        # Create buffers
        sid = ctypes.create_string_buffer(sid_size.value)
        domain = ctypes.create_string_buffer(domain_size.value * 2)  # Unicode
        
        # Get the SID
        result = advapi32.LookupAccountNameW(None, current_username, sid, byref(sid_size),
                                           domain, byref(domain_size), byref(sid_type))
        
        if result:
            print("Current user SID retrieved successfully")
            # Return the buffer itself, not the pointer value
            return sid
        else:
            error_code = kernel32.GetLastError()
            print(f"LookupAccountNameW failed with error code: {error_code}")
            return None
        
    except Exception as e:
        print(f"Exception in get_current_user_sid: {e}")
        return None

def get_administrators_sid():
    """Get the SID for the local Administrators group."""
    try:
        print("Getting Administrators group SID...")
        
        # Create SID for BUILTIN\Administrators
        sid_size = wintypes.DWORD(0)
        domain_size = wintypes.DWORD(0)
        sid_type = wintypes.DWORD()
        
        # Get required buffer sizes
        result = advapi32.LookupAccountNameW(None, "Administrators", None, byref(sid_size), 
                                           None, byref(domain_size), byref(sid_type))
        
        if sid_size.value == 0:
            print("SID size is 0, this is unexpected")
            return None
        
        # Create buffers
        sid = ctypes.create_string_buffer(sid_size.value)
        domain = ctypes.create_string_buffer(domain_size.value * 2)  # Unicode
        
        # Get the SID
        result = advapi32.LookupAccountNameW(None, "Administrators", sid, byref(sid_size),
                                           domain, byref(domain_size), byref(sid_type))
        
        if result:
            print("Administrators SID retrieved successfully")
            # Return the buffer itself, not the pointer value
            return sid
        else:
            error_code = kernel32.GetLastError()
            print(f"LookupAccountNameW failed with error code: {error_code}")
            return None
        
    except Exception as e:
        print(f"Exception in get_administrators_sid: {e}")
        return None

def create_restricted_security_descriptor():
    """
    Create a security descriptor with restricted ACL permissions.
    This replicates the behavior of setupSecurityDescriptor() from the C++ code.
    """
    try:
        print("Creating restricted security descriptor...")
        
        # Allocate security descriptor - use a larger buffer to be safe
        sd_size = 1024  # Much larger than minimum to avoid buffer issues
        pSD = ctypes.create_string_buffer(sd_size)
        if not pSD:
            print("Failed to allocate security descriptor")
            return None, None
        
        # Initialize security descriptor
        if not advapi32.InitializeSecurityDescriptor(ctypes.byref(pSD), SECURITY_DESCRIPTOR_REVISION):
            print("Failed to initialize security descriptor")
            return None, None
        
        # Create ACL with restricted permissions
        acl_size = 1024  # Conservative size for ACL with multiple ACEs
        pACL = ctypes.create_string_buffer(acl_size)
        if not pACL:
            print("Failed to allocate ACL")
            return None, None
        
        # Initialize ACL
        if not advapi32.InitializeAcl(ctypes.byref(pACL), acl_size, 2):  # ACL_REVISION = 2
            print("Failed to initialize ACL")
            return None, None
        
        # Get SIDs for current user and administrators
        user_sid = get_current_user_sid()
        admin_sid = get_administrators_sid()
        
        if not user_sid or not admin_sid:
            print("Failed to get required SIDs")
            return None, None
        
        # Add ACE for current user (limited permissions - read/execute only)
        restricted_access = FILE_GENERIC_READ | FILE_GENERIC_EXECUTE
        if not advapi32.AddAccessAllowedAce(ctypes.byref(pACL), 2, restricted_access, ctypes.byref(user_sid)):
            error_code = kernel32.GetLastError()
            print(f"Failed to add user ACE, error code: {error_code}")
            return None, None
        
        # Add ACE for administrators (full control)
        if not advapi32.AddAccessAllowedAce(ctypes.byref(pACL), 2, FILE_ALL_ACCESS, ctypes.byref(admin_sid)):
            error_code = kernel32.GetLastError()
            print(f"Failed to add admin ACE, error code: {error_code}")
            return None, None
        
        # Set DACL in security descriptor
        if not advapi32.SetSecurityDescriptorDacl(ctypes.byref(pSD), True, ctypes.byref(pACL), False):
            error_code = kernel32.GetLastError()
            print(f"Failed to set DACL in security descriptor, error code: {error_code}")
            return None, None
        
        print("Security descriptor created successfully")
        # Return the buffer objects themselves, not raw pointers
        return pSD, pACL
    
    except Exception as e:
        print(f"Exception in create_restricted_security_descriptor: {e}")
        return None, None

def set_file_acl_permissions(file_path: str, pSD) -> bool:
    """
    Set ACL permissions on a specific file.
    This replicates setFilePermissions() from the C++ code.
    """
    try:
        # Convert to bytes for Windows API
        file_path_bytes = str(file_path).encode('utf-8')
        
        # Apply security descriptor to file
        result = advapi32.SetFileSecurityA(
            file_path_bytes,
            DACL_SECURITY_INFORMATION,
            ctypes.byref(pSD)
        )
        
        if not result:
            error_code = kernel32.GetLastError()
            print(f"Failed to set file security for {file_path}, error code: {error_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"Exception setting file ACL for {file_path}: {e}")
        return False

def remove_existing_dacl(file_path: str) -> bool:
    """
    Remove existing DACL from a file by setting a NULL DACL.
    This replicates the NULL DACL removal from the C++ code.
    """
    try:
        # Create null security descriptor using ctypes buffer
        pNullSD = ctypes.create_string_buffer(1024)  # Use larger buffer like main function
        if not pNullSD:
            print("Failed to allocate null security descriptor")
            return False
        
        # Initialize null security descriptor
        if not advapi32.InitializeSecurityDescriptor(ctypes.byref(pNullSD), SECURITY_DESCRIPTOR_REVISION):
            print("Failed to initialize null security descriptor")
            return False
        
        # Set NULL DACL (removes existing DACLs)
        if not advapi32.SetSecurityDescriptorDacl(ctypes.byref(pNullSD), True, None, False):
            print("Failed to set NULL DACL")
            return False
        
        # Apply null security descriptor to remove existing DACL
        file_path_bytes = str(file_path).encode('utf-8')
        result = advapi32.SetFileSecurityA(
            file_path_bytes,
            DACL_SECURITY_INFORMATION,
            ctypes.byref(pNullSD)
        )
        
        if not result:
            error_code = kernel32.GetLastError()
            print(f"Failed to remove existing DACL for {file_path}, error code: {error_code}")
            return False
        
        return True
        
    except Exception as e:
        print(f"Exception removing DACL for {file_path}: {e}")
        return False

def set_plugin_acl_permissions(plugin_directory: Path) -> Tuple[bool, Optional[str]]:
    """
    Set ACL permissions on all files in a plugin directory.
    This is the Python equivalent of DependencyManager::setAclPermissionsPlugins().
    
    Args:
        plugin_directory (Path): Path to the installed plugin directory
        
    Returns:
        Tuple[bool, Optional[str]]: (success, error_message)
    """
    try:
        # Create restricted security descriptor
        pSD, pACL = create_restricted_security_descriptor()
        if not pSD or not pACL:
            return False, "Failed to create restricted security descriptor"
        
        try:
            # Recursively set permissions on all files in the plugin directory
            file_count = 0
            for file_path in plugin_directory.rglob('*'):
                if file_path.is_file():
                    # Remove existing DACL
                    if not remove_existing_dacl(str(file_path)):
                        return False, f"Failed to remove existing DACLs for file: {file_path}"
                    
                    # Apply new restricted DACL
                    if not set_file_acl_permissions(str(file_path), pSD):
                        return False, f"Failed to set ACL permissions for file: {file_path}"
                    
                    file_count += 1
            
            print(f"Applied ACL permissions to {file_count} file(s)")
            return True, None
            
        finally:
            # Clean up allocated memory - ctypes buffers are automatically cleaned up
            # No manual cleanup needed for ctypes.create_string_buffer objects
            pass
    
    except Exception as e:
        error_msg = f"Exception in set_plugin_acl_permissions: {e}"
        print(error_msg)
        return False, error_msg

def install_cpp_plugin(plugin_name):
    """Install the C++ plugin to the NVIDIA G-Assist plugins directory."""
    print("Installing C++ plugin...")
    
    # Define target directory
    target_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / "NVIDIA Corporation" / "nvtopps" / "rise" / "plugins"
    
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
    
    # Apply ACL security restrictions to installed plugin files
    print("\nApplying security restrictions to plugin files...")
    success, error = set_plugin_acl_permissions(target_plugin_dir)
    if not success:
        print(f"ERROR: Failed to apply security restrictions: {error}")
        print("SECURITY BREACH PREVENTION: Removing insecure plugin files...")
        
        # Remove the entire plugin directory to prevent insecure loading
        try:
            shutil.rmtree(target_plugin_dir)
            print(f"✓ Insecure plugin directory removed: {target_plugin_dir}")
            print("Installation failed due to security restrictions failure.")
            print("This prevents potentially vulnerable plugin files from being loaded.")
            raise Exception("Plugin installation failed: Unable to apply required security restrictions")
        except Exception as cleanup_error:
            print(f"ERROR: Could not remove insecure plugin directory: {cleanup_error}")
            print("SECURITY WARNING: Insecure plugin files may still exist!")
            print("\n⚠️  MANUAL CLEANUP REQUIRED:")
            print(f"Please manually delete this directory: {target_plugin_dir}")
            print("1. Open File Explorer as Administrator")
            print("2. Navigate to the directory above")
            print("3. Delete the entire plugin folder")
            print("4. This prevents the insecure plugin from being loaded by G-Assist")
            raise Exception(f"Critical security failure: Plugin installed but could not be secured or removed")
    else:
        print("✓ Security restrictions applied successfully")

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
        print("\nNote: The plugin has been secured with restricted ACL permissions.")
        print("Only administrators can modify the plugin files.")
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