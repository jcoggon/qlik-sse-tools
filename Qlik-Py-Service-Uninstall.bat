@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM  Qlik Python Tools - Windows Service Uninstaller
REM ============================================================

set "SERVICE_NAME=QlikPyTools"
set "SCRIPT_DIR=%~dp0"

REM Check for administrator privileges
net session >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo ERROR: This script must be run as Administrator.
    echo Right-click the script and select "Run as administrator".
    pause
    exit /b 1
)

REM Check if service exists
sc query %SERVICE_NAME% >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo Service '%SERVICE_NAME%' is not installed.
    pause
    exit /b 0
)

REM Locate Servy CLI
set "SERVY_CLI="
where servy-cli.exe >nul 2>&1
if !ERRORLEVEL! equ 0 (
    for /f "tokens=*" %%i in ('where servy-cli.exe') do set "SERVY_CLI=%%i"
)
if not defined SERVY_CLI if exist "%ProgramFiles%\Servy\servy-cli.exe" set "SERVY_CLI=%ProgramFiles%\Servy\servy-cli.exe"
if not defined SERVY_CLI if exist "%ProgramFiles(x86)%\Servy\servy-cli.exe" set "SERVY_CLI=%ProgramFiles(x86)%\Servy\servy-cli.exe"
if not defined SERVY_CLI if exist "%SCRIPT_DIR%servy-cli.exe" set "SERVY_CLI=%SCRIPT_DIR%servy-cli.exe"

echo Stopping service...
net stop %SERVICE_NAME% >nul 2>&1

echo Removing service...
if defined SERVY_CLI (
    "%SERVY_CLI%" uninstall "--name=%SERVICE_NAME%" --quiet
) else (
    echo Servy CLI was not found; falling back to sc delete.
    sc delete %SERVICE_NAME%
)

if !ERRORLEVEL! equ 0 (
    echo.
    echo Service '%SERVICE_NAME%' removed successfully.
    echo Log files in qlik-py-env\core\logs\ have been preserved.
) else (
    echo ERROR: Failed to remove service.
)

echo.
pause
