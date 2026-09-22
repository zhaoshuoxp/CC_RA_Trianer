$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 is required" }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.3
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed" }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name YRTrainer-Portable --collect-all keystone --add-data "fingerprints.json;." app.py
if ($LASTEXITCODE -ne 0) { throw "Build failed" }
Write-Host "Built: dist\YRTrainer-Portable.exe"
