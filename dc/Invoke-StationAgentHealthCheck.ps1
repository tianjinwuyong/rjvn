[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string]$StationCode,
  [Parameter(Mandatory)] [Alias('SupervisorTask')] [string]$AgentTask,
  [Parameter(Mandatory)] [string]$AgentPath,
  [string]$LogPath = "$env:ProgramData\Ruijing\station-health.log"
)

$ErrorActionPreference = 'Stop'
$logDir = Split-Path -Parent $LogPath
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
function Write-Health([string]$Event, [hashtable]$Data = @{}) {
  $row = [ordered]@{ timestamp=(Get-Date).ToUniversalTime().ToString('o'); stationCode=$StationCode; event=$Event }
  foreach ($key in $Data.Keys) { $row[$key] = $Data[$key] }
  ($row | ConvertTo-Json -Compress) | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

try {
  $task = Get-ScheduledTask -TaskName $AgentTask -ErrorAction SilentlyContinue
  if (-not $task) { Write-Health 'supervisor_task_missing'; return }
  $running = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($AgentPath, [StringComparison]::OrdinalIgnoreCase) })
  if ($running.Count -eq 0) {
    Start-ScheduledTask -TaskName $AgentTask
    Write-Health 'agent_started' @{ task=$AgentTask; agent=$AgentPath }
  } else {
    Write-Health 'healthy' @{ pid=($running | Select-Object -First 1 -ExpandProperty ProcessId) }
  }
} catch {
  Write-Health 'health_check_error' @{ error=$_.Exception.Message }
}
