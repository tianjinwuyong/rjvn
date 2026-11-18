# deploy_flask_supervisor.ps1
# Deploys line supervisor Flask app to multiple Windows stations
# Run from any management station with WinRM access

param(
    [string]$DeployPass = "rj",
    [string]$PythonVersion = "3.11"  # or "3.10", "3.12" - check what's installed
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Deploy Flask Line Supervisor to Multiple Stations" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$appName = "LineSupervisor"
$appPort = 8090
$localAppPath = "C:\Users\tianj\Desktop\越南工厂瑞晶\线长看板系统"

# Stations to deploy to (3 for redundancy)
$deployTargets = @(
    @{Name="ICT";   IP="192.168.6.91"},
    @{Name="组装ATE"; IP="192.168.6.95"},
    @{Name="包装ATE"; IP="192.168.6.99"}
)

# Create credential
$secPass = ConvertTo-SecureString $DeployPass -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential "Administrator", $secPass

# Remote setup script
$setupScript = @"
`$ErrorActionPreference = "SilentlyContinue"
`$appName = "$appName"
`$appPort = $appPort

Write-Host "Checking Python..." -ForegroundColor Cyan

# Find Python
`$python = $null
foreach (`$v in @("$env:LOCALAPPDATA\Programs\Python\Python311", "$env:LOCALAPPDATA\Programs\Python\Python310",
                  "$env:LOCALAPPDATA\Programs\Python\Python312", "C:\Python311", "C:\Python310", "C:\Python39", "C:\Python")) {
    if (Test-Path "`$v\python.exe") {
        `$python = "`$v\python.exe"
        break
    }
}
if (-not `$python) {
    Write-Host "Python NOT found. Installing Python 3.11..." -ForegroundColor Yellow
    # Download Python 3.11
    `$installer = "`$env:TEMP\python311_installer.exe"
    Invoke-WebRequest -Uri "https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe" -OutFile `$installer
    Start-Process -FilePath `$installer -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" -Wait
    Start-Sleep 5
    `$python = "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
}

Write-Host "Python: `$python"

# Create app folder
`$appDir = "C:\`$appName"
if (-not (Test-Path `$appDir)) {
    New-Item -ItemType Directory -Path `$appDir -Force | Out-Null
}
Set-Location `$appDir

# Install dependencies
Write-Host "Installing Python packages..." -ForegroundColor Cyan
& `$python -m pip install flask pymysql pyyaml requests paramiko --quiet --user 2>&1 | Out-Null

# Kill existing Flask on port 8090
`$existing = Get-NetTCPConnection -LocalPort `$appPort -ErrorAction SilentlyContinue
if (`$existing) {
    `$procId = (Get-Process -Id `$existing[0].OwningProcess -ErrorAction SilentlyContinue).Id
    if (`$procId) {
        Stop-Process -Id `$procId -Force -ErrorAction SilentlyContinue
        Write-Host "Killed existing process on port `$appPort"
    }
}

Write-Host "Starting Flask on port `$appPort..." -ForegroundColor Green

# Start Flask in background
`$appScript = Get-Content "$appDir\$appName.py" -ErrorAction SilentlyContinue
if (-not `$appScript) {
    Write-Host "WARNING: $appName.py not found at `$appDir" -ForegroundColor Yellow
}

# Run with nohup equivalent
Start-Process -FilePath `$python -ArgumentList "`"$appDir\$appName.py`"" -WindowStyle Hidden

Start-Sleep 3

# Verify
`$stillRunning = Get-NetTCPConnection -LocalPort `$appPort -ErrorAction SilentlyContinue
if (`$stillRunning) {
    Write-Host "SUCCESS: $appName running on port `$appPort" -ForegroundColor Green
} else {
    Write-Host "PARTIAL: Process may have started. Check manually." -ForegroundColor Yellow
}
"@

# Main deployment
foreach ($target in $deployTargets) {
    $ip = $target.IP
    $name = $target.Name
    Write-Host "[$name] $ip ..." -NoNewline

    # Check port first
    $portCheck = $false
    try {
        $c = [System.Net.Sockets.TcpClient]::new()
        $c.Connect($ip, 5985)
        $c.Close()
        $portCheck = $true
    } catch {}

    if (-not $portCheck) {
        Write-Host " WINRM FAIL" -ForegroundColor Red
        continue
    }

    try {
        $session = New-PSSession -ComputerName $ip -Credential $cred -ErrorAction Stop

        # Check if app folder exists
        $appExists = Invoke-Command -Session $session -ScriptBlock {
            Test-Path "C:\$using:appName"
        }

        if (-not $appExists) {
            Write-Host " Creating folder..." -NoNewline
            Invoke-Command -Session $session -ScriptBlock {
                New-Item -ItemType Directory -Path "C:\$using:appName" -Force | Out-Null
            }
        }

        # Copy app files
        Write-Host " Copying files..." -NoNewline
        $files = Get-ChildItem -Path $localAppPath -File
        foreach ($file in $files) {
            if ($file.Extension -in @('.py', '.yaml', '.yml', '.txt', '.html')) {
                Copy-Item -Path $file.FullName -Destination "C:\$appName\" -ToSession $session -Force
            }
        }
        Write-Host " OK" -NoNewline

        # Run setup
        Write-Host " Installing..." -NoNewline
        Invoke-Command -Session $session -ScriptBlock ([scriptblock]::Create($setupScript)) -ErrorAction SilentlyContinue

        # Check port
        Start-Sleep 3
        $running = $false
        Invoke-Command -Session $session -ScriptBlock {
            $running = (Get-NetTCPConnection -LocalPort $using:appPort -ErrorAction SilentlyContinue) -ne $null
        }
        if ($running) {
            Write-Host " OK:8090" -ForegroundColor Green
        } else {
            Write-Host " PARTIAL" -ForegroundColor Yellow
        }

        Remove-PSSession $session

    } catch {
        Write-Host " FAIL: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "Done." -ForegroundColor Cyan
Write-Host "Access any running station at: http://<station-ip>:8090"
Read-Host
