@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Qlik Python Tools - Windows Service Installer
REM  Uses NSSM (Non-Sucking Service Manager) to run as a service
REM ============================================================

set "SERVICE_NAME=QlikPyTools"
set "SCRIPT_DIR=%~dp0"
set "VENV_DIR=%SCRIPT_DIR%qlik-py-env"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "CORE_DIR=%VENV_DIR%\core"
set "LOG_DIR=%CORE_DIR%\logs"

REM Check for administrator privileges
net session >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click the script and select "Run as administrator".
    pause
    exit /b 1
)

REM Check that the virtual environment exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Virtual environment not found at %VENV_DIR%
    echo Please run Qlik-Py-Init.bat first.
    pause
    exit /b 1
)

REM Locate NSSM - check local directory, then PATH
set "NSSM_EXE="
if exist "%SCRIPT_DIR%nssm.exe" (
    set "NSSM_EXE=%SCRIPT_DIR%nssm.exe"
) else (
    where nssm >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        for /f "tokens=*" %%i in ('where nssm') do set "NSSM_EXE=%%i"
    )
)

if not defined NSSM_EXE (
    echo ERROR: NSSM ^(Non-Sucking Service Manager^) not found.
    echo.
    echo Please download NSSM from: https://nssm.cc/download
    echo Then either:
    echo   1. Place nssm.exe in this directory: %SCRIPT_DIR%
    echo   2. Or add it to your system PATH
    echo.
    pause
    exit /b 1
)

echo ============================================================
echo  Qlik Python Tools - Service Installer
echo ============================================================
echo.
echo  Service name:  %SERVICE_NAME%
echo  Python:        %PYTHON_EXE%
echo  Working dir:   %CORE_DIR%
echo  Log directory: %LOG_DIR%
echo  NSSM:          %NSSM_EXE%
echo.

REM Check if service already exists
sc query %SERVICE_NAME% >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo WARNING: Service '%SERVICE_NAME%' already exists.
    echo To reinstall, run Qlik-Py-Service-Uninstall.bat first.
    pause
    exit /b 1
)

REM Ensure log directory exists
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo Installing service...
"%NSSM_EXE%" install %SERVICE_NAME% "%PYTHON_EXE%" "-u __main__.py"
if !ERRORLEVEL! neq 0 (
    echo ERROR: Failed to install service.
    pause
    exit /b 1
)

REM Configure service parameters
echo Configuring service...

REM Set working directory to core/ so relative paths work correctly
"%NSSM_EXE%" set %SERVICE_NAME% AppDirectory "%CORE_DIR%"

REM Set display name and description
"%NSSM_EXE%" set %SERVICE_NAME% DisplayName "Qlik Python Tools SSE"
"%NSSM_EXE%" set %SERVICE_NAME% Description "Qlik Server Side Extension providing Python data science functions"

REM Redirect stdout and stderr to log files (captures startup messages)
"%NSSM_EXE%" set %SERVICE_NAME% AppStdout "%LOG_DIR%\service-stdout.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStderr "%LOG_DIR%\service-stderr.log"
"%NSSM_EXE%" set %SERVICE_NAME% AppStdoutCreationDisposition 4
"%NSSM_EXE%" set %SERVICE_NAME% AppStderrCreationDisposition 4
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateOnline 1
"%NSSM_EXE%" set %SERVICE_NAME% AppRotateBytes 5242880

REM Auto-restart on failure
"%NSSM_EXE%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM_EXE%" set %SERVICE_NAME% AppRestartDelay 5000

REM Set startup type to automatic
"%NSSM_EXE%" set %SERVICE_NAME% Start SERVICE_AUTO_START

echo.
echo ============================================================
echo  Service installed successfully!
echo ============================================================
echo.
echo  To START the service:
echo    net start %SERVICE_NAME%
echo.
echo  To STOP the service:
echo    net stop %SERVICE_NAME%
echo.
echo  Log files:
echo    Application log:  %LOG_DIR%\SSEPlugin.log
echo    Service stdout:   %LOG_DIR%\service-stdout.log
echo    Service stderr:   %LOG_DIR%\service-stderr.log
echo.
echo  The service is set to start automatically on boot.
echo.

set /p START_NOW="Start the service now? (Y/N): "
if /i "%START_NOW%"=="Y" (
    echo Starting service...
    net start %SERVICE_NAME%
    if !ERRORLEVEL! equ 0 (
        echo Service started successfully.
    ) else (
        echo Failed to start service. Check the log files for details.
    )
)

echo.
pause
