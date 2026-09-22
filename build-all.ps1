$ErrorActionPreference = "Stop"

Write-Host "Building Red Alert 2 trainer..."
& "$PSScriptRoot\RedAlert2\build.ps1"
if ($LASTEXITCODE -ne 0) { throw "Red Alert 2 build failed" }

Write-Host "Building Red Alert 3 trainer..."
& "$PSScriptRoot\RedAlert3\build.ps1"
if ($LASTEXITCODE -ne 0) { throw "Red Alert 3 build failed" }

Write-Host "Building Command & Conquer 3 trainer..."
& "$PSScriptRoot\CommandConquer3\build.ps1"
if ($LASTEXITCODE -ne 0) { throw "Command & Conquer 3 build failed" }
