[CmdletBinding(SupportsShouldProcess)]
param(
  [string]$ConfigPath = "$PSScriptRoot\station-supervisor-manual.json",
  [string]$PythonPath = 'python.exe',
  [string]$HealthScript,
  [string]$WorkingRoot = 'D:\stations',
  [string]$RunAsUser = 'SYSTEM'
)

$ErrorActionPreference = 'Stop'
if (-not $HealthScript) { $HealthScript = Join-Path $PSScriptRoot 'Invoke-StationAgentHealthCheck.ps1' }
$config = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$healthScriptPath = (Resolve-Path -LiteralPath $HealthScript).Path
$results = foreach ($station in $config.stations) {
  $taskName = "RuijingHealth_$($station.code)"
  $agentPath = Join-Path $WorkingRoot (Split-Path -Leaf $station.agent)
  $logPath = Join-Path $WorkingRoot "health-$($station.code).log"
  $arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$healthScriptPath`" -StationCode `"$($station.code)`" -SupervisorTask `"$($station.task)`" -AgentPath `"$agentPath`" -LogPath `"$logPath`""
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $WorkingRoot
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration (New-TimeSpan -Days 3650)
  $principal = New-ScheduledTaskPrincipal -UserId $RunAsUser -LogonType ServiceAccount -RunLevel Highest
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 1)
  if ($PSCmdlet.ShouldProcess($taskName, 'register periodic Agent health check')) {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
  }
  [pscustomobject]@{ Station=$station.code; Task=$taskName; Agent=$agentPath; Interval='1 minute' }
}
$results | Format-Table -AutoSize
