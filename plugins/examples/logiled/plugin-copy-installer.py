#!/usr/bin/env python3
"""
Plugin Copy Installer for Logitech LED Plugin
This script runs with administrator privileges to install pre-built plugins
to the NVIDIA G-Assist adapters directory.
"""

import os
import sys
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
    
    # Use ShellExecute to run as administrator (no arguments needed)
    try:
        result = ctypes.windll.shell32.ShellExecuteW(
            None,  # hwnd
            "runas",  # operation
            script_path,  # file
            None,  # parameters (none needed - we auto-detect from working directory)
            None,  # directory
            1  # show command
        )
        
        if result > 32:  # Success
            return True
        else:
            return False
    except Exception as e:
        print(f"Failed to elevate privileges: {e}")
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

def install_plugin_with_admin(plugin_name: str, source_path: str) -> Tuple[bool, Optional[str]]:
    """
    Install a plugin to the NVIDIA G-Assist plugins directory with admin privileges.
    
    Args:
        plugin_name (str): Name of the plugin to install
        source_path (str): Path to the plugin files
    
    Returns:
        Tuple[bool, Optional[str]]: (success, error_message)
    """
    try:
        source_path = Path(source_path)
        if not source_path.exists():
            return False, f"Source path does not exist: {source_path}"
        
        # Define target directory in NVIDIA plugins folder
        target_plugins_dir = Path(os.environ.get('PROGRAMDATA', 'C:\\ProgramData')) / "NVIDIA Corporation" / "nvtopps" / "rise" / "plugins"
        target_plugin_dir = target_plugins_dir / plugin_name
        
        print(f"Installing plugin '{plugin_name}' from {source_path} to {target_plugin_dir}")
        
        # Create target plugin directory if it doesn't exist
        target_plugin_dir.mkdir(parents=True, exist_ok=True)
        print(f"Created/verified target directory: {target_plugin_dir}")
        
        # Look for required files
        plugin_exe_names = [
            f"g-assist-plugin-{plugin_name}.exe",
            f"g-assist-{plugin_name}-plugin.exe",
            f"{plugin_name}-plugin.exe"
        ]
        
        plugin_exe = None
        manifest_json = source_path / "manifest.json"
        
        # Find the plugin executable
        for exe_name in plugin_exe_names:
            potential_exe = source_path / exe_name
            if potential_exe.exists():
                plugin_exe = potential_exe
                print(f"Found plugin executable: {plugin_exe}")
                break
        
        # If not found in main directory, check x64/Release subdirectory (Visual Studio output)
        if not plugin_exe:
            vs_release_path = source_path / "x64" / "Release"
            if vs_release_path.exists():
                print(f"Checking x64/Release subdirectory for required files")
                for exe_name in plugin_exe_names:
                    vs_plugin_exe = vs_release_path / exe_name
                    if vs_plugin_exe.exists():
                        plugin_exe = vs_plugin_exe
                        print(f"Found plugin executable in x64/Release: {plugin_exe}")
                        break
        
        if not plugin_exe:
            return False, f"Plugin executable not found for '{plugin_name}'"
        
        if not manifest_json.exists():
            return False, f"manifest.json not found for '{plugin_name}'"
        
        # Copy required files
        shutil.copy2(plugin_exe, target_plugin_dir)
        shutil.copy2(manifest_json, target_plugin_dir)
        print(f"Copied {plugin_exe.name} and manifest.json to target directory")
        
        # Handle optional files (config.json)
        optional_files = ["config.json"]
        copied_optional = []
        
        for optional_file in optional_files:
            source_file = source_path / optional_file
            if source_file.exists():
                shutil.copy2(source_file, target_plugin_dir)
                copied_optional.append(optional_file)
                print(f"Copied optional file: {optional_file}")
        
        optional_msg = f" (also copied: {', '.join(copied_optional)})" if copied_optional else ""
        print(f"Plugin '{plugin_name}' files copied successfully{optional_msg}")
        
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
            except Exception as cleanup_error:
                print(f"ERROR: Could not remove insecure plugin directory: {cleanup_error}")
                print("SECURITY WARNING: Insecure plugin files may still exist!")
                print("\n⚠️  MANUAL CLEANUP REQUIRED:")
                print(f"Please manually delete this directory: {target_plugin_dir}")
                print("1. Open File Explorer as Administrator")
                print("2. Navigate to the directory above")
                print("3. Delete the entire plugin folder")
                print("4. This prevents the insecure plugin from being loaded by G-Assist")
                return False, f"Critical security failure: Plugin installed but could not be secured or removed"
            
            # If cleanup succeeded, raise the security failure exception
            return False, f"Plugin installation failed: Unable to apply required security restrictions"
        else:
            print("✓ Security restrictions applied successfully")
        
        print(f"Plugin '{plugin_name}' installed successfully")
        return True, None
        
    except PermissionError as e:
        return False, f"Permission denied: {e}. Please ensure you're running as Administrator."
    except Exception as e:
        return False, f"Installation failed: {e}"

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
    
    # Method 3: Try to extract from executable name in manifest (backup)
    if manifest_file.exists():
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
                if 'executable' in manifest:
                    executable = manifest['executable']
                    
                    # Remove .exe extension
                    if executable.endswith('.exe'):
                        executable = executable[:-4]
                    
                    # Handle different naming patterns:
                    # Pattern 1: "g-assist-plugin-{name}" -> extract {name}
                    if executable.startswith('g-assist-plugin-'):
                        name_part = executable[16:]  # Remove "g-assist-plugin-"
                        print(f"Note: Using plugin name '{name_part}' from executable pattern 'g-assist-plugin-{name_part}.exe'")
                        return name_part
                    
                    # Pattern 2: "g-assist-{name}-plugin" -> extract {name}
                    elif executable.startswith('g-assist-') and executable.endswith('-plugin'):
                        name_part = executable[9:-7]  # Remove "g-assist-" and "-plugin"
                        print(f"Note: Using plugin name '{name_part}' from executable pattern 'g-assist-{name_part}-plugin.exe'")
                        return name_part
                    
                    # Pattern 3: "{name}-plugin" -> extract {name}
                    elif executable.endswith('-plugin'):
                        name_part = executable[:-7]  # Remove "-plugin"
                        print(f"Note: Using plugin name '{name_part}' from executable pattern '{name_part}-plugin.exe'")
                        return name_part
        except (json.JSONDecodeError, KeyError):
            pass
    
    return plugin_name

def main():
    """Main entry point for the plugin copy installer."""
    # Auto-detect plugin name and source path from installer directory
    installer_dir = get_installer_directory()
    plugin_name = detect_plugin_name()
    source_path = str(installer_dir)
    
    print(f"Plugin Copy Installer - Installing '{plugin_name}'")
    print(f"Source path: {source_path}")
    print(f"Installer directory: {installer_dir}")
    
    # Check if we have admin privileges
    if not is_admin():
        print("This script requires administrator privileges to install plugins.")
        print("Attempting to elevate privileges...")
        
        if elevate_privileges():
            print("Please approve the UAC prompt to continue installation.")
            sys.exit(0)  # Exit this instance, elevated instance will continue
        else:
            print("Failed to elevate privileges. Please run this script as Administrator.")
            input("Press Enter to exit...")
            sys.exit(1)
    
    print("Running with administrator privileges ✓")
    
    # Install the plugin
    success, error_message = install_plugin_with_admin(plugin_name, source_path)
    
    if success:
        print(f"\n=== Installation Complete! ===")
        print(f"The '{plugin_name}' plugin has been successfully installed to the NVIDIA G-Assist adapters directory.")
        print("Please restart G-Assist to use the plugin.")
        # Exit automatically on success
    else:
        print(f"\n=== Installation Failed ===")
        print(f"Error: {error_message}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()

