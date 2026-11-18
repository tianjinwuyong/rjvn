# =============================================================================
# Service Manager - Manage Windows Services
# =============================================================================

param(
    [string]$Action = "list",
    [string]$Name = ""
)

$ErrorActionPreference = "Continue"

function Show-ServiceList {
    Write-Host "=== Windows Services ===" -ForegroundColor Cyan
    Write-Host ""
    
    $services = Get-Service | Sort-Object Status, Name
    
    Write-Host "RUNNING SERVICES:" -ForegroundColor Green
    $services | Where-Object { $_.Status -eq 'Running' } | ForEach-Object {
        Write-Host "  $($_.Name) - $($_.DisplayName)"
    }
    
    Write-Host ""
    Write-Host "STOPPED SERVICES:" -ForegroundColor Yellow
    $services | Where-Object { $_.Status -eq 'Stopped' } | ForEach-Object {
        Write-Host "  $($_.Name) - $($_.DisplayName)"
    }
}

function Show-ServiceDetail {
    param([string]$ServiceName)
    
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host "Service '$ServiceName' not found" -ForegroundColor Red
        return
    }
    
    Write-Host ""
    Write-Host "=== $($svc.DisplayName) ===" -ForegroundColor Cyan
    Write-Host "  Name: $($svc.Name)"
    Write-Host "  Status: $($svc.Status)"
    Write-Host "  StartType: $($svc.StartType)"
    Write-Host ""
    
    # Get more detail
    $wmi = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'" -ErrorAction SilentlyContinue
    if ($wmi) {
        Write-Host "  Process ID: $($wmi.ProcessId)"
        Write-Host "  Path: $($wmi.PathName)"
    }
}

function Start-ServiceCustom {
    param([string]$ServiceName)
    Start-Service -Name $ServiceName -ErrorAction Stop
    Write-Host "Started: $ServiceName" -ForegroundColor Green
}

function Stop-ServiceCustom {
    param([string]$ServiceName)
    Stop-Service -Name $ServiceName -Force -ErrorAction Stop
    Write-Host "Stopped: $ServiceName" -ForegroundColor Yellow
}

function Restart-ServiceCustom {
    param([string]$ServiceName)
    Restart-Service -Name $ServiceName -Force -ErrorAction Stop
    Write-Host "Restarted: $ServiceName" -ForegroundColor Green
}

# Main
switch ($Action.ToLower()) {
    "list" { Show-ServiceList }
    "status" { Show-ServiceDetail -ServiceName $Name }
    "start" { 
        if (-not $Name) { Write-Host "Specify -Name <service name>" -ForegroundColor Red }
        else { Start-ServiceCustom -ServiceName $Name }
    }
    "stop" { 
        if (-not $Name) { Write-Host "Specify -Name <service name>" -ForegroundColor Red }
        else { Stop-ServiceCustom -ServiceName $Name }
    }
    "restart" { 
        if (-not $Name) { Write-Host "Specify -Name <service name>" -ForegroundColor Red }
        else { Restart-ServiceCustom -ServiceName $Name }
    }
    default {
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  .\service_manager.ps1 -Action list           # List all services"
        Write-Host "  .\service_manager.ps1 -Action status -Name <name>  # Show service detail"
        Write-Host "  .\service_manager.ps1 -Action start -Name <name>   # Start service"
        Write-Host "  .\service_manager.ps1 -Action stop -Name <name>    # Stop service"
        Write-Host "  .\service_manager.ps1 -Action restart -Name <name> # Restart service"
    }
}
