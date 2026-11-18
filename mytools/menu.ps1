# =============================================================================
# MyTools Menu - Launcher for all tools
# =============================================================================

$ErrorActionPreference = "Continue"

$tools = @(
    @{ Name = "sysinfo"; Desc = "System Information"; File = "sysinfo.ps1" },
    @{ Name = "netcheck"; Desc = "Network Connectivity Check"; File = "netcheck.ps1" },
    @{ Name = "ping"; Desc = "Quick Ping"; File = "ping.ps1" },
    @{ Name = "disk"; Desc = "Disk Usage"; File = "disk_usage.ps1" },
    @{ Name = "service"; Desc = "Service Manager"; File = "service_manager.ps1" },
    @{ Name = "process"; Desc = "Process Manager"; File = "process_manager.ps1" },
    @{ Name = "log"; Desc = "Log Viewer"; File = "log_viewer.ps1" },
    @{ Name = "ssh"; Desc = "SSH Manager (Console)"; File = "ssh_manager.ps1" },
    @{ Name = "sshui"; Desc = "SSH Manager (GUI)"; File = "SSHManagerUI\SSHManagerUI.exe"; Type = "gui" },
    @{ Name = "sshui-ps"; Desc = "SSH Manager PS (Merged)"; File = "SSHManagerUI\ssh_manager_ui.ps1"; Type = "gui" },
    @{ Name = "sql"; Desc = "SQL Server Viewer"; File = "SQLServerViewer\SQLServerViewer.exe"; Type = "gui" },
    @{ Name = "p22"; Desc = "Port 22 Opener (Python)"; File = "port22_opener.py"; Type = "gui" },
    @{ Name = "p22-ps"; Desc = "Port 22 Opener (PS Script)"; File = "open_port22_all_stations.ps1"; Type = "gui" },
    @{ Name = "sshtool"; Desc = "SSH Setup Tool (Download MSI + Install)"; File = "setup_ssh_tool.ps1" }
)

function Show-Menu {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║         MY TOOLS - Launcher          ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    
    for ($i = 0; $i -lt $tools.Count; $i++) {
        $num = ($i + 1).ToString().PadLeft(2)
        $type = if ($tools[$i].Type -eq "gui") { "[GUI]" } else { "[PS]" }
        Write-Host "  [$num] $type $($tools[$i].Desc)" -ForegroundColor White
    }
    
    Write-Host "  [0] Exit" -ForegroundColor Gray
    Write-Host ""
}

function Run-Tool {
    param([int]$Index)

    if ($Index -eq 0) { exit }
    if ($Index -gt $tools.Count) {
        Write-Host "Invalid selection" -ForegroundColor Red
        return
    }

    $tool = $tools[$Index - 1]
    Write-Host ""
    Write-Host "Running: $($tool.Desc)" -ForegroundColor Cyan
    Write-Host "----------------------------------------" -ForegroundColor DarkGray

    $scriptPath = Join-Path $PSScriptRoot $tool.File

    if ($tool.Type -eq "gui") {
        Write-Host "Launching GUI application..." -ForegroundColor Green
        Start-Process $scriptPath
    } elseif ($tool.File -match "\.exe$") {
        Write-Host "Launching application..." -ForegroundColor Green
        Start-Process $scriptPath
    } else {
        & $scriptPath
    }

    Write-Host ""
    Write-Host "Press Enter to continue..." -ForegroundColor Yellow
    Read-Host
}

# Main loop
while ($true) {
    Show-Menu
    $choice = Read-Host "Select tool"
    
    if ($choice -match "^\d+$") {
        Run-Tool -Index ([int]$choice)
    }
}
