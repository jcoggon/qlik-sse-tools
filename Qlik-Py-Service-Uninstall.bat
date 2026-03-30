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

REM Locate NSSM
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
    echo ERROR: NSSM not found. Place nssm.exe in %SCRIPT_DIR% or add to PATH.
    pause
    exit /b 1
)

echo Stopping service...
net stop %SERVICE_NAME% >nul 2>&1

echo Removing service...
"%NSSM_EXE%" remove %SERVICE_NAME% confirm
if !ERRORLEVEL! equ 0 (
    echo.
    echo Service '%SERVICE_NAME%' removed successfully.
    echo Log files in qlik-py-env\core\logs\ have been preserved.
) else (
    echo ERROR: Failed to remove service.
)

echo.
pause
