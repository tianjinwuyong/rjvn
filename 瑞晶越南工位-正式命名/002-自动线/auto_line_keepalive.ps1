$ErrorActionPreference = 'Continue'
$AutoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = 'C:\Users\tianj\AppData\Local\Programs\Python\Python38\python.exe'
if (-not (Test-Path -LiteralPath $Python)) { $Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $Python) { throw 'Python 3.8 was not found' }
$PortScript = Join-Path (Split-Path -Parent $AutoRoot) 'open_station_api_ports.py'
if (Test-Path -LiteralPath $PortScript) {
    Start-Process -FilePath $Python -ArgumentList @($PortScript) -WorkingDirectory (Split-Path -Parent $PortScript) -Wait -WindowStyle Normal
}
$ApiHost = Join-Path (Split-Path -Parent $AutoRoot) 'station_local_info_api_host.py'
if (Test-Path -LiteralPath $ApiHost) {
    $apiRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*$ApiHost*--line-domain AUTO_LINE*" }
    if (-not $apiRunning) { Start-Process -FilePath $Python -ArgumentList @($ApiHost,'--line-domain','AUTO_LINE') -WorkingDirectory (Split-Path -Parent $ApiHost) -WindowStyle Normal | Out-Null }
}
$Panel = Join-Path (Split-Path -Parent $AutoRoot) 'station_basics_panel.py'
if (Test-Path -LiteralPath $Panel) {
    $panelRunning = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*$Panel*" }
    if (-not $panelRunning) { Start-Process -FilePath $Python -ArgumentList @($Panel) -WorkingDirectory (Split-Path -Parent $Panel) -WindowStyle Normal | Out-Null }
}

$Stations = @()
function Add-Station([string]$Prefix, [string]$ScriptName, [string]$Mode) {
    $matches = @(Get-ChildItem -LiteralPath $AutoRoot -Directory | Where-Object { $_.Name.StartsWith($Prefix) })
    foreach ($match in $matches) {
        $script = Join-Path $match.FullName $ScriptName
        if (Test-Path -LiteralPath $script) {
            if ($Mode -eq 'PDA') {
                $arguments = @('-m','streamlit','run',$script,'--server.headless','true')
            } else {
                $arguments = @($script)
            }
            $script:Stations += @{ Folder=$match.Name; Script=$script; Args=$arguments }
        }
    }
}
Add-Station '(01)' 'pda_station.py' 'PDA'
Add-Station '(02)' 'aoi_quality_agent.py' 'AGENT'
Add-Station '(03)' 'ict_agent.py' 'AGENT'
Add-Station '(04)' 'fct_agent.py' 'AGENT'
Add-Station '(05)' 'depanel_heartbeat_agent.py' 'AGENT'
Add-Station '(06)' 'qrbinding.py' 'AGENT'
Add-Station '(07)' 'assembly_ate_agent.py' 'AGENT'
Add-Station '(08)' 'supersonic_agent.py' 'AGENT'
Add-Station '(09)' 'aging_cab_agent.py' 'AGENT'
Add-Station '(10)' 'hivolt_ate_agent.py' 'AGENT'
Add-Station '(11)' 'packing_ate_agent.py' 'AGENT'
Add-Station '(12)' 'outer_box_binding_agent.py' 'AGENT'
Add-Station '(13)' 'pallet_binding_agent.py' 'AGENT'

function Find-StationProcess([string]$ScriptPath) {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match '^python' -and $_.CommandLine -like "*$ScriptPath*"
    }
}

while ($true) {
    foreach ($station in $Stations) {
        $working = Split-Path -Parent $station.Script
        if (-not (Find-StationProcess $station.Script)) {
            Start-Process -FilePath $Python -ArgumentList $station.Args -WorkingDirectory $working -WindowStyle Normal | Out-Null
        }
    }
    Start-Sleep -Seconds 10
}
