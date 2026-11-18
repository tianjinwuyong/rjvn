# =============================================================================
# Process Manager - View and Manage Processes
# =============================================================================

param(
    [string]$Action = "list",
    [string]$Name = "",
    [int]$PID = 0
)

function Show-ProcessList {
    Write-Host "=== Top Processes by Memory ===" -ForegroundColor Cyan
    Write-Host ""
    
    $procs = Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 30
    
    Write-Host "PID       Name                 Memory(MB)   CPU(s)" -ForegroundColor Yellow
    Write-Host "-" * 60
    
    foreach ($p in $procs) {
        $mem = [math]::Round($p.WorkingSet64 / 1MB, 1)
        $cpu = [math]::Round($p.CPU, 2)
        Write-Host "$($p.Id.ToString().PadLeft(7)) $($p.ProcessName.PadLeft(20)) $($mem.ToString().PadLeft(10)) $($cpu.ToString().PadLeft(8))"
    }
}

function Show-ProcessDetail {
    param([string]$ProcessName)
    
    $procs = Get-Process -Name $ProcessName -ErrorAction SilentlyContinue
    if (-not $procs) {
        Write-Host "Process '$ProcessName' not found" -ForegroundColor Red
        return
    }
    
    foreach ($p in $procs) {
        Write-Host ""
        Write-Host "=== $($p.ProcessName) (PID: $($p.Id)) ===" -ForegroundColor Cyan
        Write-Host "  Memory: $([math]::Round($p.WorkingSet64 / 1MB, 1)) MB"
        Write-Host "  CPU: $([math]::Round($p.CPU, 2)) seconds"
        Write-Host "  Threads: $($p.Threads.Count)"
        Write-Host "  Handles: $($p.HandleCount)"
        Write-Host "  Start Time: $($p.StartTime)"
        Write-Host "  File: $($p.Path)"
    }
}

function Kill-ProcessCustom {
    param([int]$ProcessId)
    
    Stop-Process -Id $ProcessId -Force -ErrorAction Stop
    Write-Host "Killed process $ProcessId" -ForegroundColor Green
}

function Kill-ProcessByName {
    param([string]$ProcessName)
    
    Stop-Process -Name $ProcessName -Force -ErrorAction Stop
    Write-Host "Killed all '$ProcessName' processes" -ForegroundColor Green
}

# Main
switch ($Action.ToLower()) {
    "list" { Show-ProcessList }
    "find" { Show-ProcessDetail -ProcessName $Name }
    "kill" { 
        if ($PID -gt 0) { Kill-ProcessCustom -ProcessId $PID }
        elseif ($Name) { Kill-ProcessByName -ProcessName $Name }
        else { Write-Host "Specify -PID <id> or -Name <name>" -ForegroundColor Red }
    }
    default {
        Write-Host "Usage:" -ForegroundColor Yellow
        Write-Host "  .\process_manager.ps1 -Action list              # List top processes"
        Write-Host "  .\process_manager.ps1 -Action find -Name <name> # Find process details"
        Write-Host "  .\process_manager.ps1 -Action kill -PID <id>     # Kill by PID"
        Write-Host "  .\process_manager.ps1 -Action kill -Name <name> # Kill by name"
    }
}
