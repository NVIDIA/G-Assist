@echo off
setlocal enabledelayedexpansion

:: Set default variables
set PLUGIN_NAME=find_my_mcp
set PYTHON=python
set DIST_DIR=..\..\..\dist

:: Validate manifest.json before building
echo Validating manifest.json...
%PYTHON% -m json.tool manifest.json >nul 2>&1
if ERRORLEVEL 1 (
	echo ERROR: manifest.json is not valid JSON!
	echo Please fix the JSON syntax errors before building.
	exit /b 1
)
echo manifest.json is valid.

:: Build the plugin using PyInstaller
echo Building %PLUGIN_NAME%...
pyinstaller --onefile --name g-assist-plugin-%PLUGIN_NAME% --distpath "%DIST_DIR%\%PLUGIN_NAME%" plugin.py

:: Copy configuration and manifest
echo Copying manifest.json...
copy manifest.json "%DIST_DIR%\%PLUGIN_NAME%\" >nul
if exist config.json (
    echo Copying config.json...
    copy config.json "%DIST_DIR%\%PLUGIN_NAME%\" >nul
)

echo Build complete for %PLUGIN_NAME%.
endlocal

