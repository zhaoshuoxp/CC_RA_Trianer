$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $python = @("py", "-3.12")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $python = @("python")
} else {
    throw "Python 3.12 is required"
}

if ($python.Count -eq 2) {
    & $python[0] $python[1] -m venv .venv
} else {
    & $python[0] -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw "Unable to create virtual environment" }

& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.0
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name RA3Trainer-Portable --collect-all keystone --add-data "fingerprints.json;." app.py
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
Write-Host "Built: dist\RA3Trainer-Portable.exe"
