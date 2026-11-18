# ============================================================
# 瑞晶产线工位监控 + 自动重启
# Station Monitor Daemon for 瑞晶 Manual Line
# Runs on central PC (95 or 56), monitors all 11 stations
# Auto-restarts Flask on any station that goes down
# ============================================================

param(
    [int]$IntervalSec = 30,        # Check every N seconds
    [int]$Port = 8090,             # Flask port on each station
    [switch]$OneShot,              # Run once and exit (for testing)
    [switch]$NoAutoRestart         # Monitor only, don't restart
)

$ErrorActionPreference = "Continue"

# ============================================================
# Station list — manual line only (no auto line)
# ============================================================
$Stations = @(
    @{ Code="01-AOI";      Name="AOI";       IP="192.168.6.90" },
    @{ Code="02-ICT";      Name="ICT";       IP="192.168.6.91" },
    @{ Code="03-FCT";      Name="FCT";       IP="192.168.6.92" },
    @{ Code="04-分板机";    Name="分板机";     IP="192.168.6.93" },
    @{ Code="05-绑码";     Name="绑码";      IP="192.168.6.94" },
    @{ Code="06-激光打标";  Name="激光打标";   IP="192.168.6.95" },
    @{ Code="07-组装ATE";  Name="组装ATE";   IP="192.168.6.95" },
    @{ Code="08-超声";     Name="超声";      IP="192.168.6.96" },
    @{ Code="09-波峰焊";   Name="波峰焊";    IP="192.168.6.1.10" },
    @{ Code="10-成品老化";  Name="成品老化";   IP="192.168.6.97" },
    @{ Code="11-高压测试";  Name="高压测试";   IP="192.168.6.98" },
    @{ Code="12-包装ATE";  Name="包装ATE";   IP="192.168.6.99" }
)

# Credentials
$WinRMPort = 5985
$User = "Administrator"
$Pass = "rj"
$secPass = ConvertTo-SecureString $Pass -AsPlainText -Force
$Cred = New-Object System.Management.Automation.PSCredential $User, $secPass
$Opt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# ============================================================
# Helpers
# ============================================================
function Get-StationsWithWinRM {
    $r = @{}
    foreach ($s in $Stations) {
        $ip = $s.IP
        Write-Host "  Checking $ip..." -NoNewline
        try {
            $t = Test-NetConnection $ip -Port $WinRMPort -WarningAction SilentlyContinue -TimeoutSeconds 5 -ErrorAction Stop
            if ($t.TcpTestSucceeded) {
                $r[$ip] = $true
                Write-Host " WINRM OK" -ForegroundColor Green
            } else {
                $r[$ip] = $false
                Write-Host " WINRM CLOSED" -ForegroundColor Red
            }
        } catch {
            $r[$ip] = $false
            Write-Host " WINRM ERROR" -ForegroundColor Red
        }
    }
    return $r
}

function Test-FlaskAlive {
    param($IP, $Port)
    try {
        $t = Test-NetConnection $IP -Port $Port -WarningAction SilentlyContinue -TimeoutSeconds 5 -ErrorAction Stop
        return $t.TcpTestSucceeded
    } catch {
        return $false
    }
}

function Restart-FlaskOnStation {
    param($IP, $StationName, $Code)

    $script = @"
`$pythonPaths = @(
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe",
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe",
    "C:\Python311\python.exe",
    "C:\Python310\python.exe",
    "C:\Python39\python.exe",
    "C:\Python38\python.exe"
)
`$python = `$null
foreach (`$p in `$pythonPaths) {
    if (Test-Path `$p) { `$python = `$p; break }
}

if (-not `$python) {
    Write-Output "PYTHON_NOT_FOUND"
    exit 1
}

`$appDir = "C:\LineSupervisor"
`$appFile = "`$appDir\lineSupervisor.py"

# Kill existing Flask on port $Port
`$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if (`$existing) {
    `$pid = (Get-Process -Id `$existing[0].OwningProcess -ErrorAction SilentlyContinue).Id
    if (`$pid) {
        Stop-Process -Id `$pid -Force -ErrorAction SilentlyContinue
        Write-Output "KILLED_old_pid_`$pid"
    }
}

Start-Sleep 2

# Ensure directory
if (-not (Test-Path `$appDir)) {
    New-Item -ItemType Directory -Path `$appDir -Force | Out-Null
}

# Start Flask
`$logFile = "`$appDir\flask_`$Port.log"
`$errLog = "`$appDir\flask_`$Port.err"
`$proc = Start-Process -FilePath `$python -ArgumentList `$appFile -WorkingDirectory `$appDir -WindowStyle Hidden -PassThru -RedirectStandardError `$errLog
Start-Sleep 5

# Verify
`$stillRunning = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if (`$stillRunning) {
    Write-Output "RESTARTED_ok_pid_`$(`$proc.Id)"
} else {
    Write-Output "RESTARTED_failed"
}
"@

    try {
        $session = New-PSSession -ComputerName $IP -Credential $Cred -Authentication Basic -SessionOption $Opt -ErrorAction Stop
        $output = Invoke-Command -Session $session -ScriptBlock $script -ErrorAction Stop
        Remove-PSSession $session
        return $output.Trim()
    } catch {
        return "WINRM_ERROR: $($_.Exception.Message.Split("`n")[0])"
    }
}

# ============================================================
# LOGGING
# ============================================================
$LogDir = "C:\Users\tianj\Desktop\越南工厂瑞晶\mytools\logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir "station_monitor_$(Get-Date -Format 'yyyyMMdd').log"

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts][$Level] $Msg"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

# ============================================================
# PRE-CHECK: verify WinRM on all stations
# ============================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 瑞晶产线工位监控 — $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Log "=== Monitor started ==="
Write-Log "Checking WinRM connectivity on all stations..."

$reachable = Get-StationsWithWinRM

$allGood = $reachable.Values | Where-Object { $_ -eq $true }
if ($allGood.Count -lt $Stations.Count) {
    Write-Host ""
    Write-Host "WARNING: $($Stations.Count - $allGood.Count) stations have WinRM closed:" -ForegroundColor Yellow
    $Stations | ForEach-Object {
        if (-not $reachable[$_.IP]) {
            Write-Host "  $($_.Code) $($_.IP) - WinRM closed" -ForegroundColor Yellow
            Write-Log "$($_.Code) $($_.IP) - WinRM not reachable" "WARN"
        }
    }
    Write-Host ""
}

Write-Host ""
Write-Host "Starting monitor loop (every ${IntervalSec}s)..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

# ============================================================
# MAIN LOOP
# ============================================================
$loopCount = 0
$restartCount = @{}

while ($true) {
    $loopCount++
    $ts = Get-Date -Format "HH:mm:ss"
    Write-Host "[$ts] Cycle $loopCount — checking..." -ForegroundColor DarkGray

    $allDown = @()

    foreach ($s in $Stations) {
        $ip = $s.IP
        $code = $s.Code
        $name = $s.Name

        if (-not $reachable[$ip]) {
            continue  # Skip stations without WinRM
        }

        # Check Flask on port 8090
        $alive = Test-FlaskAlive -IP $ip -Port $Port

        if ($alive) {
            Write-Host "  $code/$name $ip :8090 OK" -ForegroundColor Green
        } else {
            Write-Host "  $code/$name $ip :8090 DOWN" -ForegroundColor Red
            $allDown += $s

            if (-not $restartCount[$code]) { $restartCount[$code] = 0 }
            $restartCount[$code]++
        }
    }

    # Auto-restart down stations
    if ($allDown.Count -gt 0 -and -not $NoAutoRestart) {
        Write-Host ""
        Write-Host "  === Restarting down stations ===" -ForegroundColor Yellow

        foreach ($s in $allDown) {
            $ip = $s.IP
            $code = $s.Code
            $name = $s.Name

            Write-Log "$code/$name ($ip) is DOWN — restart attempt #$($restartCount[$code])" "WARN"

            $result = Restart-FlaskOnStation -IP $ip -StationName $name -Code $code
            Write-Host "  $code restart result: $result" -ForegroundColor Yellow

            if ($result -match "RESTARTED_ok") {
                Write-Log "$code/$name RESTARTED OK: $result" "OK"
            } else {
                Write-Log "$code/$name RESTART FAILED: $result" "ERROR"
            }

            Start-Sleep 3  # Stagger to avoid overwhelming
        }
    }

    Write-Host ""

    if ($OneShot) {
        Write-Log "=== OneShot mode — exiting ==="
        break
    }

    Start-Sleep $IntervalSec
}
