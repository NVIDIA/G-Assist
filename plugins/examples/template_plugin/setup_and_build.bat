@echo off
setlocal ENABLEDELAYEDEXPANSION

REM ============================================================================
REM Unified setup + build script for the template plugin
REM  - Creates a local venv (.\.venv)
REM  - Installs dependencies from requirements.txt
REM  - Builds a standalone EXE via PyInstaller
REM  - Copies manifest/config into the dist folder so it can be deployed directly
REM ============================================================================

set SCRIPT_DIR=%~dp0
set VENV_DIR=%SCRIPT_DIR%\.venv
set PYTHON_EXE=python

if not exist "%VENV_DIR%\Scripts\python.exe" (
    echo [SETUP] Creating virtual environment...
    "%PYTHON_EXE%" -m venv "%VENV_DIR%" || goto :error
)

echo [SETUP] Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat" || goto :error

echo [SETUP] Upgrading pip...
python -m pip install --upgrade pip >nul || goto :error

echo [SETUP] Installing requirements...
python -m pip install -r "%SCRIPT_DIR%\requirements.txt" || goto :error

echo [BUILD] Cleaning previous artifacts...
if exist "%SCRIPT_DIR%\build" rd /s /q "%SCRIPT_DIR%\build"
if exist "%SCRIPT_DIR%\dist" rd /s /q "%SCRIPT_DIR%\dist"

echo [BUILD] Running PyInstaller...
pyinstaller ^
    --clean ^
    --onefile ^
    --name g-assist-plugin-template ^
    "%SCRIPT_DIR%\plugin.py" || goto :error

set DIST_DIR=%SCRIPT_DIR%\dist\g-assist-plugin-template
if not exist "%DIST_DIR%" (
    echo [BUILD] ERROR: Expected dist folder "%DIST_DIR%" not found.
    goto :error
)

echo [DEPLOY] Copying manifest and config...
copy /Y "%SCRIPT_DIR%\manifest.json" "%DIST_DIR%\manifest.json" >nul || goto :error
copy /Y "%SCRIPT_DIR%\config.json" "%DIST_DIR%\config.json" >nul || goto :error

echo.
echo [SUCCESS] Build complete. Deploy contents of:
echo          %DIST_DIR%
goto :eof

:error
echo [FAILED] Setup or build step encountered an error.
exit /b 1

