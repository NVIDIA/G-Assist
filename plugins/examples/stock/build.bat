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
:: Replace 'plugin' with the name of your plugin
set PLUGIN_DIR=%DIST_DIR%\stock

if exist %VENV% (
	call %VENV%\Scripts\activate.bat

	:: Ensure spotify subfolder exists
	if not exist "%PLUGIN_DIR%" mkdir "%PLUGIN_DIR%"

	:: Replace 'g-assist-plugin' with the name of your plugin
	pyinstaller --onefile --name g-assist-stock-plugin --distpath "%PLUGIN_DIR%" plugin.py
	if exist manifest.json (
		copy /y manifest.json "%PLUGIN_DIR%\manifest.json"
		echo manifest.json copied successfully.
	) 

	if exist config.json (
		copy /y config.json "%PLUGIN_DIR%\config.json"
		echo config.json copied successfully.
	) 

	call %VENV%\Scripts\deactivate.bat
	echo Executable can be found in the "%PLUGIN_DIR%" directory
	exit /b 0
) else (
	echo Please run setup.bat before attempting to build
	exit /b 1
)

:nopython
echo Python needs to be installed and in your path
exit /b 1
