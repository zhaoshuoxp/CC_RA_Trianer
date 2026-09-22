$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$compiler = "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
$output = Join-Path $root 'dist'
New-Item -ItemType Directory -Path $output -Force | Out-Null

& $compiler /nologo /target:winexe /platform:x86 /optimize+ `
  /win32manifest:"$root\Cnc3Trainer\app.manifest" `
  /reference:System.dll /reference:System.Drawing.dll /reference:System.Windows.Forms.dll `
  /out:"$output\CNC3Trainer-Portable.exe" `
  "$root\Cnc3Trainer\NativeMethods.cs" `
  "$root\Cnc3Trainer\GameProfile.cs" `
  "$root\Cnc3Trainer\ProcessMemory.cs" `
  "$root\Cnc3Trainer\X86Builder.cs" `
  "$root\Cnc3Trainer\TrainerEngine.cs" `
  "$root\Cnc3Trainer\MainForm.cs" `
  "$root\Cnc3Trainer\Program.cs"

if ($LASTEXITCODE -ne 0) { throw "编译失败，退出代码 $LASTEXITCODE" }
Get-FileHash -Algorithm SHA256 -LiteralPath "$output\CNC3Trainer-Portable.exe"
