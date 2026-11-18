$ErrorActionPreference = 'Stop'
$deputyRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $deputyRoot 'dist20260818\deputy_mes_agent.exe'
$task = 'RUIJING Deputy MES'
if (-not (Test-Path -LiteralPath $exe)) { throw "Deputy MES executable not found: $exe" }
schtasks.exe /Create /TN $task /TR ('"' + $exe + '"') /SC ONLOGON /F | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Could not register automatic startup task (exit code $LASTEXITCODE)" }
Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -WindowStyle Hidden
Write-Output "Installed and started $task"
