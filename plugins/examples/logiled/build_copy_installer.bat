@echo off
setlocal

echo Building Logitech LED Plugin Copy Installer...
echo.

:: Check if Python is available
where /q python
if ERRORLEVEL 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

:: Install PyInstaller if not already installed
echo Installing PyInstaller...
python -m pip install pyinstaller

:: Build the copy installer executable
echo Creating plugin copy installer executable...
python -m PyInstaller --onefile --name plugin-copy-installer --distpath . plugin-copy-installer.py

if exist plugin-copy-installer.exe (
    echo.
    echo === Plugin Copy Installer created successfully! ===
    echo The installer executable is: plugin-copy-installer.exe
    echo.
    echo This installer can be used to install pre-built plugin files.
    echo.
    echo IMPORTANT: This installer must remain in this directory alongside the plugin files.
    echo.
    echo To install the plugin:
    echo 1. Ensure the C++ plugin is already built (g-assist-plugin-logiled.exe exists)
    echo 2. Right-click on plugin-copy-installer.exe
    echo 3. Select "Run as administrator"
    echo 4. Follow the installation prompts
    echo.
) else (
    echo ERROR: Failed to create installer executable
    exit /b 1
)

pause

