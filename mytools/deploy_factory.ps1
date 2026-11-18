# ============================================================
# 瑞晶产线统一部署系统
# 手动线 11 台工位 + Flask 线长看板
# 部署脚本 — 从 95 运行
# ============================================================

param(
    [string]$ShareHost = "192.168.6.95",
    [string]$LocalDeploy = "C:\LineSupervisor",
    [string]$ShareName = "LineSupervisor",
    [string]$StationDeploy = "C:\Stations",
    [string]$DeployPass = "rj",
    [PSCredential]$Credential = $null,
    [switch]$DeployOnly,
    [switch]$StartOnly,
    [switch]$StatusOnly,
    [switch]$Monitor,
    [switch]$RestartAll,
    [int]$CheckInterval = 30
)

$ErrorActionPreference = "Continue"
$WinRMPort = 5985
$FlaskPort = 8090
$UNCShare = "\\$ShareHost\$ShareName`$"

# ============================================================
# 工位清单 — 手动线
# ============================================================
$Stations = @(
    @{ Code="02-ICT";      IP="192.168.6.91";  Name="ICT";        Folder="ICT";          Exes=@("ICT_station.exe","apiserver_fwd_ict.exe") },
    @{ Code="03-FCT";      IP="192.168.6.92";  Name="FCT";        Folder="FCT";          Exes=@("FCT_station.exe") },
    @{ Code="04-分板机";   IP="192.168.6.93";  Name="分板机";      Folder="PCBADivider";   Exes=@("PCBADividerStation.exe") },
    @{ Code="05-绑码";     IP="192.168.6.94";  Name="绑码";        Folder="QRBinding";     Exes=@("QRBinding_v2.exe") },
    @{ Code="06-激光打标"; IP="192.168.6.95";  Name="激光打标";    Folder=$null;           Exes=@() },
    @{ Code="07-组装ATE";  IP="192.168.6.95";  Name="组装ATE";    Folder="AssemblyATE";    Exes=@("AssemblyATE.exe","ScannerHelper_ATE.exe") },
    @{ Code="08-超声";     IP="192.168.6.96";  Name="超声";        Folder="Ultrasonic";    Exes=@("UltrasonicStation.exe") },
    @{ Code="09-成品老化";  IP="192.168.6.97";  Name="成品老化";    Folder="AgingCab";      Exes=@("AgingCab.exe") },
    @{ Code="10-高压测试";  IP="192.168.6.98";  Name="高压测试";    Folder="HiVoltATE";     Exes=@("HiVoltATE.exe") },
    @{ Code="11-包装ATE";  IP="192.168.6.99";  Name="包装ATE";     Folder="PackingATE";    Exes=@("PackingATE.exe") },
    @{ Code="12-包装";     IP="192.168.6.100"; Name="包装";         Folder="PackingStation";Exes=@("PackingStation.exe") }
)

# 源码路径
$FlaskSource = "C:\Users\tianj\Desktop\越南工厂瑞晶\线长看板系统"
$StationSource = "C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名\004-手动线"

if (-not $Credential) {
    $secPass = ConvertTo-SecureString $DeployPass -AsPlainText -Force
    $Credential = New-Object System.Management.Automation.PSCredential "Administrator", $secPass
}
$SessionOpt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# ============================================================
# Helpers
# ============================================================
function Get-PSSessionSafe {
    param($IP)
    try {
        return New-PSSession -ComputerName $IP -Credential $Credential -Authentication Basic -SessionOption $SessionOpt -ErrorAction Stop
    } catch { return $null }
}

function Write-Step {
    param([string]$T, [string]$C = "Cyan")
    Write-Host ""; Write-Host ("=" * 60) -ForegroundColor $C; Write-Host " $T" -ForegroundColor $C; Write-Host ("=" * 60) -ForegroundColor $C
}

# ============================================================
# STEP 0: 在 95 创建共享文件夹
# ============================================================
function Step-SetupShare {
    Write-Step "STEP 0: 创建网络共享 $UNCShare"

    $s = Get-PSSessionSafe $ShareHost
    if (-not $s) { Write-Host "  无法连接 $ShareHost" -ForegroundColor Red; return $false }

    Invoke-Command -Session $s -ScriptBlock {
        param($lp, $sn)

        if (-not (Test-Path $lp)) { New-Item -ItemType Directory -Path $lp -Force | Out-Null }
        if (-not (Test-Path "$lp\logs")) { New-Item -ItemType Directory -Path "$lp\logs" -Force | Out-Null }

        $sn2 = $sn + "`$"
        $exist = Get-SmbShare -Name $sn2 -ErrorAction SilentlyContinue
        if (-not $exist) {
            New-SmbShare -Name $sn2 -Path $lp -FullAccess "Everyone" -ReadAccess "Everyone" -Force | Out-Null
        }

        netsh advfirewall firewall add rule name="SMB_LineSupervisor" dir=in action=allow protocol=tcp localport=445 profile=any 2>$null | Out-Null

        Write-Host "  共享: \\$env:COMPUTERNAME\$sn2 → $lp" -ForegroundColor Green

    } -ArgumentList $LocalDeploy, $ShareName

    Remove-PSSession $s
    return $true
}

# ============================================================
# STEP 1: 同步 Flask 代码到 95 共享文件夹
# ============================================================
function Step-SyncFlask {
    Write-Step "STEP 1: 同步 Flask 到 $UNCShare"

    if (-not (Test-Path $FlaskSource)) {
        Write-Host "  源码不存在: $FlaskSource" -ForegroundColor Red; return $false
    }

    $s = Get-PSSessionSafe $ShareHost
    if (-not $s) { Write-Host "  无法连接 $ShareHost" -ForegroundColor Red; return $false }

    Invoke-Command -Session $s -ScriptBlock {
        param($src, $dest)

        $ErrorActionPreference = "Continue"
        $count = 0

        $exts = @("*.py", "*.yaml", "*.yml", "*.txt", "*.html", "*.css", "*.js")
        foreach ($ext in $exts) {
            $files = Get-ChildItem -Path $src -Filter $ext -Recurse -File -ErrorAction SilentlyContinue
            foreach ($f in $files) {
                $rel = $f.FullName.Replace($src, "").TrimStart("\")
                $dstDir = Join-Path $dest ($rel -replace "[^\\]+$", "")
                if (-not (Test-Path $dstDir)) { New-Item -ItemType Directory -Path $dstDir -Force | Out-Null }
                Copy-Item -Path $f.FullName -Destination $dstDir -Force
                $count++
            }
        }

        foreach ($dir in @("templates", "static")) {
            $sdir = Join-Path $src $dir
            $ddir = Join-Path $dest $dir
            if (Test-Path $sdir) {
                if (Test-Path $ddir) { Remove-Item $ddir -Recurse -Force }
                Copy-Item -Path $sdir -Destination $dest -Recurse -Force
                $count++
            }
        }

        $core = Join-Path $dest "lineSupervisor.py"
        if (Test-Path $core) {
            $sz = (Get-Item $core).Length
            Write-Host "  Synced $count files — lineSupervisor.py OK ($sz bytes)" -ForegroundColor Green
        } else {
            Write-Host "  lineSupervisor.py NOT FOUND!" -ForegroundColor Red
        }

    } -ArgumentList $FlaskSource, $LocalDeploy

    Remove-PSSession $s
    return $true
}

# ============================================================
# STEP 2: 部署工位 EXE 到各工位
# ============================================================
function Step-DeployStationExes {
    Write-Step "STEP 2: 部署工位 EXE"

    foreach ($st in $Stations) {
        $ip = $st.IP
        $code = $st.Code
        $name = $st.Name
        $folder = $st.Folder
        $exes = $st.Exes

        Write-Host ""
        Write-Host "  [$code] $name ($ip)..." -ForegroundColor Cyan

        if (-not $exes -or $exes.Count -eq 0) {
            Write-Host "    (Flask only — skip exe)" -ForegroundColor Gray
            continue
        }

        $s = Get-PSSessionSafe $ip
        if (-not $s) { Write-Host "    WINRM FAIL" -ForegroundColor Red; continue }

        try {
            $srcFolder = Join-Path $StationSource $folder
            if (-not (Test-Path $srcFolder)) {
                Write-Host "    源码目录不存在: $srcFolder" -ForegroundColor Red
                Remove-PSSession $s; continue
            }

            Invoke-Command -Session $s -ScriptBlock {
                if (-not (Test-Path "C:\Stations")) { New-Item -ItemType Directory -Path "C:\Stations" -Force | Out-Null }
            }

            $copied = 0
            foreach ($exe in $exes) {
                $srcExe = Join-Path $srcFolder "dist" $exe
                if (Test-Path $srcExe) {
                    Copy-Item -Path $srcExe -Destination "C:\Stations\" -ToSession $s -Force
                    $copied++
                    Write-Host "    + $exe" -ForegroundColor Green
                } else {
                    $srcExe2 = Join-Path $srcFolder $exe
                    if (Test-Path $srcExe2) {
                        Copy-Item -Path $srcExe2 -Destination "C:\Stations\" -ToSession $s -Force
                        $copied++
                        Write-Host "    + $exe" -ForegroundColor Green
                    } else {
                        Write-Host "    - $exe NOT FOUND" -ForegroundColor Yellow
                    }
                }
            }

            $distDir = Join-Path $srcFolder "dist"
            if (Test-Path $distDir) {
                $dbs = Get-ChildItem -Path $distDir -Filter "*.db" -File -ErrorAction SilentlyContinue
                foreach ($db in $dbs) {
                    Copy-Item -Path $db.FullName -Destination "C:\Stations\" -ToSession $s -Force
                }
            }

            Write-Host "    Deployed $copied exe(s)" -ForegroundColor Green

        } catch {
            Write-Host ("    ERROR: " + $_.Exception.Message.Split("`n")[0]) -ForegroundColor Red
        }

        Remove-PSSession $s
    }
}

# ============================================================
# STEP 3: 创建启动脚本 + 计划任务
# ============================================================
function Step-CreateLaunchers {
    Write-Step "STEP 3: 创建启动脚本 + 计划任务"

    foreach ($st in $Stations) {
        $ip = $st.IP
        $code = $st.Code
        $name = $st.Name
        $folder = $st.Folder
        $exes = $st.Exes

        Write-Host "  [$code] $name ($ip)..." -NoNewline

        $s = Get-PSSessionSafe $ip
        if (-not $s) { Write-Host " WINRM FAIL" -ForegroundColor Red; continue }

        try {
            Invoke-Command -Session $s -ScriptBlock {
                param($code, $name, $folder, $exesJson, $unc, $port)

                $ErrorActionPreference = "Continue"
                $exes = $exesJson | ConvertFrom-Json

                if (-not (Test-Path "C:\Stations")) { New-Item -ItemType Directory -Path "C:\Stations" -Force | Out-Null }
                if (-not (Test-Path "C:\LineSupervisor")) { New-Item -ItemType Directory -Path "C:\LineSupervisor" -Force | Out-Null }
                if (-not (Test-Path "C:\LineSupervisor\logs")) { New-Item -ItemType Directory -Path "C:\LineSupervisor\logs" -Force | Out-Null }

                # Flask 启动脚本
                $flaskScript = @"
# 瑞晶 Flask 启动脚本
`$python = `$null
foreach (`$p in @(
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python314\python.exe",
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe",
    "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe",
    "C:\Python314\python.exe","C:\Python311\python.exe","C:\Python310\python.exe"
)) {
    if (Test-Path `$p) { `$python = `$p; break }
}
if (-not `$python) { Write-Host "Python not found"; exit 1 }

`$appPath = "$unc\lineSupervisor.py"
`$logDir = "C:\LineSupervisor\logs"
`$port = $port

`$old = Get-NetTCPConnection -LocalPort `$port -ErrorAction SilentlyContinue
if (`$old) {
    `$pid = (Get-Process -Id `$old[0].OwningProcess -ErrorAction SilentlyContinue).Id
    if (`$pid) { Stop-Process -Id `$pid -Force -ErrorAction SilentlyContinue }
}
Start-Sleep 3

& `$python -m pip install flask pymysql pyyaml requests paramiko --quiet --user 2>&1 | Out-Null

`$proc = Start-Process -FilePath `$python -ArgumentList "`"$appPath`"" -WorkingDirectory "C:\LineSupervisor" -WindowStyle Hidden -PassThru -RedirectStandardError "`$logDir\flask_`$port.err"
Start-Sleep 6

`$stillUp = Get-NetTCPConnection -LocalPort `$port -ErrorAction SilentlyContinue
if (`$stillUp) {
    Write-Host "[`$(Get-Date)] Flask OK PID:`$(`$proc.Id) port:`$port"
    exit 0
} else {
    Write-Host "[`$(Get-Date)] Flask FAILED"
    exit 1
}
"@
                $flaskScript | Out-File -FilePath "C:\LineSupervisor\launch_flask.ps1" -Encoding UTF8

                # 工位 EXE 启动脚本
                if ($exes -and $exes.Count -gt 0) {
                    $exeListStr = ($exes | ForEach-Object { "`"`"$_`"" }) -join ","
                    $stationScript = @"
`$exes = @($exeListStr)
`$dir = "C:\Stations"
foreach (`$e in `$exes) {
    `$p = Join-Path `$dir `$e
    `$kill = "taskkill /F /IM `$e"
    Invoke-Expression `$kill 2>`$null
    if (Test-Path `$p) {
        Write-Host "[`$(Get-Date)] Start `$e"
        Start-Process -FilePath `$p -WorkingDirectory `$dir -WindowStyle Hidden
    }
}
"@
                    $stationScript | Out-File -FilePath "C:\Stations\launch_stations.ps1" -Encoding UTF8
                }

                Write-Output "OK"

            } -ArgumentList $code, $name, $folder, ($exes | ConvertTo-Json), $UNCShare, $FlaskPort | Out-Null

            # Flask 计划任务
            $flaskTaskName = "LineSupervisor_Flask"
            Invoke-Command -Session $s -ScriptBlock {
                param($tn, $lp, $port)

                $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$lp\launch_flask.ps1`"" -WorkingDirectory "C:\LineSupervisor"
                $trigger = New-ScheduledTaskTrigger -AtStartup
                $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

                Unregister-ScheduledTask -TaskName $tn -Confirm:$false -ErrorAction SilentlyContinue
                Register-ScheduledTask -TaskName $tn -Trigger $trigger -Action $action -Settings $settings -RunLevel Highest -Force | Out-Null
                Write-Output "FlaskTask:OK"

            } -ArgumentList $flaskTaskName, "C:\LineSupervisor", $FlaskPort | Out-String | ForEach-Object { $_.Trim() }

            # 工位 EXE 计划任务
            if ($exes -and $exes.Count -gt 0) {
                $stationTaskName = "LineSupervisor_Stations"
                Invoke-Command -Session $s -ScriptBlock {
                    param($tn, $sd)

                    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$sd\launch_stations.ps1`"" -WorkingDirectory "C:\Stations"
                    $trigger = New-ScheduledTaskTrigger -AtStartup
                    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

                    Unregister-ScheduledTask -TaskName $tn -Confirm:$false -ErrorAction SilentlyContinue
                    Register-ScheduledTask -TaskName $tn -Trigger $trigger -Action $action -Settings $settings -RunLevel Highest -Force | Out-Null
                    Write-Output "StationTask:OK"

                } -ArgumentList $stationTaskName, "C:\Stations" | Out-String | ForEach-Object { $_.Trim() }
            }

            Write-Host " OK" -ForegroundColor Green

        } catch {
            Write-Host (" ERROR: " + $_.Exception.Message.Split("`n")[0]) -ForegroundColor Red
        }

        if ($s) { Remove-PSSession $s }
    }
}

# ============================================================
# STEP 4: 启动所有服务
# ============================================================
function Step-StartAll {
    Write-Step "STEP 4: 启动所有服务"

    foreach ($st in $Stations) {
        $ip = $st.IP
        $code = $st.Code
        $name = $st.Name
        $exes = $st.Exes

        Write-Host "  [$code] $name ($ip)..." -NoNewline

        $s = Get-PSSessionSafe $ip
        if (-not $s) { Write-Host " WINRM FAIL" -ForegroundColor Red; continue }

        try {
            # 启动 Flask
            $flaskResult = Invoke-Command -Session $s -ScriptBlock {
                param($fp, $port)

                $old = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
                if ($old) {
                    $pid = (Get-Process -Id $old[0].OwningProcess -ErrorAction SilentlyContinue).Id
                    if ($pid) { Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue }
                }
                Start-Sleep 2

                Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$fp\launch_flask.ps1`"" -WindowStyle Hidden
                Start-Sleep 6

                $stillUp = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
                if ($stillUp) { return "FLASK_OK" } else { return "FLASK_FAIL" }

            } -ArgumentList "C:\LineSupervisor", $FlaskPort

            if ($flaskResult.Trim() -eq "FLASK_OK") {
                Write-Host " :$FlaskPort OK" -ForegroundColor Green
            } else {
                Write-Host " :$FlaskPort FAIL" -ForegroundColor Red
            }

            # 启动工位 EXE
            if ($exes -and $exes.Count -gt 0) {
                Invoke-Command -Session $s -ScriptBlock {
                    param($sd, $exeList)

                    $killCmd = ($exeList | ForEach-Object { "taskkill /F /IM `$_" }) -join "; "
                    Invoke-Expression $killCmd 2>$null
                    Start-Sleep 1
                    Start-Process powershell.exe -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$sd\launch_stations.ps1`"" -WindowStyle Hidden

                } -ArgumentList "C:\Stations", $exes | Out-Null

                Write-Host " EXE started" -ForegroundColor Green
            }

        } catch {
            Write-Host (" ERROR: " + $_.Exception.Message.Split("`n")[0]) -ForegroundColor Red
        }

        if ($s) { Remove-PSSession $s }
    }
}

# ============================================================
# STATUS
# ============================================================
function Get-FullStatus {
    Write-Step "产线状态 ($(Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))"

    $up = 0; $down = 0; $noWinRM = 0

    foreach ($st in $Stations) {
        $ip = $st.IP
        $code = $st.Code
        $name = $st.Name
        $exes = $st.Exes

        $winrmOk = $false
        try {
            $t = Test-NetConnection $ip -Port $WinRMPort -WarningAction SilentlyContinue -TimeoutSeconds 3 -ErrorAction Stop
            $winrmOk = $t.TcpTestSucceeded
        } catch {}

        if (-not $winrmOk) {
            Write-Host "  $code/$name $ip  WINRM_CLOSED" -ForegroundColor Red
            $noWinRM++; continue
        }

        $flaskUp = $false
        try {
            $t = Test-NetConnection $ip -Port $FlaskPort -WarningAction SilentlyContinue -TimeoutSeconds 3 -ErrorAction Stop
            $flaskUp = $t.TcpTestSucceeded
        } catch {}

        if ($flaskUp) {
            Write-Host ("  {0}/{1} {2} :{3} OK" -f $code, $name, $ip, $FlaskPort) -ForegroundColor Green
            $up++
        } else {
            Write-Host ("  {0}/{1} {2} :{3} DOWN" -f $code, $name, $ip, $FlaskPort) -ForegroundColor Red
            $down++
        }
    }

    Write-Host ""
    Write-Host ("Flask运行: {0} | 已停止: {1} | WinRM不可达: {2}" -f $up, $down, $noWinRM) -ForegroundColor $(if($down -eq 0 -and $noWinRM -eq 0) { "Green" } else { "Yellow" })
}

# ============================================================
# RESTART ALL
# ============================================================
function Restart-All {
    Write-Step "重启所有 Flask"
    Step-StartAll
}

# ============================================================
# MAIN
# ============================================================
Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host " 瑞晶产线统一部署系统 — $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor Cyan
Write-Host ("=" * 60) -ForegroundColor Cyan

if ($StatusOnly) {
    Get-FullStatus; exit 0
}

if ($RestartAll) {
    Restart-All; exit 0
}

if ($Monitor) {
    Write-Host "Monitor mode — Ctrl+C to stop" -ForegroundColor Yellow
    while ($true) {
        Get-FullStatus
        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] Next in $CheckInterval s..." -ForegroundColor DarkGray
        Start-Sleep $CheckInterval
    }
    exit 0
}

if (-not $DeployOnly -and -not $StartOnly) {
    $ok = Step-SetupShare; if (-not $ok) { exit 1 }
    $ok = Step-SyncFlask; if (-not $ok) { exit 1 }
    Step-DeployStationExes
    Step-CreateLaunchers
    Step-StartAll

    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host " 部署完成!" -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host ""
    Write-Host "Flask: http://192.168.6.95:8090"
    Write-Host "共享: $UNCShare"
    Write-Host ""
    Write-Host "日常维护:" -ForegroundColor Cyan
    Write-Host "  .\deploy_factory.ps1 -StatusOnly" -ForegroundColor Gray
    Write-Host "  .\deploy_factory.ps1 -RestartAll" -ForegroundColor Gray
    Write-Host "  .\deploy_factory.ps1 -Monitor" -ForegroundColor Gray
}

if ($DeployOnly) {
    Step-SetupShare
    Step-SyncFlask
    Step-DeployStationExes
    Step-CreateLaunchers
}

if ($StartOnly) {
    Step-StartAll
}
