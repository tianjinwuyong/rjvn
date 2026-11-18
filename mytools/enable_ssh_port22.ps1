# =============================================================================
# Enable SSH + Port 22 on THIS STATION
# Copy to USB → Run on each station as Administrator
# Right-click → "Run with PowerShell" (Run as Administrator)
# =============================================================================

#Requires -RunAsAdministrator
$ErrorActionPreference = "SilentlyContinue"

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║     Enable SSH Server + Port 22 on This PC      ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Install OpenSSH Server ──
Write-Host "  [1/4] Installing OpenSSH Server..." -ForegroundColor Yellow -NoNewline
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -eq "Installed") {
    Write-Host " already installed" -ForegroundColor Green
} else {
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
    Write-Host " DONE" -ForegroundColor Green
}

# ── Step 2: Start SSH Service ──
Write-Host "  [2/4] Starting SSH service..." -ForegroundColor Yellow -NoNewline
Start-Service sshd
Set-Service sshd -StartupType Automatic
if ((Get-Service sshd).Status -eq "Running") {
    Write-Host " RUNNING" -ForegroundColor Green
} else {
    Write-Host " FAILED" -ForegroundColor Red
}

# ── Step 3: Open port 22 in firewall ──
Write-Host "  [3/4] Opening firewall port 22..." -ForegroundColor Yellow -NoNewline

# Method A: OpenSSH rule
$rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if ($rule) {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
    Write-Host " OpenSSH rule enabled" -ForegroundColor Green
} else {
    # Method B: Create via netsh (most reliable)
    netsh advfirewall firewall add rule name="SSH Port 22" dir=in action=allow protocol=TCP localport=22 | Out-Null
    Write-Host " rule created via netsh" -ForegroundColor Green
}

# Also ensure via netsh (belt and suspenders)
netsh advfirewall firewall add rule name="OpenSSH Server sshd" dir=in action=allow protocol=TCP localport=22 | Out-Null

# ── Step 4: Verify ──
Write-Host "  [4/4] Verifying..." -ForegroundColor Yellow
$listening = Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue
if ($listening) {
    Write-Host "  ✅ Port 22 is LISTENING - SSH is ready!" -ForegroundColor Green
    $ip = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | Select-Object -First 1).IPAddress
    Write-Host ""
    Write-Host "  Connect from another PC:" -ForegroundColor Cyan
    Write-Host "    ssh $env:USERNAME@$ip" -ForegroundColor White
} else {
    Write-Host "  ❌ Port 22 NOT listening - check sshd service" -ForegroundColor Red
}

Write-Host ""
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host "  DONE - SSH server is ready on this machine" -ForegroundColor Green
Write-Host ""
pause
