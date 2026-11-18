# ============================================================
# 鐟炴櫠浜х嚎 NG cycle 涓€閿繙绋嬮儴缃?# 閮ㄧ讲鐩爣: MES server (155) + 鎵€鏈夊伐浣?(90-100, 160)
# 閫氳繃: WinRM (5985) 鈥?SSH (22) 鑷妇瀹屾垚鍚庝細鑷姩鍒囨崲
# 鍑嵁: Administrator / rj  (鏉ヨ嚜 stations_read.txt)
# ============================================================
param(
    [switch]$DeployMES,
    [switch]$DeployStations,
    [switch]$StatusOnly,
    [switch]$Pilot  # 浠呴儴缃?FCT 涓€鍙板仛楠岃瘉
)

$ErrorActionPreference = "Continue"
$WinRMPort = 5985
$SSHPort = 22
$Credential = New-Object System.Management.Automation.PSCredential(
    "Administrator",
    (ConvertTo-SecureString "rj" -AsPlainText -Force)
)
$SessionOpt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# 宸ヤ綅娓呭崟 (浠?stations_read.txt)
$Stations = @(
    @{ Code="02-ICT";        IP="192.168.6.91";  Folder="(03)ICT";        Exe=@("ict_2d_agent.exe","ict_qt_3d_agent.exe") },
    @{ Code="03-FCT";        IP="192.168.6.92";  Folder="(04)FCT";        Exe=@("fct_2d_agent.exe","fct_qt_3d_agent.exe") },
    @{ Code="04-鍒嗘澘鏈?;     IP="192.168.6.93";  Folder="(05)鍒嗘澘鏈?;      Exe=@() },
    @{ Code="05-缁戠爜";       IP="192.168.6.94";  Folder="(06)缁戠爜";        Exe=@() },
    @{ Code="07-缁勮ATE";    IP="192.168.6.95";  Folder="(07)缁勮ATE";     Exe=@() },
    @{ Code="08-瓒呭０";       IP="192.168.6.96";  Folder="(08)瓒呭０";        Exe=@("supersonic_agent.exe","supersonic_qt_3d_agent.exe") },
    @{ Code="09-鎴愬搧鑰佸寲";    IP="192.168.6.97";  Folder="(09)鎴愬搧鑰佸寲";    Exe=@("aging_cab_agent.exe","aging_cab_qt_3d_agent.exe") },
    @{ Code="10-楂樺帇娴嬭瘯";    IP="192.168.6.98";  Folder="(10)楂樺帇娴嬭瘯";    Exe=@() },
    @{ Code="11-鍖呰ATE";    IP="192.168.6.99";  Folder="(11)鍖呰ATE";     Exe=@() },
    @{ Code="12-鍖呰";       IP="192.168.6.100"; Folder="(12)鍖呰";        Exe=@() }
)

$ReworkStation = @{ Code="13-Rework"; IP="192.168.6.160"; Folder="005-鍥炰慨绔欒川閲忓伐浣?; Exe=@("rework_2d_agent.exe","rework_qt_3d_agent.exe") }

$MesServer = @{ Code="MES"; IP="192.168.6.155"; Folder=$null }
$BaseDir = "C:\Users\tianj\Desktop\瓒婂崡宸ュ巶鐟炴櫠\鐟炴櫠瓒婂崡宸ヤ綅-姝ｅ紡鍛藉悕"
$MesServerDir = "C:\Users\tianj\Desktop\瓒婂崡宸ュ巶鐟炴櫠\smt-factory-system\services\api"

function W { param($T,$C="Cyan") Write-Host ""; Write-Host ("="*60) -ForegroundColor $C; Write-Host " $T" -ForegroundColor $C; Write-Host ("="*60) -ForegroundColor $C }
function Get-Session { param($IP)
    try { return New-PSSession -ComputerName $IP -Credential $Credential -Authentication Basic -SessionOption $SessionOpt -ErrorAction Stop }
    catch { Write-Host "  WINRM $IP FAIL: $($_.Exception.Message.Split("`n")[0])" -ForegroundColor Red; return $null }
}

# ============================================================
# 0. STATUS
# ============================================================
function Get-Status {
    W "浜х嚎鐘舵€?($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))"
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
    W "STEP 1: 閮ㄧ讲 MES server.js 鈫?192.168.6.155"
    $s = Get-Session $MesServer.IP
    if (-not $s) { return $false }

    try {
        $backupTs = Get-Date -Format "yyyyMMdd_HHmmss"
        Invoke-Command -Session $s -ScriptBlock {
            param($src, $bak)
            if (Test-Path "$src\server.js") {
                Copy-Item "$src\server.js" "$src\server.js.$bak" -Force
                Write-Host "  [MES] backed up 鈫?server.js.$bak" -ForegroundColor Yellow
            }
        } -ArgumentList "C:\Users\tianj\Desktop\瓒婂崡宸ュ巶鐟炴櫠\smt-factory-system\services\api", $backupTs

        Copy-Item "$MesServerDir\server.js" -Destination "C:\Users\tianj\Desktop\瓒婂崡宸ュ巶鐟炴櫠\smt-factory-system\services\api\server.js" -ToSession $s -Force
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
            Start-Process -FilePath "node" -ArgumentList "start_dev.js" -WorkingDirectory "C:\Users\tianj\Desktop\瓒婂崡宸ュ巶鐟炴櫠\smt-factory-system" -WindowStyle Hidden
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
    W "STEP 2: 閮ㄧ讲鍏变韩妯″潡 ng_release_handler.py + retest_arm.py"
    $sharedSrcDir = "$BaseDir\004-鎵嬪姩绾?
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
    W "STEP 3: 閮ㄧ讲鍚勭珯 core + exe"

    foreach ($s in $StationList) {
        $ip = $s.IP
        $folder = $s.Folder
        $exes = $s.Exe
        if (-not $exes -or $exes.Count -eq 0) {
            Write-Host "  [$($s.Code)] $ip 鈥?no exe (skip)" -ForegroundColor Gray
            continue
        }
        Write-Host ""
        Write-Host "  [$($s.Code)] $ip ($folder) ..." -ForegroundColor Cyan
        $session = Get-Session $ip
        if (-not $session) { continue }

        try {
            $srcFolder = "$BaseDir\004-鎵嬪姩绾縗$folder"
            if (-not (Test-Path $srcFolder)) {
                Write-Host "    婧愮爜鐩綍涓嶅瓨鍦? $srcFolder" -ForegroundColor Red
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

            $sharedSrc = "$BaseDir\004-鎵嬪姩绾?
            foreach ($f in @("ng_release_handler.py","retest_arm.py","station_arrival_core.py","station_history_core.py","station_maintenance_core.py","station_core_contract.py")) {
                $localF = Join-Path $sharedSrc $f
                if (Test-Path $localF) {
                    Copy-Item $localF -Destination "C:\Stations\shared\" -ToSession $session -Force
                }
            }

            $coreFile = Switch ($folder) {
                "(03)ICT"        { "ict_core.py" }
                "(04)FCT"        { "fct_core.py" }
                "(08)瓒呭０"       { "supersonic_core.py" }
                "(09)鎴愬搧鑰佸寲"   { "aging_cab_core.py" }
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
    W "STEP 4: 閮ㄧ讲鍥炰慨绔?(192.168.6.160)"
    $ip = $ReworkStation.IP
    Write-Host "  [$($ReworkStation.Code)] $ip ..." -ForegroundColor Cyan
    $session = Get-Session $ip
    if (-not $session) {
        Write-Host "    WINRM FAIL 鈥?retry after SSH bootstrap completes" -ForegroundColor Yellow
        return
    }

    try {
        Invoke-Command -Session $session -ScriptBlock {
            if (-not (Test-Path "C:\Stations")) { New-Item -ItemType Directory -Path "C:\Stations" -Force | Out-Null }
            if (-not (Test-Path "C:\Stations\shared")) { New-Item -ItemType Directory -Path "C:\Stations\shared" -Force | Out-Null }
        }

        $reworkDir = "$BaseDir\005-鍥炰慨绔欒川閲忓伐浣?
        foreach ($f in @("ng_release_handler.py","retest_arm.py")) {
            $local = "$BaseDir\004-鎵嬪姩绾縗$f"
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
# 5. RESTART STATION SERVICES
# ============================================================
function Restart-Stations {
    param($StationList)
    W "STEP 5: 閲嶅惎鍚勫伐浣嶆湇鍔?
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
Write-Host " 鐟炴櫠浜х嚎 NG cycle 涓€閿繙绋嬮儴缃?鈥?$(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($StatusOnly) { Get-Status; exit 0 }

if ($Pilot) {
    W "PILOT: 浠呴儴缃?FCT (192.168.6.92) 楠岃瘉"
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
    Restart-Stations $Stations
    Restart-Stations @($ReworkStation)
}

Get-Status
