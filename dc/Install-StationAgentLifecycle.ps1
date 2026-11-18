[CmdletBinding(SupportsShouldProcess)]
param(
  [Parameter(Mandatory)] [string]$StationCode,
  [Parameter(Mandatory)] [string]$AgentPath,
  [string]$HealthScript,
  [string]$WorkingDirectory,
  [string]$RunAsUser = "$env:COMPUTERNAME\$env:USERNAME",
  [string]$TaskPrefix = 'Ruijing',
  [switch]$UseSupervisor,
  [string]$SupervisorPath = "$PSScriptRoot\station_supervisor.py",
  [string]$PythonPath = 'python.exe'
)

$ErrorActionPreference = 'Stop'
$agent = (Resolve-Path -LiteralPath $AgentPath).Path
if (-not $HealthScript) { $HealthScript = Join-Path $PSScriptRoot 'Invoke-StationAgentHealthCheck.ps1' }
$health = (Resolve-Path -LiteralPath $HealthScript).Path
if (-not $WorkingDirectory) { $WorkingDirectory = Split-Path -Parent $agent }
$agentTask = "${TaskPrefix}Agent_$StationCode"
$healthTask = "${TaskPrefix}Health_$StationCode"
$log = Join-Path $WorkingDirectory 'health.log'
$healthArgs = "-NoProfile -ExecutionPolicy Bypass -File `"$health`" -StationCode `"$StationCode`" -AgentTask `"$agentTask`" -AgentPath `"$agent`" -LogPath `"$log`""
if ($UseSupervisor) {
  $supervisor = (Resolve-Path -LiteralPath $SupervisorPath).Path
  $supervisorLog = Join-Path $WorkingDirectory 'supervisor.log'
  $supervisorHealth = Join-Path $WorkingDirectory 'supervisor-health.json'
  $supervisorArgs = "`"$supervisor`" run --station-code `"$StationCode`" --agent `"$agent`" --working-dir `"$WorkingDirectory`" --log-file `"$supervisorLog`" --health-file `"$supervisorHealth`""
  $agentAction = New-ScheduledTaskAction -Execute $PythonPath -Argument $supervisorArgs -WorkingDirectory $WorkingDirectory
} else {
  $agentAction = New-ScheduledTaskAction -Execute $agent -WorkingDirectory $WorkingDirectory
}
$healthAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $healthArgs -WorkingDirectory $WorkingDirectory
$loginTrigger = New-ScheduledTaskTrigger -AtLogOn -User $RunAsUser.Split('\')[-1]
$periodicTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
$interactive = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType Interactive -RunLevel Highest
$system = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
if ($PSCmdlet.ShouldProcess($StationCode, 'register Agent auto-start and periodic health check')) {
  Register-ScheduledTask -TaskName $agentTask -Action $agentAction -Trigger $loginTrigger -Principal $interactive -Settings $settings -Force | Out-Null
  Register-ScheduledTask -TaskName $healthTask -Action $healthAction -Trigger $periodicTrigger -Principal $system -Settings $settings -Force | Out-Null
  Start-ScheduledTask -TaskName $agentTask
  Start-ScheduledTask -TaskName $healthTask
}
[pscustomobject]@{ Station=$StationCode; AgentTask=$agentTask; HealthTask=$healthTask; Agent=$agent; UseSupervisor=[bool]$UseSupervisor; CheckInterval='1 minute' }
