@echo off
set "SCRIPT_DIR=%~dp0"

cd /d "%SCRIPT_DIR%qlik-py-env\Scripts"
call activate.bat

:: Sync source files to the virtual environment before starting
echo Syncing source files...
xcopy /E /Y /Q "%SCRIPT_DIR%core\*" "%SCRIPT_DIR%qlik-py-env\core\"
xcopy /E /Y /Q "%SCRIPT_DIR%generated\*" "%SCRIPT_DIR%qlik-py-env\generated\"
if exist "%SCRIPT_DIR%.env" copy /Y "%SCRIPT_DIR%.env" "%SCRIPT_DIR%qlik-py-env\.env"

cd /d "%SCRIPT_DIR%qlik-py-env\core"
python -u __main__.py %*
pause
