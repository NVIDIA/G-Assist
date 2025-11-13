@echo off
REM Build and Deploy All G-Assist Plugins
REM This script runs the PowerShell script with default parameters

echo ========================================
echo G-Assist Plugin Builder ^& Deployer
echo ========================================
echo.

REM Check if PowerShell is available
where pwsh >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo Using PowerShell Core...
    pwsh -ExecutionPolicy Bypass -File "%~dp0build_and_deploy_all.ps1" %*
) else (
    echo Using Windows PowerShell...
    powershell -ExecutionPolicy Bypass -File "%~dp0build_and_deploy_all.ps1" %*
)

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Build failed! Check the output above for errors.
    pause
    exit /b 1
)

echo.
echo All plugins built and deployed successfully!
pause

