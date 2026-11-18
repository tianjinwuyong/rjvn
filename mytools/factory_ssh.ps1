# =============================================================================
# Factory SSH Tool - Quick SSH to factory stations
# =============================================================================

param(
    [string]$Station = ""
)

# Factory stations database
$stations = @{
    # === 手动线 (Manual Line - EPS18W) ===
    "波峰焊" = @{ IP = "192.168.1.10"; User = ""; Desc = "Wave Soldering" }
    "AOI手动" = @{ IP = "192.168.6.90"; User = "Admin"; Desc = "AOI Inspection" }
    "ICT手动" = @{ IP = "192.168.6.91"; User = "Admin"; Desc = "ICT Test" }
    "FCT手动" = @{ IP = "192.168.6.92"; User = "Administrator"; Desc = "FCT Test" }
    "分板机手动" = @{ IP = "192.168.6.93"; User = "Administrator"; Desc = "Depanel Machine" }
    "绑码手动" = @{ IP = "192.168.6.94"; User = ""; Desc = "QR Code Binding" }
    "组装ATE手动" = @{ IP = "192.168.6.95"; User = "Administrator"; Desc = "Assembly ATE" }
    "超声波手动" = @{ IP = "192.168.6.96"; User = ""; Desc = "Ultrasonic Welding" }
    "老化手动" = @{ IP = "192.168.6.97"; User = "Administrator"; Desc = "Aging (Antonson)" }
    "高压测试手动" = @{ IP = "192.168.6.98"; User = "Administrator"; Desc = "Hi-Pot Test" }
    "包装ATE手动" = @{ IP = "192.168.6.99"; User = "Administrator"; Desc = "Packaging ATE" }
    "包装手动" = @{ IP = "192.168.6.100"; User = "Administrator"; Desc = "Packaging" }

    # === 自动线 (Auto Line - EPS48W) ===
    "AOI自动" = @{ IP = "192.168.6.50"; User = "Admin"; Desc = "AOI Inspection" }
    "ICT自动" = @{ IP = "192.168.6.51"; User = "Admin"; Desc = "ICT Test" }
    "FCT自动" = @{ IP = "192.168.6.52"; User = "Administrator"; Desc = "FCT Test" }
    "分板机自动" = @{ IP = "192.168.6.53"; User = "Administrator"; Desc = "Depanel Machine" }
    "激光打标" = @{ IP = "192.168.6.54"; User = ""; Desc = "Laser Marking" }
    "组装ATE自动" = @{ IP = "192.168.6.55"; User = "Administrator"; Desc = "Assembly ATE" }
    "自动超声波" = @{ IP = "192.168.6.56"; User = "wy"; Desc = "Auto Ultrasonic (THIS PC)" }
    "创华老化" = @{ IP = "192.168.6.57"; User = "tianjinwuyong"; Desc = "Aging (Chuanghua)" }
    "高压测试自动" = @{ IP = "192.168.6.58"; User = "Administrator"; Desc = "Hi-Pot Test" }
    "包装ATE左" = @{ IP = "192.168.6.59"; User = "Administrator"; Desc = "Packaging ATE Left" }
    "包装ATE右" = @{ IP = "192.168.6.60"; User = "Administrator"; Desc = "Packaging ATE Right" }

    # === Common shortcuts ===
    "ssh" = @{ IP = "192.168.6.155"; User = "$env:USERNAME"; Desc = "This PC" }
}

function Show-Stations {
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║              Factory Station SSH Tool                         ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  手动线 (EPS18W) - Manual Line:" -ForegroundColor Yellow
    Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    $manualStations = @("波峰焊", "AOI手动", "ICT手动", "FCT手动", "分板机手动", "绑码手动", "组装ATE手动", "超声波手动", "老化手动", "高压测试手动", "包装ATE手动", "包装手动")
    for ($i = 0; $i -lt $manualStations.Count; $i++) {
        $name = $manualStations[$i]
        $s = $stations[$name]
        Write-Host "    [$($i+1).)] $($name.PadRight(12)) → $($s.IP.PadRight(15)) $($s.User)" -ForegroundColor White
    }

    Write-Host ""
    Write-Host "  自动线 (EPS48W) - Auto Line:" -ForegroundColor Yellow
    Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor DarkGray

    $autoStations = @("AOI自动", "ICT自动", "FCT自动", "分板机自动", "激光打标", "组装ATE自动", "自动超声波", "创华老化", "高压测试自动", "包装ATE左", "包装ATE右")
    for ($i = 0; $i -lt $autoStations.Count; $i++) {
        $name = $autoStations[$i]
        $s = $stations[$name]
        Write-Host "    [$(($i+1)+$manualStations.Count).] $($name.PadRight(12)) → $($s.IP.PadRight(15)) $($s.User)" -ForegroundColor White
    }

    Write-Host ""
    Write-Host "  本机 (This PC):" -ForegroundColor Yellow
    Write-Host "  ─────────────────────────────────────────────────────────────" -ForegroundColor DarkGray
    Write-Host "    [99.] ssh               → $($stations['ssh'].IP.PadRight(15)) $env:USERNAME" -ForegroundColor White

    Write-Host ""
    Write-Host "  [0.]  Exit" -ForegroundColor Gray
    Write-Host ""
}

function Connect-SSH {
    param([string]$Name)

    if (-not $stations.ContainsKey($Name)) {
        Write-Host "Unknown station: $Name" -ForegroundColor Red
        return
    }

    $s = $stations[$Name]
    Write-Host ""
    Write-Host "Connecting to $($s.Desc) ($($s.IP))..." -ForegroundColor Cyan

    if ($s.User) {
        ssh $s.User@$($s.IP)
    } else {
        ssh $($s.IP)
    }
}

# Main
if ($Station) {
    Connect-SSH -Name $Station
} else {
    Show-Stations

    $choice = Read-Host "Select station number"
    if ($choice -eq "0") { exit }

    $manualCount = 12
    $allStations = @("波峰焊", "AOI手动", "ICT手动", "FCT手动", "分板机手动", "绑码手动", "组装ATE手动", "超声波手动", "老化手动", "高压测试手动", "包装ATE手动", "包装手动",
                    "AOI自动", "ICT自动", "FCT自动", "分板机自动", "激光打标", "组装ATE自动", "自动超声波", "创华老化", "高压测试自动", "包装ATE左", "包装ATE右")

    $idx = [int]$choice - 1
    if ($idx -ge 0 -and $idx -lt $allStations.Count) {
        Connect-SSH -Name $allStations[$idx]
    } elseif ($choice -eq "99") {
        Connect-SSH -Name "ssh"
    } else {
        Write-Host "Invalid selection" -ForegroundColor Red
    }
}
