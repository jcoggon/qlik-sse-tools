& $PSScriptRoot\qlik-py-env\Scripts\activate.ps1

# Sync source files to the virtual environment before starting
Write-Host "Syncing source files..."
Copy-Item -Path "$PSScriptRoot\core\*" -Destination "$PSScriptRoot\qlik-py-env\core\" -Recurse -Force
Copy-Item -Path "$PSScriptRoot\generated\*" -Destination "$PSScriptRoot\qlik-py-env\generated\" -Recurse -Force
if (Test-Path "$PSScriptRoot\.env") {
    Copy-Item -Path "$PSScriptRoot\.env" -Destination "$PSScriptRoot\qlik-py-env\.env" -Force
}

cd $PSScriptRoot\qlik-py-env\core
python -u __main__.py