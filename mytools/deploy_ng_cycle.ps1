# ============================================================
# 瑞晶产线 NG cycle 一键远程部署
# 部署目标: MES server (155) + 所有工位 (90-100, 160)
# 通过: WinRM (5985) — SSH (22) 自举完成后会自动切换
# 凭据: Administrator / rj  (来自 stations_read.txt)
# ============================================================
param(
    [switch]$DeployMES,
    [switch]$DeployStations,
    [switch]$StatusOnly,
    [switch]$Pilot  # 仅部署 FCT 一台做验证
)

$ErrorActionPreference = "Continue"
$WinRMPort = 5985
$SSHPort = 22
$Credential = New-Object System.Management.Automation.PSCredential(
    "Administrator",
    (ConvertTo-SecureString "rj" -AsPlainText -Force)
)
$SessionOpt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# 工位清单 (从 stations_read.txt)
$Stations = @(
    @{ Code="02-ICT";        IP="192.168.6.91";  Folder="(03)ICT";        Exe=@("ict_2d_agent.exe","ict_qt_3d_agent.exe") },
    @{ Code="03-FCT";        IP="192.168.6.92";  Folder="(04)FCT";        Exe=@("fct_2d_agent.exe","fct_qt_3d_agent.exe") },
    @{ Code="04-分板机";     IP="192.168.6.93";  Folder="(05)分板机";      Exe=@() },
    @{ Code="05-绑码";       IP="192.168.6.94";  Folder="(06)绑码";        Exe=@() },
    @{ Code="07-组装ATE";    IP="192.168.6.95";  Folder="(07)组装ATE";     Exe=@() },
    @{ Code="08-超声";       IP="192.168.6.96";  Folder="(08)超声";        Exe=@("supersonic_agent.exe","supersonic_qt_3d_agent.exe") },
    @{ Code="09-成品老化";    IP="192.168.6.97";  Folder="(09)成品老化";    Exe=@("aging_cab_agent.exe","aging_cab_qt_3d_agent.exe") },
    @{ Code="10-高压测试";    IP="192.168.6.98";  Folder="(10)高压测试";    Exe=@() },
    @{ Code="11-包装ATE";    IP="192.168.6.99";  Folder="(11)包装ATE";     Exe=@() },
    @{ Code="12-CaseBinding"; IP="192.168.6.100"; Folder="(12)外箱绑码";  Exe=@("outer_box_binding_2d_agent.exe","outer_box_binding_qt_3d_agent.exe") }
)

$ReworkStation = @{ Code="13-Rework"; IP="192.168.6.160"; Folder="005-回修站质量工位"; Exe=@("rework_2d_agent.exe","rework_qt_3d_agent.exe") }

$PalletStation = @{ Code="14-PalletBinding"; IP="192.168.6.161"; Folder="(13)栈板绑码"; Exe=@("pallet_binding_2d_agent.exe","pallet_binding_qt_3d_agent.exe"); Protocol="SSH"; SSHUser="admin"; SSHPass="rj" }

$MesServer = @{ Code="MES"; IP="192.168.6.155"; Folder=$null }
$BaseDir = "C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名"
$MesServerDir = "C:\Users\tianj\Desktop\越南工厂瑞晶\smt-factory-system\services\api"

function W { param($T,$C="Cyan") Write-Host ""; Write-Host ("="*60) -ForegroundColor $C; Write-Host " $T" -ForegroundColor $C; Write-Host ("="*60) -ForegroundColor $C }
function Get-Session { param($IP)
    try { return New-PSSession -ComputerName $IP -Credential $Credential -Authentication Basic -SessionOption $SessionOpt -ErrorAction Stop }
    catch { Write-Host "  WINRM $IP FAIL: $($_.Exception.Message.Split("`n")[0])" -ForegroundColor Red; return $null }
}

# ============================================================
# 0. STATUS
# ============================================================
function Get-Status {
    W "产线状态 ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))"
    $up=0; $down=0
    $all = $Stations + @($ReworkStation) + @($MesServer)
    foreach ($s in $all) {
        $ip = $s.IP
        try {
            $winrm = (Test-NetConnection $ip -Port $WinRMPort -WarningAction SilentlyContinue -TimeoutSeconds 3).TcpTestSucceeded
            $ssh = (Test-NetConnection $ip -Port $SSHPort -WarningAction SilentlyContinue -TimeoutSeconds 2).TcpTestSucceeded
            $color = if ($winrm -or $ssh) { "Green"; $up++ } else { "Red"; $down++ }
            $status = "WINRM=$winrm SSH=$ssh"
            Write-Host ("  {0,-12} {1,-15} {2}" -f $s.Code, $ip, $status) -ForegroundColor $color
        } catch {
            Write-Host ("  {0,-12} {1,-15} UNREACHABLE" -f $s.Code, $ip) -ForegroundColor Red
            $down++
        }
    }
    Write-Host ""
    Write-Host ("Reachable: {0} | Unreachable: {1}" -f $up, $down) -ForegroundColor $(if($down -eq 0){"Green"}else{"Yellow"})
}

# ============================================================
# 1. DEPLOY MES SERVER (server.js)
# ============================================================
function Deploy-MES {
    W "STEP 1: 部署 MES server.js → 192.168.6.155"
    $s = Get-Session $MesServer.IP
    if (-not $s) { return $false }

    try {
        $backupTs = Get-Date -Format "yyyyMMdd_HHmmss"
        Invoke-Command -Session $s -ScriptBlock {
            param($src, $bak)
            if (Test-Path "$src\server.js") {
                Copy-Item "$src\server.js" "$src\server.js.$bak" -Force
                Write-Host "  [MES] backed up → server.js.$bak" -ForegroundColor Yellow
            }
        } -ArgumentList "C:\Users\tianj\Desktop\越南工厂瑞晶\smt-factory-system\services\api", $backupTs

        Copy-Item "$MesServerDir\server.js" -Destination "C:\Users\tianj\Desktop\越南工厂瑞晶\smt-factory-system\services\api\server.js" -ToSession $s -Force
        Write-Host "  [MES] server.js deployed" -ForegroundColor Green

        $running = Invoke-Command -Session $s -ScriptBlock {
            Get-NetTCPConnection -LocalPort 8080 -ErrorAction SilentlyContinue | Select-Object -First 1 OwningProcess
        }
        if ($running) {
            $pid = (Invoke-Command -Session $s -ScriptBlock {
                (Get-Process -Id $using:running.OwningProcess -ErrorAction SilentlyContinue).Id
            } -ArgumentList $running)
            if ($pid) {
                Invoke-Command -Session $s -ScriptBlock { Stop-Process -Id $args[0] -Force } -ArgumentList $pid
                Write-Host "  [MES] killed old PID $pid" -ForegroundColor Yellow
                Start-Sleep -Seconds 2
            }
        }

        Invoke-Command -Session $s -ScriptBlock {
            Start-Process -FilePath "node" -ArgumentList "start_dev.js" -WorkingDirectory "C:\Users\tianj\Desktop\越南工厂瑞晶\smt-factory-system" -WindowStyle Hidden
        }
        Write-Host "  [MES] start_dev.js launched" -ForegroundColor Green
        Start-Sleep -Seconds 5

        $alive = Invoke-Command -Session $s -ScriptBlock {
            try {
                $r = Invoke-WebRequest -Uri "http://localhost:8080/api/pda/heartbeats" -TimeoutSec 5 -UseBasicParsing
                return $r.StatusCode -eq 200
            } catch { return $false }
        }
        Write-Host ("  [MES] health check: " + $(if($alive){"ALIVE 200 OK"}else{"FAIL"})) -ForegroundColor $(if($alive){"Green"}else{"Red"})
    } finally {
        Remove-PSSession $s
    }
    return $true
}

# ============================================================
# 2. DEPLOY SHARED MODULES to all stations
# ============================================================
function Deploy-SharedModules {
    param($StationList)
    W "STEP 2: 部署共享模块 ng_release_handler.py + retest_arm.py"
    $sharedSrcDir = "$BaseDir\004-手动线"
    $files = @("ng_release_handler.py", "retest_arm.py")

    foreach ($s in $StationList) {
        $ip = $s.IP
        Write-Host ""
        Write-Host "  [$($s.Code)] $ip ..." -ForegroundColor Cyan
        $session = Get-Session $ip
        if (-not $session) { continue }

        try {
            Invoke-Command -Session $session -ScriptBlock {
                param($target)
                if (-not (Test-Path $target)) { New-Item -ItemType Directory -Path $target -Force | Out-Null }
            } -ArgumentList "C:\Stations\shared"

            foreach ($f in $files) {
                $local = Join-Path $sharedSrcDir $f
                if (Test-Path $local) {
                    Copy-Item $local -Destination "C:\Stations\shared\" -ToSession $session -Force
                    Write-Host "    + shared\$f" -ForegroundColor Green
                }
            }
        } finally {
            Remove-PSSession $session
        }
    }
}

# ============================================================
# 3. DEPLOY CORE FILES + EXE to station
# ============================================================
function Deploy-StationExes {
    param($StationList)
    W "STEP 3: 部署各站 core + exe"

    foreach ($s in $StationList) {
        $ip = $s.IP
        $folder = $s.Folder
        $exes = $s.Exe
        if (-not $exes -or $exes.Count -eq 0) {
            Write-Host "  [$($s.Code)] $ip — no exe (skip)" -ForegroundColor Gray
            continue
        }
        Write-Host ""
        Write-Host "  [$($s.Code)] $ip ($folder) ..." -ForegroundColor Cyan
        $session = Get-Session $ip
        if (-not $session) { continue }

        try {
            $srcFolder = "$BaseDir\004-手动线\$folder"
            if (-not (Test-Path $srcFolder)) {
                Write-Host "    源码目录不存在: $srcFolder" -ForegroundColor Red
                continue
            }

            Invoke-Command -Session $session -ScriptBlock {
                if (-not (Test-Path "C:\Stations")) { New-Item -ItemType Directory -Path "C:\Stations" -Force | Out-Null }
            }

            foreach ($exe in $exes) {
                $localExe = "$srcFolder\dist\$exe"
                if (Test-Path $localExe) {
                    Copy-Item $localExe -Destination "C:\Stations\" -ToSession $session -Force
                    Write-Host "    + $exe" -ForegroundColor Green
                } else {
                    Write-Host "    - $exe NOT FOUND locally" -ForegroundColor Yellow
                }
            }

            $sharedSrc = "$BaseDir\004-手动线"
            foreach ($f in @("ng_release_handler.py","retest_arm.py","station_arrival_core.py","station_history_core.py","station_maintenance_core.py","station_core_contract.py")) {
                $localF = Join-Path $sharedSrc $f
                if (Test-Path $localF) {
                    Copy-Item $localF -Destination "C:\Stations\shared\" -ToSession $session -Force
                }
            }

            $coreFile = Switch ($folder) {
                "(03)ICT"        { "ict_core.py" }
                "(04)FCT"        { "fct_core.py" }
                "(08)超声"       { "supersonic_core.py" }
                "(09)成品老化"   { "aging_cab_core.py" }
                default          { $null }
            }
            if ($coreFile) {
                $coreLocal = "$srcFolder\$coreFile"
                if (Test-Path $coreLocal) {
                    Copy-Item $coreLocal -Destination "C:\Stations\" -ToSession $session -Force
                    Write-Host "    + $coreFile" -ForegroundColor Green
                }
            }
        } finally {
            Remove-PSSession $session
        }
    }
}

# ============================================================
# 4. DEPLOY REWORK STATION
# ============================================================
function Deploy-Rework {
    W "STEP 4: 部署回修站 (192.168.6.160)"
    $ip = $ReworkStation.IP
    Write-Host "  [$($ReworkStation.Code)] $ip ..." -ForegroundColor Cyan
    $session = Get-Session $ip
    if (-not $session) {
        Write-Host "    WINRM FAIL — retry after SSH bootstrap completes" -ForegroundColor Yellow
        return
    }

    try {
        Invoke-Command -Session $session -ScriptBlock {
            if (-not (Test-Path "C:\Stations")) { New-Item -ItemType Directory -Path "C:\Stations" -Force | Out-Null }
            if (-not (Test-Path "C:\Stations\shared")) { New-Item -ItemType Directory -Path "C:\Stations\shared" -Force | Out-Null }
        }

        $reworkDir = "$BaseDir\005-回修站质量工位"
        foreach ($f in @("ng_release_handler.py","retest_arm.py")) {
            $local = "$BaseDir\004-手动线\$f"
            if (Test-Path $local) {
                Copy-Item $local -Destination "C:\Stations\shared\" -ToSession $session -Force
                Write-Host "    + shared\$f" -ForegroundColor Green
            }
        }

        $coreLocal = "$reworkDir\rework_core.py"
        if (Test-Path $coreLocal) {
            Copy-Item $coreLocal -Destination "C:\Stations\" -ToSession $session -Force
            Write-Host "    + rework_core.py" -ForegroundColor Green
        }

        foreach ($exe in $ReworkStation.Exe) {
            $localExe = "$reworkDir\dist\$exe"
            if (Test-Path $localExe) {
                Copy-Item $localExe -Destination "C:\Stations\" -ToSession $session -Force
                Write-Host "    + $exe" -ForegroundColor Green
            }
        }
    } finally {
        Remove-PSSession $session
    }
}

# ============================================================
# 5. DEPLOY PALLET STATION (SSH only — .161)
# ============================================================
function Deploy-PalletStation {
    W "STEP 5: 部署栈板绑码站 (192.168.6.161) via SSH"
    $ip = $PalletStation.IP
    $user = $PalletStation.SSHUser
    $pass = $PalletStation.SSHPass
    $folder = $PalletStation.Folder
    Write-Host "  [$($PalletStation.Code)] $ip ..." -ForegroundColor Cyan

    # Create dirs via SSH
    $sshCmd = "mkdir C:\Stations; mkdir C:\Stations\shared; echo DIRS_OK"
    $result = sshpass -p $pass ssh -o StrictHostKeyChecking=no -o ConnectTimeout=15 "$user@$ip" $sshCmd 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    SSH dirs FAIL: $LASTEXITCODE" -ForegroundColor Red
        return
    }
    Write-Host "    + C:\Stations created" -ForegroundColor Green

    # Copy shared modules
    foreach ($f in @("ng_release_handler.py","retest_arm.py","station_arrival_core.py","station_history_core.py","station_maintenance_core.py","station_core_contract.py")) {
        $local = "$BaseDir\004-手动线\$f"
        if (Test-Path $local) {
            sshpass -p $pass scp -o StrictHostKeyChecking=no $local "$user@$ip`:C:\Stations\shared\" 2>&1 | Out-Null
            Write-Host "    + shared\$f" -ForegroundColor Green
        }
    }

    # Copy core
    $coreLocal = "$BaseDir\004-手动线\$folder\pallet_binding_core.py"
    if (Test-Path $coreLocal) {
        sshpass -p $pass scp -o StrictHostKeyChecking=no $coreLocal "$user@$ip`:C:\Stations\" 2>&1 | Out-Null
        Write-Host "    + pallet_binding_core.py" -ForegroundColor Green
    }

    # Copy exes
    foreach ($exe in $PalletStation.Exe) {
        $localExe = "$BaseDir\004-手动线\$folder\dist\$exe"
        if (Test-Path $localExe) {
            sshpass -p $pass scp -o StrictHostKeyChecking=no $localExe "$user@$ip`:C:\Stations\" 2>&1 | Out-Null
            Write-Host "    + $exe" -ForegroundColor Green
        }
    }

    Write-Host "  [$($PalletStation.Code)] deployed via SSH" -ForegroundColor Green
}

# ============================================================
# 6. RESTART STATION SERVICES
# ============================================================
function Restart-Stations {
    param($StationList)
    W "STEP 5: 重启各工位服务"
    foreach ($s in $StationList) {
        if (-not $s.Exe -or $s.Exe.Count -eq 0) { continue }
        $ip = $s.IP
        Write-Host "  [$($s.Code)] $ip ..." -NoNewline -ForegroundColor Cyan
        $session = Get-Session $ip
        if (-not $session) { Write-Host " WINRM FAIL" -ForegroundColor Red; continue }

        try {
            Invoke-Command -Session $session -ScriptBlock {
                param($exeList)
                $exeList | ForEach-Object {
                    $kill = "taskkill /F /IM $_"
                    Invoke-Expression $kill 2>$null
                }
                Start-Sleep -Seconds 1
                foreach ($e in $exeList) {
                    $p = "C:\Stations\$e"
                    if (Test-Path $p) {
                        Start-Process -FilePath $p -WorkingDirectory "C:\Stations" -WindowStyle Hidden
                    }
                }
            } -ArgumentList $s.Exe
            Write-Host " restarted" -ForegroundColor Green
        } catch {
            Write-Host (" FAIL: " + $_.Exception.Message.Split("`n")[0]) -ForegroundColor Red
        } finally {
            Remove-PSSession $session
        }
    }
}

# ============================================================
# MAIN
# ============================================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host " 瑞晶产线 NG cycle 一键远程部署 — $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($StatusOnly) { Get-Status; exit 0 }

if ($Pilot) {
    W "PILOT: 仅部署 FCT (192.168.6.92) 验证"
    $fctOnly = @($Stations | Where-Object { $_.Code -eq "03-FCT" })
    Deploy-SharedModules $fctOnly
    Deploy-StationExes $fctOnly
    Restart-Stations $fctOnly
    exit 0
}

if ($DeployMES) {
    Deploy-MES
}
if ($DeployStations) {
    Deploy-SharedModules $Stations
    Deploy-StationExes $Stations
    Deploy-Rework
    Deploy-PalletStation
    Restart-Stations $Stations
    Restart-Stations @($ReworkStation)
}

Get-Status