@echo off
setlocal

echo Building Logitech G C++ Plugin Installer...
echo.

:: Check if Python is available
where /q python
if ERRORLEVEL 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python from https://python.org
    echo.
    echo Note: Python is only needed to build the installer executable.
    echo The actual C++ plugin will be built with Visual Studio.
    pause
    exit /b 1
)

:: Install PyInstaller if not already installed
echo Installing PyInstaller...
python -m pip install pyinstaller

:: Build the installer executable
echo Creating installer executable...
python -m PyInstaller --onefile --name logiled-plugin-installer --distpath . installer.py

if exist logiled-plugin-installer.exe (
    echo.
    echo === Logitech G C++ Plugin Installer created successfully! ===
    echo The installer executable is: logiled-plugin-installer.exe
    echo.
    echo IMPORTANT: This installer must remain in this directory alongside the Visual Studio project files.
    echo.
    echo Prerequisites for installation:
    echo 1. Visual Studio 2022 with C++ development tools
    echo 2. Logitech G HUB Gaming Software installed
    echo 3. LED Illumination SDK 9.00 extracted to project directory
    echo 4. JSON for Modern C++ library set up
    echo.
    echo To install the plugin:
    echo 1. Right-click on logiled-plugin-installer.exe
    echo 2. Select "Run as administrator"
    echo 3. Follow the installation prompts
    echo.
    echo The installer will:
    echo - Build the C++ plugin using Visual Studio/MSBuild
    echo - Install to NVIDIA G-Assist adapters directory
    echo - Handle all dependencies automatically
    echo.
) else (
    echo ERROR: Failed to create installer executable
    exit /b 1
)

pause 