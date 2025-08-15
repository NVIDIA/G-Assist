:: This batch file converts a Python script into a Windows executable.
@echo off
setlocal

:: Determine if we have 'python' or 'python3' in the path. On Windows, the
:: Python executable is typically called 'python', so check that first.
where /q python
if ERRORLEVEL 1 goto python3
set PYTHON=python
goto build

:python3
where /q python3
if ERRORLEVEL 1 goto nopython
set PYTHON=python3

:: Verify the setup script has been run
:build
set VENV=.venv
set DIST_DIR=dist
set PLUGIN_NAME=google
set GOOGLE_DIR=%DIST_DIR%\%PLUGIN_NAME%
if exist %VENV% (
	call %VENV%\Scripts\activate.bat

	:: Ensure google subfolder exists
	if not exist "%GOOGLE_DIR%" mkdir "%GOOGLE_DIR%"

	pyinstaller --onefile --name g-assist-plugin-%PLUGIN_NAME% --distpath "%GOOGLE_DIR%" plugin.py
	if exist manifest.json (
		copy /y manifest.json "%GOOGLE_DIR%\manifest.json"
		echo manifest.json copied successfully.
	) else (
		echo {} > manifest.json
		echo Created a blank manifest.json file.	
		copy /y manifest.json "%GOOGLE_DIR%\manifest.json"
		echo manifest.json copied successfully.
	)
	if exist config.json (
		copy /y config.json "%GOOGLE_DIR%\config.json"
		echo config.json copied successfully.
	) else (
		echo {} > config.json
		echo Created a blank config.json file.	
		copy /y config.json "%GOOGLE_DIR%\config.json"
		echo config.json copied successfully.
	)
	
	echo ^<insert your API key here from https://aistudio.google.com/app/apikey^> > google.key
	echo Created a blank google.key file. ACTION REQUIRED: Please populate it with your Google Gemini key.
	copy /y google.key "%GOOGLE_DIR%\google.key"
	echo google.key copied successfully.
	
	call %VENV%\Scripts\deactivate.bat
	echo Executable can be found in the "%GOOGLE_DIR%" directory
	exit /b 0
) else (
	echo Please run setup.bat before attempting to build
	exit /b 1
)

:nopython
echo Python needs to be installed and in your path
exit /b 1
