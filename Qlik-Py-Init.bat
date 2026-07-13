@echo off
setlocal enabledelayedexpansion

REM Check for Python 3.13 using multiple methods

REM Method 1: Try the Windows Python Launcher (py.exe) - most reliable on Windows
where py >nul 2>&1
if !ERRORLEVEL! equ 0 (
    for /f "tokens=2 delims= " %%v in ('py -3.13 --version 2^>^&1') do set "PY_VER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
        if %%a EQU 3 if %%b EQU 13 (
            set "PYTHON_CMD=py -3.13"
            goto :python_found
        )
    )
)

REM Method 2: Try python on PATH
where python >nul 2>&1
if !ERRORLEVEL! equ 0 (
    for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set "PY_VER=%%v"
    for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
        if %%a EQU 3 if %%b EQU 13 (
            set "PYTHON_CMD=python"
            goto :python_found
        )
    )
)

REM Method 3: Check common Windows install paths
for %%P in (
    "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    "%ProgramFiles%\Python313\python.exe"
    "%ProgramFiles(x86)%\Python313\python.exe"
    "C:\Python313\python.exe"
) do (
    if exist %%P (
        for /f "tokens=2 delims= " %%v in ('%%P --version 2^>^&1') do set "PY_VER=%%v"
        for /f "tokens=1,2 delims=." %%a in ("!PY_VER!") do (
            if %%a EQU 3 if %%b EQU 13 (
                set "PYTHON_CMD=%%~P"
                goto :python_found
            )
        )
    )
)

echo ERROR: Python 3.13 is required but not found.
echo.
echo Python must be accessible via one of:
echo   - The 'py' launcher (installed by default with Python on Windows)
echo   - The 'python' command on your PATH
echo   - A standard install location
echo.
echo If Python is installed, try reinstalling with "Add Python to PATH" checked,
echo or ensure the Python Launcher is included in the install.
echo.
echo Download Python 3.13 from https://www.python.org/downloads/
pause
exit /b 1

:python_found
echo Using Python at: & %PYTHON_CMD% --version & echo.
echo Setting up the Python virtual environment... & echo.
%PYTHON_CMD% -m venv "%~dp0\qlik-py-env"
echo.
echo Copying project files to the new directory... & echo.
xcopy /E /I /Y "%~dp0\generated" "%~dp0\qlik-py-env\generated"
xcopy /E /I /Y "%~dp0\core" "%~dp0\qlik-py-env\core"
copy /Y "%~dp0\requirements.txt" "%~dp0\qlik-py-env\requirements.txt"
if exist "%~dp0\models" xcopy /E /I /Y "%~dp0\models" "%~dp0\qlik-py-env\models"
if exist "%~dp0\.env" copy /Y "%~dp0\.env" "%~dp0\qlik-py-env\.env"
if exist "%~dp0\.env.example" copy /Y "%~dp0\.env.example" "%~dp0\qlik-py-env\.env.example"
echo.
echo Activating the virtual environment... & echo.
cd /d "%~dp0qlik-py-env\Scripts"
call activate.bat
cd /d "%~dp0qlik-py-env"
echo.
echo Installing required packages from requirements.txt... & echo.
python -m pip install --upgrade setuptools pip wheel
pip install -r "%~dp0\requirements.txt"
python -m spacy download en_core_web_sm
echo.
echo Creating a new firewall rule for TCP port 50055... & echo.
netsh advfirewall firewall add rule name="Qlik PyTools" dir=in action=allow protocol=TCP localport=50055
echo.
echo Setup completed. Please check the log above for errors in red text. & echo.
echo Run Qlik-Py-Start.bat to start this Server Side Extension. & echo.
pause
