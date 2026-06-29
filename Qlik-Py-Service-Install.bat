@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Qlik Python Tools - Windows Service Installer
REM  Uses Servy to run the SSE as a Windows service
REM ============================================================

set "SERVICE_NAME=QlikPyTools"
set "DISPLAY_NAME=Qlik Python Tools SSE"
set "DESCRIPTION=Qlik Server Side Extension providing Python data science functions"
set "SERVY_VERSION=8.5"
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

REM Locate Servy CLI - check PATH, common install folder, then package directory
set "SERVY_CLI="
where servy-cli.exe >nul 2>&1
if !ERRORLEVEL! equ 0 (
    for /f "tokens=*" %%i in ('where servy-cli.exe') do set "SERVY_CLI=%%i"
)
if not defined SERVY_CLI if exist "%ProgramFiles%\Servy\servy-cli.exe" set "SERVY_CLI=%ProgramFiles%\Servy\servy-cli.exe"
if not defined SERVY_CLI if exist "%ProgramFiles(x86)%\Servy\servy-cli.exe" set "SERVY_CLI=%ProgramFiles(x86)%\Servy\servy-cli.exe"
if not defined SERVY_CLI if exist "%SCRIPT_DIR%servy-cli.exe" set "SERVY_CLI=%SCRIPT_DIR%servy-cli.exe"

if not defined SERVY_CLI (
    set "SERVY_INSTALLER="
    if exist "%SCRIPT_DIR%servy-%SERVY_VERSION%-x64-installer.exe" set "SERVY_INSTALLER=%SCRIPT_DIR%servy-%SERVY_VERSION%-x64-installer.exe"
    if not defined SERVY_INSTALLER (
        for %%f in ("%SCRIPT_DIR%servy-*-x64-installer.exe") do (
            if exist "%%~f" set "SERVY_INSTALLER=%%~f"
        )
    )
    if not defined SERVY_INSTALLER (
        echo ERROR: Servy was not found.
        echo.
        echo Place servy-%SERVY_VERSION%-x64-installer.exe in this directory:
        echo   %SCRIPT_DIR%
        echo.
        echo The Raptor gateway package normally includes this installer in the bundled SSE tools zip.
        pause
        exit /b 1
    )

    echo Installing Servy from !SERVY_INSTALLER!...
    "!SERVY_INSTALLER!" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    if !ERRORLEVEL! neq 0 (
        echo ERROR: Servy installer failed with exit code !ERRORLEVEL!.
        pause
        exit /b 1
    )

    if exist "%ProgramFiles%\Servy\servy-cli.exe" set "SERVY_CLI=%ProgramFiles%\Servy\servy-cli.exe"
    if not defined SERVY_CLI if exist "%ProgramFiles(x86)%\Servy\servy-cli.exe" set "SERVY_CLI=%ProgramFiles(x86)%\Servy\servy-cli.exe"
)

if not defined SERVY_CLI (
    echo ERROR: Servy installer completed, but servy-cli.exe was not found.
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
echo  Servy CLI:     %SERVY_CLI%
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
"%SERVY_CLI%" install "--name=%SERVICE_NAME%" "--displayName=%DISPLAY_NAME%" "--description=%DESCRIPTION%" "--path=%PYTHON_EXE%" "--startupDir=%CORE_DIR%" "--params=-u __main__.py" "--startupType=AutomaticDelayedStart" "--stdout=%LOG_DIR%\service-stdout.log" "--stderr=%LOG_DIR%\service-stderr.log" --enableSizeRotation "--rotationSize=5" "--maxRotations=10" "--recoveryAction=RestartProcess" "--maxRestartAttempts=0" --quiet
if !ERRORLEVEL! neq 0 (
    echo ERROR: Failed to install service.
    pause
    exit /b 1
)

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
    "%SERVY_CLI%" start "--name=%SERVICE_NAME%" --quiet
    if !ERRORLEVEL! equ 0 (
        echo Service started successfully.
    ) else (
        echo Failed to start service. Check the log files for details.
    )
)

echo.
pause
