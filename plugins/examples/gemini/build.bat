:: This batch file converts a Python script into a Windows executable.
@echo off
setlocal enabledelayedexpansion

echo ========================================
echo GEMINI PLUGIN BUILD SCRIPT
echo ========================================
echo.

:: Determine if we have 'python' or 'python3' in the path
where /q python
if ERRORLEVEL 1 goto python3
set PYTHON=python
goto validate

:python3
where /q python3
if ERRORLEVEL 1 goto nopython
set PYTHON=python3

:validate
echo [1/8] Validating Python installation...
%PYTHON% --version >nul 2>&1
if ERRORLEVEL 1 (
    echo [ERROR] Python not working correctly
    goto nopython
)
for /f "tokens=*" %%i in ('%PYTHON% --version') do set PYTHON_VERSION=%%i
echo [OK] Found %PYTHON_VERSION%
echo.

echo [2/8] Checking required files...
if not exist gemini.py (
    echo [ERROR] gemini.py not found in current directory
    exit /b 1
)
echo [OK] gemini.py exists

if not exist manifest.json (
    echo [ERROR] manifest.json not found
    exit /b 1
)
echo [OK] manifest.json exists

if not exist requirements.txt (
    echo [ERROR] requirements.txt not found
    exit /b 1
)
echo [OK] requirements.txt exists
echo.

echo [3/8] Validating manifest.json...
%PYTHON% -c "import json; json.load(open('manifest.json'))" >nul 2>&1
if ERRORLEVEL 1 (
    echo [ERROR] manifest.json is not valid JSON
    exit /b 1
)
echo [OK] manifest.json is valid JSON

%PYTHON% -c "import json; m=json.load(open('manifest.json')); assert 'functions' in m, 'No functions array'; assert len(m['functions'])>0, 'Empty functions'" >nul 2>&1
if ERRORLEVEL 1 (
    echo [ERROR] manifest.json missing or empty functions array
    exit /b 1
)
echo [OK] manifest.json has functions defined
echo.

:: Verify the setup script has been run
echo [4/8] Checking virtual environment...
set VENV=.venv
set DIST_DIR=Release
set GEMINI_DIR=%DIST_DIR%
if not exist %VENV% (
    echo [ERROR] Virtual environment not found
    echo Please run setup.bat first
    exit /b 1
)
echo [OK] Virtual environment exists

call %VENV%\Scripts\activate.bat
if ERRORLEVEL 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

echo [5/8] Validating dependencies...
python -c "from google import genai" >nul 2>&1
if ERRORLEVEL 1 (
    echo [ERROR] Google Generative AI library not installed
    echo Please run setup.bat first
    call %VENV%\Scripts\deactivate.bat
    exit /b 1
)
echo [OK] Core dependencies installed

echo [6/8] Checking PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if ERRORLEVEL 1 (
    echo [ERROR] PyInstaller not installed
    echo Installing PyInstaller...
    pip install pyinstaller
    if ERRORLEVEL 1 (
        echo [ERROR] Failed to install PyInstaller
        call %VENV%\Scripts\deactivate.bat
        exit /b 1
    )
)
echo [OK] PyInstaller available
echo.

echo [7/8] Testing plugin import...
python -c "import gemini" >nul 2>&1
if ERRORLEVEL 1 (
    echo [WARNING] Plugin has import errors (check if all dependencies are installed)
) else (
    echo [OK] Plugin imports successfully
)
echo.

echo [7.2/8] Static code analysis (checking for undefined names)...
python -c "import pyflakes" >nul 2>&1
if ERRORLEVEL 1 (
    echo Installing pyflakes for code analysis...
    pip install pyflakes >nul 2>&1
)

python -m pyflakes gemini.py 2>_lint_errors.txt
set LINT_RESULT=%ERRORLEVEL%
if %LINT_RESULT% NEQ 0 (
    echo [WARNING] Code quality issues detected:
    type _lint_errors.txt
    echo.
    echo These may cause runtime errors. Review and fix if needed.
    echo.
) else (
    echo [OK] No undefined names or obvious errors detected
)
del _lint_errors.txt >nul 2>&1
echo.

echo [7.5/8] Running smoke test (verify plugin can start without crashing)...
REM Delete old log to get fresh startup errors
del "%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gemini-plugin.log" >nul 2>&1

REM Use pre-made smoke test template
if not exist _smoke_test_template.py (
    echo [WARNING] Smoke test template not found, skipping smoke test
    goto skip_smoke_test
)

python _smoke_test_template.py 2>_smoke_error.txt
set SMOKE_TEST_RESULT=%ERRORLEVEL%

if %SMOKE_TEST_RESULT% NEQ 0 (
    echo [ERROR] Plugin CRASHED during startup
    echo.
    echo ========================================
    echo WHY IT FAILED
    echo ========================================
    
    REM Show Python errors if any
    if exist _smoke_error.txt (
        for %%A in (_smoke_error.txt) do set ERROR_SIZE=%%~zA
        if !ERROR_SIZE! GTR 0 (
            echo.
            echo Python errors:
            echo ----------------------------------------
            type _smoke_error.txt
            echo ----------------------------------------
        )
    )
    
    REM Show plugin log errors (filter out expected "invalid JSON" from smoke test)
    set PLUGIN_LOG=%PROGRAMDATA%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gemini-plugin.log
    if exist "!PLUGIN_LOG!" (
        echo.
        echo Plugin log (critical errors only^):
        echo ----------------------------------------
        powershell -Command "Get-Content '$env:PROGRAMDATA\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gemini-plugin.log' | Where-Object { $_ -notmatch 'invalid JSON' -and ($_ -match 'ERROR' -or $_ -match 'CRITICAL' -or $_ -match 'EXCEPTION') } | Select-Object -Last 10"
        echo ----------------------------------------
        echo (Note^: "invalid JSON" errors during smoke test are expected and harmless^)
    )
    
    echo.
    echo ========================================
    echo LIKELY CAUSES
    echo ========================================
    echo   - Missing Python dependency (run^: pip install -r requirements.txt^)
    echo   - Syntax error in gemini.py
    echo   - Import error at module level
    echo   - Crash in global initialization code
    echo.
    echo ========================================
    echo HOW TO DEBUG
    echo ========================================
    echo   1. Run^: python gemini.py   (see full error^)
    echo   2. Check^: %%PROGRAMDATA%%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\gemini-plugin.log
    echo   3. Verify^: pip list ^| findstr "google-generativeai"
    echo.
    set /p CONTINUE_BUILD="Continue building broken plugin? (Y/N) "
    if /i "!CONTINUE_BUILD!" NEQ "Y" (
        echo.
        echo Build CANCELLED - fix the errors above and run build.bat again
        del _smoke_error.txt >nul 2>&1
        call %VENV%\Scripts\deactivate.bat
        exit /b 1
    )
    echo.
    echo [WARNING] Building anyway (plugin will NOT work until errors are fixed)
    echo.
) else (
    echo [OK] Plugin starts without crashing
)

:skip_smoke_test
del _smoke_error.txt >nul 2>&1
echo.

echo [8/8] Building executable...
if exist %VENV%\Scripts\activate.bat (

	:: Ensure gemini subfolder exists
	if not exist "%GEMINI_DIR%" mkdir "%GEMINI_DIR%"

	pyinstaller --onefile --name g-assist-plugin-gemini --distpath "%GEMINI_DIR%" gemini.py
	if ERRORLEVEL 1 (
	    echo [ERROR] PyInstaller build failed
	    call %VENV%\Scripts\deactivate.bat
	    exit /b 1
	)
	echo [OK] Executable built successfully
	echo.
	
	echo [POST-BUILD] Copying configuration files...
	if exist manifest.json (
		copy /y manifest.json "%GEMINI_DIR%\manifest.json" >nul
		echo [OK] manifest.json copied
	) else (
		echo [WARNING] manifest.json not found, creating blank
		echo {} > manifest.json
		copy /y manifest.json "%GEMINI_DIR%\manifest.json" >nul
	)
	
	if exist config.json (
		copy /y config.json "%GEMINI_DIR%\config.json" >nul
		echo [OK] config.json copied
	) else (
		echo [WARNING] config.json not found, creating template
		echo {} > config.json
		copy /y config.json "%GEMINI_DIR%\config.json" >nul
	)
	
	echo ^<insert your API key here from https://aistudio.google.com/app/apikey^> > gemini-api.key
	copy /y gemini-api.key "%GEMINI_DIR%\gemini-api.key" >nul
	echo [ACTION REQUIRED] Fill in gemini-api.key with your API key
	echo.
	
	echo [VALIDATION] Verifying build output...
	if not exist "%GEMINI_DIR%\g-assist-plugin-gemini.exe" (
	    echo [ERROR] Executable not found in output directory
	    call %VENV%\Scripts\deactivate.bat
	    exit /b 1
	)
	
	for %%A in ("%GEMINI_DIR%\g-assist-plugin-gemini.exe") do (
	    set EXE_SIZE=%%~zA
	)
	
	:: Convert bytes to MB for display
	set /a EXE_SIZE_MB=!EXE_SIZE!/1048576
	
	if !EXE_SIZE! LSS 100000 (
	    echo [ERROR] Executable size is too small (!EXE_SIZE! bytes - expected 5MB+^)
	    echo Build failed - executable is incomplete
	    call %VENV%\Scripts\deactivate.bat
	    exit /b 1
	)
	
	echo [OK] Executable exists (!EXE_SIZE_MB! MB^)
	echo.
	
	call %VENV%\Scripts\deactivate.bat
	
	echo ========================================
	echo BUILD SUCCESSFUL!
	echo ========================================
	echo.
	echo Output directory: %GEMINI_DIR%
	echo.
	echo Files created:
	dir /b "%GEMINI_DIR%"
	echo.
	echo Next steps:
	echo 1. Copy contents to: %%PROGRAMDATA%%\NVIDIA Corporation\nvtopps\rise\plugins\gemini\
	echo 2. Add your API key to gemini-api.key
	echo 3. Restart G-Assist
	echo.
	exit /b 0
) else (
	echo Please run setup.bat before attempting to build
	exit /b 1
)

:nopython
echo Python needs to be installed and in your path
exit /b 1
