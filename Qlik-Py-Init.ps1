# Find Python 3.13
$PythonCmd = $null

# Method 1: Try the Windows Python Launcher (py.exe) - most reliable on Windows
try {
    $ver = & py -3.13 --version 2>&1
    if ($ver -match '(\d+)\.(\d+)') {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -eq 3 -and $minor -eq 13) {
            $PythonCmd = "py"
            $PythonArgs = @("-3.13")
        }
    }
} catch { }

# Method 2: Try python3 and python on PATH
if (-not $PythonCmd) {
    foreach ($cmd in @("python3", "python")) {
        try {
            $ver = & $cmd --version 2>&1
            if ($ver -match '(\d+)\.(\d+)') {
                $major = [int]$Matches[1]
                $minor = [int]$Matches[2]
                if ($major -eq 3 -and $minor -eq 13) {
                    $PythonCmd = $cmd
                    $PythonArgs = @()
                    break
                }
            }
        } catch { }
    }
}

# Method 3: Check common Windows install paths
if (-not $PythonCmd) {
    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:ProgramFiles\Python313\python.exe",
        "${env:ProgramFiles(x86)}\Python313\python.exe",
        "C:\Python313\python.exe"
    )
    foreach ($path in $commonPaths) {
        if (Test-Path $path) {
            try {
                $ver = & $path --version 2>&1
                if ($ver -match '(\d+)\.(\d+)') {
                    $major = [int]$Matches[1]
                    $minor = [int]$Matches[2]
                    if ($major -eq 3 -and $minor -eq 13) {
                        $PythonCmd = $path
                        $PythonArgs = @()
                        break
                    }
                }
            } catch { }
        }
    }
}

if (-not $PythonCmd) {
    Write-Error "ERROR: Python 3.13 is required but not found."
    Write-Output ""
    Write-Output "Python must be accessible via one of:"
    Write-Output "  - The 'py' launcher (installed by default with Python on Windows)"
    Write-Output "  - The 'python' command on your PATH"
    Write-Output "  - A standard install location"
    Write-Output ""
    Write-Output "If Python is installed, try reinstalling with 'Add Python to PATH' checked,"
    Write-Output "or ensure the Python Launcher is included in the install."
    Write-Output ""
    Write-Output "Download Python 3.13 from https://www.python.org/downloads/"
    exit 1
}

Write-Output "Using $(& $PythonCmd @PythonArgs --version)"
Write-Output ""
Write-Output "Setting up the Python virtual environment..."
& $PythonCmd @PythonArgs -m venv $PSScriptRoot\qlik-py-env
if ($LASTEXITCODE -ne 0) { throw "Failed to create the Python 3.13 virtual environment." }

Write-Output ""
Write-Output "Copying project files to the new directory..."
Copy-Item -Path $PSScriptRoot\generated -Destination $PSScriptRoot\qlik-py-env\generated -Recurse -Force
Copy-Item -Path $PSScriptRoot\core -Destination $PSScriptRoot\qlik-py-env\core -Recurse -Force
Copy-Item -Path $PSScriptRoot\requirements.txt -Destination $PSScriptRoot\qlik-py-env\requirements.txt -Force
if (Test-Path $PSScriptRoot\models) { Copy-Item -Path $PSScriptRoot\models -Destination $PSScriptRoot\qlik-py-env\models -Recurse -Force }
if (Test-Path $PSScriptRoot\.env) { Copy-Item -Path $PSScriptRoot\.env -Destination $PSScriptRoot\qlik-py-env\.env -Force }
if (Test-Path $PSScriptRoot\.env.example) { Copy-Item -Path $PSScriptRoot\.env.example -Destination $PSScriptRoot\qlik-py-env\.env.example -Force }

Write-Output ""
$VenvPython = Join-Path $PSScriptRoot "qlik-py-env\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) { throw "Virtual environment Python was not created at $VenvPython" }
Write-Output "Using virtual environment: $(& $VenvPython --version)"

Write-Output ""
Write-Output "Installing required packages..."
& $VenvPython -m pip install --upgrade setuptools pip wheel
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip tooling in the virtual environment." }
& $VenvPython -m pip install -r $PSScriptRoot\requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Failed to install the core requirements." }
& $VenvPython -m spacy download en_core_web_sm
if ($LASTEXITCODE -ne 0) { throw "Failed to install the spaCy English model." }

Write-Output ""
Write-Output "Creating a new firewall rule for TCP port 50055..."
netsh advfirewall firewall add rule name=Qlik-PyTools dir=in action=allow protocol=TCP localport=50055

Write-Output ""
Write-Output "Setup completed. Please check the log above for errors in red text."
Write-Output "Run Qlik-Py-Start.ps1 to start this Server Side Extension."
