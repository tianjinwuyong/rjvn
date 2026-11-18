# install_ssh_smb.ps1
# Run as Administrator on each target station to install OpenSSH + open ports 22 and 445
# No arguments needed

$ErrorActionPreference = "SilentlyContinue"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " OpenSSH + Firewall Setup (Ports 22, 445)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

$hostname = $env:COMPUTERNAME
$ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Manual | Where-Object { $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress

Write-Host "[$hostname] [$ip]" -ForegroundColor Yellow
Write-Host ""

# ---- Port 22: OpenSSH Server ----
Write-Host "Step 1: Installing OpenSSH Server..." -ForegroundColor White

$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -ne "Installed") {
    $result = Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
    if ($result.RestartNeeded) {
        Write-Host "  Restart needed after OpenSSH install." -ForegroundColor Yellow
    } else {
        Write-Host "  OpenSSH installed." -ForegroundColor Green
    }
} else {
    Write-Host "  OpenSSH already installed." -ForegroundColor Gray
}

# Start and enable sshd
Write-Host "Step 2: Starting sshd service..." -ForegroundColor White
$svc = Get-Service -Name sshd -ErrorAction SilentlyContinue
if ($svc) {
    Start-Service sshd -ErrorAction SilentlyContinue
    Set-Service sshd -StartupType Automatic
    Write-Host "  sshd started (StartupType=Automatic)." -ForegroundColor Green
} else {
    Write-Host "  sshd service NOT found!" -ForegroundColor Red
}

# ---- Firewall rules ----
Write-Host "Step 3: Opening firewall ports 22 and 445..." -ForegroundColor White

# Port 22 - SSH
$rule22 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not $rule22) {
    New-NetFirewallRule -Name "Port22-Open" `
        -DisplayName "SSH (Port 22)" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 22 `
        -Action Allow `
        -Profile Any `
        -Enabled True `
        | Out-Null
    Write-Host "  Port 22 rule created." -ForegroundColor Green
} else {
    if ($rule22.Action -ne "Allow") {
        Enable-NetFirewallRule -Name "Port22-Open"
    }
    Write-Host "  Port 22 rule already exists." -ForegroundColor Gray
}

# Port 445 - SMB
$rule445 = Get-NetFirewallRule -Name "Port445-Open" -ErrorAction SilentlyContinue
if (-not $rule445) {
    New-NetFirewallRule -Name "Port445-Open" `
        -DisplayName "SMB (Port 445)" `
        -Direction Inbound `
        -Protocol TCP `
        -LocalPort 445 `
        -Action Allow `
        -Profile Any `
        -Enabled True `
        | Out-Null
    Write-Host "  Port 445 rule created." -ForegroundColor Green
} else {
    if ($rule445.Action -ne "Allow") {
        Enable-NetFirewallRule -Name "Port445-Open"
    }
    Write-Host "  Port 445 rule already exists." -ForegroundColor Gray
}

# OpenSSH default rule
$ruleSSHD = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if ($ruleSSHD) {
    if ($ruleSSHD.Action -ne "Allow") {
        Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
        Write-Host "  OpenSSH-Server-In-TCP rule enabled." -ForegroundColor Green
    }
}

# ---- Verify ----
Write-Host ""
Write-Host "Step 4: Verification..." -ForegroundColor White

$port22 = $null
$port445 = $null
$svcRunning = $null

try {
    $sock = [System.Net.Sockets.TcpClient]::new()
    $sock.Connect("127.0.0.1", 22)
    $port22 = $true
    $sock.Close()
} catch { $port22 = $false }

try {
    $sock2 = [System.Net.Sockets.TcpClient]::new()
    $sock2.Connect("127.0.0.1", 445)
    $port445 = $true
    $sock2.Close()
} catch { $port445 = $false }

$svcRunning = (Get-Service -Name sshd -ErrorAction SilentlyContinue).Status -eq "Running"

Write-Host "  Port 22 (SSH):    $(if($port22){'LISTENING'}else{'NOT LISTENING'})" -ForegroundColor $(if($port22){'Green'}else{'Red'})
Write-Host "  Port 445 (SMB):   $(if($port445){'LISTENING'}else{'NOT LISTENING'})" -ForegroundColor $(if($port445){'Green'}else{'Red'})
Write-Host "  sshd service:     $(if($svcRunning){'RUNNING'}else{'NOT RUNNING'})" -ForegroundColor $(if($svcRunning){'Green'}else{'Red'})

Write-Host ""
if ($port22 -and $svcRunning) {
    Write-Host "SUCCESS: SSH is ready on port 22." -ForegroundColor Green
    Write-Host "You can now connect via: ssh <user>@$ip" -ForegroundColor Green
} else {
    Write-Host "WARNING: Something may not be working correctly." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Press Enter to exit..."
Read-Host
