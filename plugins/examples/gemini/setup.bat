:: This batch file setups a users environment to build an executable from a
:: Python script.
@echo off
setlocal

:: Determine if we have 'python' or 'python3' in the path. On Windows, the
:: Python executable is typically called 'python', so check that first.
python --version >nul 2>nul
if %errorlevel% == 0 (
    set PYTHON=python
    goto setup
)

python3 --version >nul 2>nul
if %errorlevel% == 0 (
    set PYTHON=python3
    goto setup
)

goto nopython

:: Setup the virtual environment if it does not already exist.
:setup
set VENV=.venv
if not exist %VENV% (
	%PYTHON% -m venv %VENV%
)

:: Install the required packages
call %VENV%\Scripts\activate.bat
%PYTHON% -m pip install -r requirements.txt
call %VENV%\Scripts\deactivate.bat

echo Setup complete
endlocal
exit /b 0

:nopython
echo Python needs to be installed and in your path
exit /b 1
