$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& "$ScriptDir\qlik-py-env\Scripts\Activate.ps1"
$env:PYTHONPATH = "$ScriptDir\core;$ScriptDir\generated;$env:PYTHONPATH"
$HostAddress = if ($env:QLIK_CLOUD_HOST) { $env:QLIK_CLOUD_HOST } else { "127.0.0.1" }
$Port = if ($env:QLIK_CLOUD_PORT) { $env:QLIK_CLOUD_PORT } else { "8080" }
python -m uvicorn cloud_api:app --app-dir "$ScriptDir\core" --host $HostAddress --port $Port --no-server-header
