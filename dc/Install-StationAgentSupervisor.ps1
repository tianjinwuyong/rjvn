[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory)] [string]$StationCode,
  [Parameter(Mandatory)] [string]$AgentPath,
  [Parameter(Mandatory)] [string]$TaskName,
  [string]$SupervisorPath = "$PSScriptRoot\station_supervisor.py",
  [string]$PythonPath = "python.exe",
  [string]$WorkingDirectory,
  [string]$RunAsUser = "$env:COMPUTERNAME\$env:USERNAME"
)

$ErrorActionPreference = 'Stop'
$agent = (Resolve-Path -LiteralPath $AgentPath).Path
$supervisor = (Resolve-Path -LiteralPath $SupervisorPath).Path
if (-not $WorkingDirectory) { $WorkingDirectory = Split-Path -Parent $agent }
$log = Join-Path $WorkingDirectory 'supervisor.log'
$health = Join-Path $WorkingDirectory 'supervisor-health.json'
$arguments = "`"$supervisor`" run --station-code `"$StationCode`" --agent `"$agent`" --working-dir `"$WorkingDirectory`" --log-file `"$log`" --health-file `"$health`""
$action = New-ScheduledTaskAction -Execute $PythonPath -Argument $arguments -WorkingDirectory $WorkingDirectory
$principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType Interactive -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $RunAsUser.Split('\')[-1]
if ($PSCmdlet.ShouldProcess($TaskName, 'register and start interactive Agent supervisor')) {
  Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName $TaskName
  [pscustomobject]@{ Task=$TaskName; Station=$StationCode; Agent=$agent; Supervisor=$supervisor; State=(Get-ScheduledTask -TaskName $TaskName).State }
}
