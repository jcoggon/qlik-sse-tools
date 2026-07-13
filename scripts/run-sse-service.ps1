$ErrorActionPreference = "Continue"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$Root = Split-Path -Parent $PSScriptRoot
$Core = Join-Path $Root "qlik-py-env\core"
$Python = Join-Path $Root "qlik-py-env\Scripts\python.exe"
$Logs = Join-Path $Root "logs"
$ProcessLog = Join-Path $Logs "sse-process.log"
$Port = if ($env:QLIK_SSE_PORT) { $env:QLIK_SSE_PORT } else { "50055" }
New-Item -ItemType Directory -Path $Logs -Force | Out-Null
Set-Location $Core

while ($true) {
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path (Join-Path $Logs "sse-wrapper.log") -Value "=== starting Qlik SSE at $stamp ==="
    & $Python -X utf8 -u "__main__.py" --port $Port *> $ProcessLog
    $exitCode = $LASTEXITCODE
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path (Join-Path $Logs "sse-wrapper.log") -Value "=== exited at $stamp with code $exitCode; restarting in 5 seconds ==="
    Start-Sleep -Seconds 5
}
