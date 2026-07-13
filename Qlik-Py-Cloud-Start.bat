@echo off
set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%qlik-py-env\Scripts\activate.bat"
set "PYTHONPATH=%SCRIPT_DIR%core;%SCRIPT_DIR%generated;%PYTHONPATH%"
if not defined QLIK_CLOUD_HOST set "QLIK_CLOUD_HOST=127.0.0.1"
if not defined QLIK_CLOUD_PORT set "QLIK_CLOUD_PORT=8080"
python -m uvicorn cloud_api:app --app-dir "%SCRIPT_DIR%core" --host "%QLIK_CLOUD_HOST%" --port "%QLIK_CLOUD_PORT%" --no-server-header
