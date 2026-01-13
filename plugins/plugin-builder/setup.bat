:: Shared setup script for all G-Assist plugins (Python, C++, Node.js)
:: Usage: setup.bat <plugin-name|all> [-deploy]
@echo off
setlocal EnableDelayedExpansion

set EXAMPLES_DIR=%~dp0
set SDK_PYTHON=%EXAMPLES_DIR%..\sdk\python
set SDK_CPP=%EXAMPLES_DIR%..\sdk\cpp
set SDK_NODEJS=%EXAMPLES_DIR%..\sdk\nodejs
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

echo.
echo ============================================================
echo G-Assist Plugin Setup
echo ============================================================
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
)
if /i "%PLUGIN_NAME%"=="all" goto :done

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

goto :done

:: ============================================================
:: SUBROUTINE: Setup a single plugin
:: ============================================================
:setup_plugin
set "P_NAME=%~1"
set "P_DIR=%EXAMPLES_DIR%%P_NAME%"
set "P_LIBS=%P_DIR%\libs"
set "P_DEPLOY_DIR=%DEPLOY_BASE%\%P_NAME%"

echo ------------------------------------------------------------
echo Setting up: %P_NAME%
echo ------------------------------------------------------------

:: Detect plugin type
set "P_TYPE=unknown"
if exist "%P_DIR%\plugin.py" set "P_TYPE=python"
if exist "%P_DIR%\plugin.cpp" set "P_TYPE=cpp"
if exist "%P_DIR%\main.cpp" set "P_TYPE=cpp"
if exist "%P_DIR%\CMakeLists.txt" set "P_TYPE=cpp"
if exist "%P_DIR%\*.vcxproj" set "P_TYPE=cpp"
if exist "%P_DIR%\plugin.js" set "P_TYPE=nodejs"

echo Plugin type: %P_TYPE%

:: Create libs folder if it doesn't exist
if not exist "%P_LIBS%" mkdir "%P_LIBS%"

:: Handle based on plugin type
if "%P_TYPE%"=="python" call :setup_python
if "%P_TYPE%"=="cpp" call :setup_cpp
if "%P_TYPE%"=="nodejs" call :setup_nodejs
if "%P_TYPE%"=="unknown" (
    echo WARNING: Could not detect plugin type
)

echo Setup complete for %P_NAME%

:: Deploy if -deploy flag was passed
if %DEPLOY%==1 (
    call :deploy_plugin
)

echo.
goto :eof

:: ============================================================
:: PYTHON SETUP
:: ============================================================
:setup_python
echo [Python Plugin]

:: Check Python version
call :check_python_version

:: Pip install requirements if file exists
set "P_REQUIREMENTS=%P_DIR%\requirements.txt"
if exist "%P_REQUIREMENTS%" (
    findstr /v /r "^#" "%P_REQUIREMENTS%" | findstr /r /v "^$" >nul 2>&1
    if not errorlevel 1 (
        echo Installing pip dependencies to libs/...
        %PYTHON% -m pip install -r "%P_REQUIREMENTS%" --target "%P_LIBS%" --upgrade --quiet
    ) else (
        echo No pip dependencies in requirements.txt
    )
) else (
    echo No requirements.txt found
)

:: Copy gassist_sdk from SDK folder
if exist "%SDK_PYTHON%\gassist_sdk" (
    echo Copying Python SDK to libs/gassist_sdk/...
    xcopy /E /I /Y "%SDK_PYTHON%\gassist_sdk" "%P_LIBS%\gassist_sdk" >nul
)

goto :eof

:: ============================================================
:: C++ SETUP
:: ============================================================
:setup_cpp
echo [C++ Plugin]

:: Create include directory in libs
if not exist "%P_LIBS%\include" mkdir "%P_LIBS%\include"

:: Copy gassist_sdk.hpp from SDK folder
if exist "%SDK_CPP%\gassist_sdk.hpp" (
    echo Copying C++ SDK to libs/include/gassist_sdk.hpp...
    copy /Y "%SDK_CPP%\gassist_sdk.hpp" "%P_LIBS%\include\" >nul
)

:: Check if nlohmann/json exists in logiled (common location)
set "NLOHMANN_SRC=%EXAMPLES_DIR%logiled\nlohmann"
if exist "%NLOHMANN_SRC%\json.hpp" (
    echo Copying nlohmann/json.hpp to libs/include/nlohmann/...
    if not exist "%P_LIBS%\include\nlohmann" mkdir "%P_LIBS%\include\nlohmann"
    copy /Y "%NLOHMANN_SRC%\json.hpp" "%P_LIBS%\include\nlohmann\" >nul
) else (
    echo NOTE: nlohmann/json not found. CMake will download it during build.
)

:: Copy DLLs from any SDK redist folders to libs/ (for runtime loading)
:: Note: Using "dir ... >nul 2>&1 &&" since "if exist *.dll" doesn't work with wildcards
dir "%P_DIR%\iCUESDK\redist\x64\*.dll" >nul 2>&1 && (
    echo Copying iCUESDK runtime DLLs to libs/...
    copy /Y "%P_DIR%\iCUESDK\redist\x64\*.dll" "%P_LIBS%\" >nul
)
dir "%P_DIR%\AutomationSDK\redist\x64\*.dll" >nul 2>&1 && (
    echo Copying AutomationSDK runtime DLLs to libs/...
    copy /Y "%P_DIR%\AutomationSDK\redist\x64\*.dll" "%P_LIBS%\" >nul
)

echo.
echo To build: mkdir build ^& cd build ^& cmake .. ^& cmake --build . --config Release
echo   Or for VS: msbuild *.sln /p:Configuration=Release /p:Platform=x64

goto :eof

:: ============================================================
:: NODE.JS SETUP
:: ============================================================
:setup_nodejs
echo [Node.js Plugin]

:: Copy gassist-sdk.js from SDK folder
if exist "%SDK_NODEJS%\gassist-sdk.js" (
    echo Copying Node.js SDK to libs/gassist-sdk.js...
    copy /Y "%SDK_NODEJS%\gassist-sdk.js" "%P_LIBS%\" >nul
)

:: Check if Node.js is available
where /q node
if errorlevel 1 (
    echo WARNING: Node.js not found in PATH
) else (
    for /f "tokens=1" %%v in ('node --version') do echo Node.js version: %%v
)

goto :eof

:: ============================================================
:: DEPLOY PLUGIN
:: ============================================================
:deploy_plugin
echo Deploying to %P_DEPLOY_DIR%...

:: ============================================================
:: PRE-DEPLOYMENT: Validate source manifest
:: ============================================================
call :validate_manifest "%P_DIR%\manifest.json" "SOURCE"
if errorlevel 1 (
    echo.
    echo ERROR: Source manifest validation failed - NOT deploying!
    echo Fix the issues above before deploying.
    goto :eof
)

:: Create deploy directory if it doesn't exist
if not exist "%P_DEPLOY_DIR%" mkdir "%P_DEPLOY_DIR%"

:: Copy common files
if exist "%P_DIR%\manifest.json" copy /Y "%P_DIR%\manifest.json" "%P_DEPLOY_DIR%\" >nul
if exist "%P_DIR%\config.json" copy /Y "%P_DIR%\config.json" "%P_DEPLOY_DIR%\" >nul

:: Copy type-specific files
if "%P_TYPE%"=="python" (
    if exist "%P_DIR%\plugin.py" copy /Y "%P_DIR%\plugin.py" "%P_DEPLOY_DIR%\" >nul
    if exist "%P_LIBS%" xcopy /E /I /Y "%P_LIBS%" "%P_DEPLOY_DIR%\libs" >nul
)

if "%P_TYPE%"=="cpp" (
    :: For C++, copy built executable and any DLLs
    set "CPP_BUILD_DIR=%P_DIR%\build\Release"
    
    :: Try build/Release first (CMake output)
    if exist "!CPP_BUILD_DIR!\*.exe" (
        echo Copying executable from build/Release...
        copy /Y "!CPP_BUILD_DIR!\*.exe" "%P_DEPLOY_DIR%\" >nul
        
        :: Copy any DLLs from build directory
        if exist "!CPP_BUILD_DIR!\*.dll" (
            echo Copying DLLs from build/Release...
            copy /Y "!CPP_BUILD_DIR!\*.dll" "%P_DEPLOY_DIR%\" >nul
        )
    ) else if exist "%P_DIR%\x64\Release\*.exe" (
        :: Try x64/Release (Visual Studio output)
        echo Copying executable from x64/Release...
        copy /Y "%P_DIR%\x64\Release\*.exe" "%P_DEPLOY_DIR%\" >nul
        
        if exist "%P_DIR%\x64\Release\*.dll" (
            echo Copying DLLs from x64/Release...
            copy /Y "%P_DIR%\x64\Release\*.dll" "%P_DEPLOY_DIR%\" >nul
        )
    ) else if exist "%P_DIR%\Release\*.exe" (
        :: Try Release folder
        echo Copying executable from Release...
        copy /Y "%P_DIR%\Release\*.exe" "%P_DEPLOY_DIR%\" >nul
        
        if exist "%P_DIR%\Release\*.dll" (
            echo Copying DLLs from Release...
            copy /Y "%P_DIR%\Release\*.dll" "%P_DEPLOY_DIR%\" >nul
        )
    ) else if exist "%P_DIR%\*.exe" (
        :: Try root folder
        echo Copying executable from plugin folder...
        copy /Y "%P_DIR%\*.exe" "%P_DEPLOY_DIR%\" >nul
        
        if exist "%P_DIR%\*.dll" (
            echo Copying DLLs from plugin folder...
            copy /Y "%P_DIR%\*.dll" "%P_DEPLOY_DIR%\" >nul
        )
    ) else (
        echo WARNING: No executable found. Build the plugin first with CMake.
    )
    
    :: Copy any DLLs from libs folder to deployed plugin's libs/
    dir "%P_LIBS%\*.dll" >nul 2>&1 && (
        echo Copying runtime DLLs to libs/...
        if not exist "%P_DEPLOY_DIR%\libs" mkdir "%P_DEPLOY_DIR%\libs"
        copy /Y "%P_LIBS%\*.dll" "%P_DEPLOY_DIR%\libs\" >nul
    )
)

if "%P_TYPE%"=="nodejs" (
    if exist "%P_DIR%\plugin.js" copy /Y "%P_DIR%\plugin.js" "%P_DEPLOY_DIR%\" >nul
    if exist "%P_DIR%\launch.bat" copy /Y "%P_DIR%\launch.bat" "%P_DEPLOY_DIR%\" >nul
    if exist "%P_LIBS%\gassist-sdk.js" copy /Y "%P_LIBS%\gassist-sdk.js" "%P_DEPLOY_DIR%\" >nul
)

:: ============================================================
:: POST-DEPLOYMENT: Validate deployed manifest
:: ============================================================
call :validate_manifest "%P_DEPLOY_DIR%\manifest.json" "DEPLOYED"
if errorlevel 1 (
    echo.
    echo WARNING: Deployed manifest validation failed!
    echo The plugin may not load correctly in G-Assist.
)

echo Deployed to: %P_DEPLOY_DIR%
goto :eof

:: ============================================================
:: VALIDATE MANIFEST
:: Checks manifest.json for common issues that would prevent loading
:: Usage: call :validate_manifest "path\to\manifest.json" "SOURCE|DEPLOYED"
:: ============================================================
:validate_manifest
set "MANIFEST_PATH=%~1"
set "MANIFEST_TYPE=%~2"
set "VALIDATION_ERRORS=0"

echo Validating %MANIFEST_TYPE% manifest...

:: Check file exists
if not exist "%MANIFEST_PATH%" (
    echo   [ERROR] manifest.json not found
    exit /b 1
)

:: Check file is not empty (0 bytes)
for %%F in ("%MANIFEST_PATH%") do set MANIFEST_SIZE=%%~zF
if "%MANIFEST_SIZE%"=="0" (
    echo   [ERROR] manifest.json is EMPTY
    exit /b 1
)

:: Validate JSON using PowerShell
powershell.exe -NoProfile -Command "try { Get-Content '%MANIFEST_PATH%' -Raw | ConvertFrom-Json | Out-Null; Write-Host '  [OK] Manifest is valid'; exit 0 } catch { Write-Host '  [ERROR] Invalid JSON'; exit 1 }"
if %ERRORLEVEL% neq 0 exit /b 1

exit /b 0

:: ============================================================
:: CHECK PYTHON VERSION
:: ============================================================
:check_python_version
:: Determine if we have 'python' or 'python3' in the path
where /q python
if ERRORLEVEL 1 (
    where /q python3
    if ERRORLEVEL 1 (
        echo WARNING: Python not found in PATH
        goto :eof
    )
    set PYTHON=python3
) else (
    set PYTHON=python
)

:: Get current Python version
for /f "tokens=2" %%v in ('%PYTHON% --version 2^>^&1') do set CURRENT_VERSION=%%v
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
        echo WARNING: Python version mismatch!
        echo   Your Python: %CURRENT_VERSION% - RISE Python: !RISE_VERSION!
        echo   Consider using RISE Python: "%RISE_PYTHON%"
        echo.
    )
)
goto :eof

:: ============================================================
:: HELP
:: ============================================================
:show_help
echo.
echo G-Assist Plugin Setup Script
echo ============================
echo.
echo This script sets up plugin dependencies for Python, C++, and Node.js plugins.
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
echo.
echo   Python plugins (plugin.py):
echo     - Pip installs packages from requirements.txt to libs/
echo     - Copies gassist_sdk from SDK to libs/
echo.
echo   C++ plugins (plugin.cpp or CMakeLists.txt):
echo     - Copies gassist_sdk.hpp to libs/include/
echo     - Copies nlohmann/json.hpp to libs/include/nlohmann/ (if available)
echo     - Note: Use CMake to build the executable
echo     - Deploy copies .exe and any .dll files from build output
echo.
echo   Node.js plugins (plugin.js):
echo     - Copies gassist-sdk.js to libs/
echo.
echo EXAMPLES:
echo   setup.bat hello-world              Setup Python plugin
echo   setup.bat hello-world-cpp          Setup C++ plugin
echo   setup.bat hello-world-nodejs       Setup Node.js plugin
echo   setup.bat all                      Setup all plugins
echo   setup.bat hello-world -deploy      Setup and deploy
echo.
echo AVAILABLE PLUGINS:
for /d %%d in ("%EXAMPLES_DIR%*") do (
    if exist "%%d\manifest.json" (
        set "PTYPE="
        if exist "%%d\plugin.py" set "PTYPE=[Python]"
        if exist "%%d\plugin.cpp" set "PTYPE=[C++]"
        if exist "%%d\main.cpp" set "PTYPE=[C++]"
        if exist "%%d\*.vcxproj" set "PTYPE=[C++]"
        if exist "%%d\CMakeLists.txt" set "PTYPE=[C++]"
        if exist "%%d\plugin.js" set "PTYPE=[Node.js]"
        echo   - %%~nxd !PTYPE!
    )
)
echo.
echo SDK PATHS:
echo   Python:   %SDK_PYTHON%
echo   C++:      %SDK_CPP%
echo   Node.js:  %SDK_NODEJS%
echo.
endlocal
exit /b 0

:done
endlocal
exit /b 0
