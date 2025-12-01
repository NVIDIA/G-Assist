:: Shared setup script for all G-Assist plugins
:: Usage: setup.bat <plugin-name|all> [-deploy]
@echo off
setlocal EnableDelayedExpansion

set EXAMPLES_DIR=%~dp0
set SDK_DIR=%EXAMPLES_DIR%..\sdk\python
set RISE_PYTHON=%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\python\python.exe
set DEPLOY_BASE=%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins

:: Check for help flag
if "%~1"=="" goto show_help
if "%~1"=="-h" goto show_help
if "%~1"=="--help" goto show_help
if "%~1"=="-?" goto show_help
if "%~1"=="/?" goto show_help

:: Get plugin name and deploy flag
set PLUGIN_NAME=%~1
set DEPLOY=0
if "%~2"=="-deploy" set DEPLOY=1
if "%~2"=="--deploy" set DEPLOY=1

:: Determine if we have 'python' or 'python3' in the path
where /q python
if ERRORLEVEL 1 goto python3
set PYTHON=python
goto check_version

:python3
where /q python3
if ERRORLEVEL 1 goto nopython
set PYTHON=python3

:check_version
:: Get current Python version
for /f "tokens=2" %%v in ('%PYTHON% --version 2^>^&1') do set CURRENT_VERSION=%%v

echo.
echo ============================================================
echo G-Assist Plugin Setup
echo ============================================================
echo.
echo Using Python: %PYTHON% (version %CURRENT_VERSION%)

:: Check if RISE embedded Python exists and compare versions
if exist "%RISE_PYTHON%" (
    for /f "tokens=2" %%v in ('"%RISE_PYTHON%" --version 2^>^&1') do set RISE_VERSION=%%v
    
    echo RISE embedded Python: !RISE_VERSION!
    
    :: Compare major.minor versions
    for /f "tokens=1,2 delims=." %%a in ("%CURRENT_VERSION%") do set CURRENT_MAJOR_MINOR=%%a.%%b
    for /f "tokens=1,2 delims=." %%a in ("!RISE_VERSION!") do set RISE_MAJOR_MINOR=%%a.%%b
    
    if not "!CURRENT_MAJOR_MINOR!"=="!RISE_MAJOR_MINOR!" (
        echo.
        echo ============================================================
        echo WARNING: Python version mismatch!
        echo ============================================================
        echo   Your Python:    %CURRENT_VERSION% ^(!CURRENT_MAJOR_MINOR!^)
        echo   RISE Python:    !RISE_VERSION! ^(!RISE_MAJOR_MINOR!^)
        echo.
        echo   Dependencies installed with a different Python version
        echo   may not work correctly with the RISE engine.
        echo.
        echo   Consider using the RISE embedded Python:
        echo   "%RISE_PYTHON%"
        echo ============================================================
        echo.
        pause
    )
) else (
    echo RISE Python: Not found ^(G-Assist not installed^)
)
echo.

:: Handle "all" - setup all plugins
if /i "%PLUGIN_NAME%"=="all" (
    echo Setting up ALL plugins...
    echo.
    
    for /d %%d in ("%EXAMPLES_DIR%*") do (
        if exist "%%d\manifest.json" (
            call :setup_plugin "%%~nxd"
        )
    )
    
    echo.
    echo ============================================================
    echo All plugins setup complete!
    echo ============================================================
    goto :end
)

:: Single plugin setup
if exist "%EXAMPLES_DIR%%PLUGIN_NAME%\manifest.json" (
    call :setup_plugin "%PLUGIN_NAME%"
) else (
    echo ERROR: Plugin "%PLUGIN_NAME%" not found.
    echo.
    echo Available plugins:
    for /d %%d in ("%EXAMPLES_DIR%*") do (
        if exist "%%d\manifest.json" (
            echo   - %%~nxd
        )
    )
    exit /b 1
)

goto :end

:: ============================================================
:: SUBROUTINE: Setup a single plugin
:: ============================================================
:setup_plugin
set "P_NAME=%~1"
set "P_DIR=%EXAMPLES_DIR%%P_NAME%"
set "P_LIBS=%P_DIR%\libs"
set "P_REQUIREMENTS=%P_DIR%\requirements.txt"
set "P_DEPLOY_DIR=%DEPLOY_BASE%\%P_NAME%"

echo ------------------------------------------------------------
echo Setting up: %P_NAME%
echo ------------------------------------------------------------

:: Create libs folder if it doesn't exist
if not exist "%P_LIBS%" mkdir "%P_LIBS%"

:: Pip install requirements if file exists and has content
if exist "%P_REQUIREMENTS%" (
    :: Check if requirements.txt has any non-comment, non-empty lines
    findstr /v /r "^#" "%P_REQUIREMENTS%" | findstr /r /v "^$" >nul 2>&1
    if not errorlevel 1 (
        echo Installing pip dependencies...
        %PYTHON% -m pip install -r "%P_REQUIREMENTS%" --target "%P_LIBS%" --upgrade --quiet
    ) else (
        echo No pip dependencies in requirements.txt
    )
) else (
    echo No requirements.txt found
)

:: Copy gassist_sdk from SDK folder
if exist "%SDK_DIR%\gassist_sdk" (
    echo Copying gassist_sdk from SDK...
    xcopy /E /I /Y "%SDK_DIR%\gassist_sdk" "%P_LIBS%\gassist_sdk" >nul
)

echo Setup complete for %P_NAME%

:: Deploy if -deploy flag was passed
if %DEPLOY%==1 (
    echo Deploying to %P_DEPLOY_DIR%...
    
    :: Create deploy directory if it doesn't exist
    if not exist "%P_DEPLOY_DIR%" mkdir "%P_DEPLOY_DIR%"
    
    :: Copy plugin files
    if exist "%P_DIR%\plugin.py" copy /Y "%P_DIR%\plugin.py" "%P_DEPLOY_DIR%\" >nul
    if exist "%P_DIR%\manifest.json" copy /Y "%P_DIR%\manifest.json" "%P_DEPLOY_DIR%\" >nul
    if exist "%P_DIR%\config.json" copy /Y "%P_DIR%\config.json" "%P_DEPLOY_DIR%\" >nul
    
    :: Copy libs folder
    if exist "%P_LIBS%" xcopy /E /I /Y "%P_LIBS%" "%P_DEPLOY_DIR%\libs" >nul
    
    echo Deployed to: %P_DEPLOY_DIR%
)

echo.
goto :eof

:: ============================================================
:: HELP
:: ============================================================
:show_help
echo.
echo G-Assist Plugin Setup Script
echo ============================
echo.
echo This script installs plugin dependencies and optionally deploys plugins.
echo.
echo USAGE:
echo   setup.bat ^<plugin-name^> [-deploy]
echo   setup.bat all [-deploy]
echo.
echo ARGUMENTS:
echo   ^<plugin-name^>    Name of the plugin folder to setup
echo   all              Setup all plugins in the examples folder
echo.
echo OPTIONS:
echo   -deploy          Also deploy the plugin(s) to RISE plugins folder
echo   -h, --help       Show this help message
echo.
echo WHAT IT DOES:
echo   1. Checks Python version compatibility with RISE embedded Python
echo   2. Creates libs/ folder in the plugin directory
echo   3. Pip installs packages from requirements.txt to libs/
echo   4. Copies gassist_sdk from the SDK folder to libs/
echo   5. (With -deploy) Copies plugin files to the RISE plugins folder
echo.
echo EXAMPLES:
echo   setup.bat hello-world              Setup hello-world plugin
echo   setup.bat hello-world -deploy      Setup and deploy hello-world
echo   setup.bat gemini -deploy           Setup and deploy gemini plugin
echo   setup.bat all                      Setup all plugins
echo   setup.bat all -deploy              Setup and deploy all plugins
echo.
echo AVAILABLE PLUGINS:
for /d %%d in ("%EXAMPLES_DIR%*") do (
    if exist "%%d\manifest.json" (
        echo   - %%~nxd
    )
)
echo.
echo PATHS:
echo   SDK source:     %SDK_DIR%
echo   Deploy base:    %DEPLOY_BASE%
echo   RISE Python:    %RISE_PYTHON%
echo.
endlocal
exit /b 0

:end
endlocal
exit /b 0

:nopython
echo ERROR: Python needs to be installed and in your path
exit /b 1

