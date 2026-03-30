@echo off
REM Qlik Python Tools — Optional Packages Installer
REM Run after Qlik-Py-Init.bat to install extra capabilities

set "PYTHON=%~dp0qlik-py-env\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found at %~dp0qlik-py-env\
    echo Please run Qlik-Py-Init.bat first.
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0install_extras.py" %*
pause
