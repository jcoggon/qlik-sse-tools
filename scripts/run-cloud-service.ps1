$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
$Core = Join-Path $Root "qlik-py-env\core"
$Python = Join-Path $Root "qlik-py-env\Scripts\python.exe"
$Logs = Join-Path $Root "logs"
$ProcessLog = Join-Path $Logs "cloud-process.log"
$BindHost = if ($env:QLIK_CLOUD_HOST) { $env:QLIK_CLOUD_HOST } else { "127.0.0.1" }
$Port = if ($env:QLIK_CLOUD_PORT) { $env:QLIK_CLOUD_PORT } else { "8080" }
New-Item -ItemType Directory -Path $Logs -Force | Out-Null
Set-Location $Root

while ($true) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path (Join-Path $Logs "cloud-wrapper.log") -Value "=== starting Qlik Cloud API at $stamp ==="
    & $Python -X utf8 -u -m uvicorn cloud_api:app --app-dir $Core --host $BindHost --port $Port --no-server-header *> $ProcessLog
    $exitCode = $LASTEXITCODE
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path (Join-Path $Logs "cloud-wrapper.log") -Value "=== exited at $stamp with code $exitCode; restarting in 5 seconds ==="
    Start-Sleep -Seconds 5
}
