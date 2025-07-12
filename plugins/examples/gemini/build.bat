:: This batch file converts a Python script into a Windows executable.
@echo off
setlocal

:: Determine if we have 'python' or 'python3' in the path. On Windows, the
:: Python executable is typically called 'python', so check that first.
python --version >nul 2>nul
if %errorlevel% == 0 (
    set PYTHON=python
    goto build
)

python3 --version >nul 2>nul
if %errorlevel% == 0 (
    set PYTHON=python3
    goto build
)

goto nopython

:: Verify the setup script has been run
:build
set VENV=.venv
set DIST_DIR=Release
set GEMINI_DIR=%DIST_DIR%
if exist %VENV% (
	call %VENV%\Scripts\activate.bat

	:: Ensure gemini subfolder exists
	if not exist "%GEMINI_DIR%" mkdir "%GEMINI_DIR%"

	pyinstaller --onefile --name g-assist-plugin-gemini --distpath "%GEMINI_DIR%" gemini.py
	if exist manifest.json (
		copy /y manifest.json "%GEMINI_DIR%\manifest.json"
		echo manifest.json copied successfully.
	) else (
		echo {} > manifest.json
		echo Created a blank manifest.json file.	
		copy /y manifest.json "%GEMINI_DIR%\manifest.json"
		echo manifest.json copied successfully.
	)
	if exist config.json (
		copy /y config.json "%GEMINI_DIR%\config.json"
		echo config.json copied successfully.
	) else (
		echo {} > config.json
		echo Created a blank config.json file.	
		copy /y config.json "%GEMINI_DIR%\config.json"
		echo config.json copied successfully.
	)
	
	if exist gemini.key (
		if not exist google.key (
			echo Renaming gemini.key to google.key...
			ren gemini.key google.key
		)
	)

	if not exist google.key (
		echo ^<insert your API key here from https://aistudio.google.com/app/apikey^> > google.key
		echo Created a blank google.key file. ACTION REQUIRED: Please populate it with your Google API key.
	)
	
	copy /y google.key "%GEMINI_DIR%\google.key"
	echo google.key copied successfully.
	
	call %VENV%\Scripts\deactivate.bat
	echo Executable can be found in the "%GEMINI_DIR%" directory
	exit /b 0
) else (
	echo Please run setup.bat before attempting to build
	exit /b 1
)

:nopython
echo Python needs to be installed and in your path
exit /b 1