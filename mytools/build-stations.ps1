# ============================================================
# Build all 10 manual line station .exe files and deploy to D:\Stations
# ============================================================

$ErrorActionPreference = "Continue"

$stations = @(
    @{ ip="192.168.6.91";  name="ICT";           srcDir="(03)ICT";            srcFile="ICT station.py";           exeName="ICT_station.exe" },
    @{ ip="192.168.6.92";  name="FCT";           srcDir="(04)FCT";             srcFile="FCT station.py";           exeName="FCT_station.exe" },
    @{ ip="192.168.6.93";  name="Depanel";        srcDir="(05)PCBA分板工位";     srcFile="组装ATE station.py";       exeName="PCBADividerStation.exe" },
    @{ ip="192.168.6.94";  name="QRBinding";      srcDir="(06)PCBA外壳绑码";     srcFile="qrbinding.py";             exeName="QRBinding_v2.exe" },
    @{ ip="192.168.6.95";  name="AssemblyATE";    srcDir="(07)组装ATE";          srcFile="组装ATE station.py";       exeName="AssemblyATE.exe" },
    @{ ip="192.168.6.96";  name="Ultrasonic";     srcDir="(08)超声";             srcFile="组装ATE station.py";       exeName="UltrasonicStation.exe" },
    @{ ip="192.168.6.97";  name="AgingCab";       srcDir="(09)成品老化";          srcFile="成品老化柜 station.py";    exeName="AgingCab.exe" },
    @{ ip="192.168.6.98";  name="HiVoltATE";      srcDir="(10)高压ATE";          srcFile="高压ATE station.py";       exeName="HiVoltATE.exe" },
    @{ ip="192.168.6.99";  name="PackingATE";     srcDir="(11)包装ATE";          srcFile="包装ATE station.py";       exeName="PackingATE.exe" },
    @{ ip="192.168.6.100"; name="Packing";        srcDir="(13)栈板绑码";          srcFile="包装工位 station.py";       exeName="PackingStation.exe" }
)

$baseSrc = "C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名\004-手动线"
$buildRoot = "C:\Users\tianj\Desktop\越南工厂瑞晶\build_output"
$deployPass = "rj"
$secPass = ConvertTo-SecureString $deployPass -AsPlainText -Force
$creds = New-Object System.Management.Automation.PSCredential "Administrator", $secPass
$sessionOpt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

# Hidden imports needed by station.py files
$hiddenImports = "--hidden-import=openpyxl --hidden-import=websockets --hidden-import=tkinter --hidden-import=collections --hidden-import=datetime --hidden-import=http --hidden-import=urllib --hidden-import=wave --hidden-import=struct --hidden-import=math --hidden-import=ctypes --hidden-import=tempfile --hidden-import=re --hidden-import=socket --hidden-import=queue --hidden-import=winreg --hidden-import=asyncio"

function New-PSSessionSafe {
    param($ip)
    try {
        return New-PSSession -ComputerName $ip -Credential $creds -Authentication Basic -SessionOption $sessionOpt -ErrorAction Stop
    } catch { return $null }
}

# ============================================================
# STEP 1: Build all stations
# ============================================================
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " STEP 1: Building all station .exe files" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $buildRoot)) { New-Item -ItemType Directory -Path $buildRoot -Force | Out-Null }

foreach ($st in $stations) {
    $srcDir = Join-Path $baseSrc $st.srcDir
    $srcFile = Join-Path $srcDir $st.srcFile
    $stBuildDir = Join-Path $buildRoot $st.name
    $distDir = Join-Path $stBuildDir "dist"
    $specFile = Join-Path $stBuildDir "$($st.name).spec"

    Write-Host ""
    Write-Host "[$($st.name)] Building $($st.srcFile)..." -ForegroundColor Yellow

    if (-not (Test-Path $srcFile)) {
        Write-Host "  SOURCE NOT FOUND: $srcFile" -ForegroundColor Red
        continue
    }

    # Create build dir
    if (-not (Test-Path $stBuildDir)) { New-Item -ItemType Directory -Path $stBuildDir -Force | Out-Null }

    # Write spec file
    $specContent = @"
# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(10000)

a = Analysis(
    ['$($srcFile -replace '\\', '\\\\')'],
    pathex=['$($stBuildDir -replace '\\', '\\\\')'],
    binaries=[],
    datas=[],
    hiddenimports=['openpyxl', 'websockets', 'tkinter', 'collections', 'datetime',
                   'http.server', 'http.client', 'urllib.request', 'urllib.error', 'urllib.parse',
                   'wave', 'struct', 'math', 'ctypes', 'tempfile', 're', 'socket', 'queue',
                   'winreg', 'asyncio', 'PIL', 'PIL._imaging'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='$($st.exeName -replace '.exe', '')',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"@

    $specContent | Out-File -FilePath $specFile -Encoding UTF8

    # Run PyInstaller
    Push-Location $stBuildDir
    try {
        $pyiCmd = "pyinstaller --clean --noconfirm --distpath `"$distDir`" --workpath `"$stBuildDir\build`" `"$specFile`" 2>&1"
        Write-Host "  Running PyInstaller..." -ForegroundColor Gray
        $result = Invoke-Expression $pyiCmd

        # Check if exe was created
        $builtExe = Join-Path $distDir $st.exeName
        if (Test-Path $builtExe) {
            $sz = [math]::Round((Get-Item $builtExe).Length / 1MB, 2)
            Write-Host "  SUCCESS: $($st.exeName) ($sz MB)" -ForegroundColor Green
        } else {
            Write-Host "  FAILED: exe not found at $builtExe" -ForegroundColor Red
            Write-Host "  PyInstaller output:" -ForegroundColor Yellow
            $result | Select-Object -Last 20 | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
        }
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Build complete. Output: $buildRoot" -ForegroundColor Green
Write-Host ""
