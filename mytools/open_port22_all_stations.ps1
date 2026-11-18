# =============================================================================
# Open Port 22 on ALL Factory Stations
# RIGHT-Click → "Run with PowerShell" (Run as Administrator)
# =============================================================================

#Requires -RunAsAdministrator
$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║     Open Port 22 on ALL Factory Stations        ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# =============================================================================
# Station database
# =============================================================================
$stations = @(
    @{Name="Wavesolder";        IP="192.168.1.10";  User="Admin"}
    @{Name="AOI_Manual";        IP="192.168.6.90";  User="Admin"}
    @{Name="ICT_Manual";        IP="192.168.6.91";  User="Admin"}
    @{Name="FCT_Manual";        IP="192.168.6.92";  User="Administrator"}
    @{Name="Depanel_Manual";    IP="192.168.6.93";  User="Administrator"}
    @{Name="QRCode_Manual";     IP="192.168.6.94";  User="Administrator"}
    @{Name="AssemblyATE_Manual";IP="192.168.6.95";  User="Administrator"}
    @{Name="Ultrasonic_Manual"; IP="192.168.6.96";  User="Administrator"}
    @{Name="Aging_Manual";      IP="192.168.6.97";  User="Administrator"}
    @{Name="HiPot_Manual";      IP="192.168.6.98";  User="Administrator"}
    @{Name="PackagingATE_Manual";IP="192.168.6.99"; User="Administrator"}
    @{Name="Packaging_Manual";  IP="192.168.6.100"; User="Administrator"}
    @{Name="AOI_Auto";          IP="192.168.6.50";  User="Admin"}
    @{Name="ICT_Auto";          IP="192.168.6.51";  User="Admin"}
    @{Name="FCT_Auto";          IP="192.168.6.52";  User="Administrator"}
    @{Name="Depanel_Auto";      IP="192.168.6.53";  User="Administrator"}
    @{Name="LaserMark";         IP="192.168.6.54";  User="Administrator"}
    @{Name="AssemblyATE_Auto";  IP="192.168.6.55";  User="Administrator"}
    @{Name="AutoUltrasonic";    IP="192.168.6.56";  User="wy"}
    @{Name="Aging_Chuanghua";   IP="192.168.6.57";  User="tianjinwuyong"}
    @{Name="HiPot_Auto";        IP="192.168.6.58";  User="Administrator"}
    @{Name="PackagingATE_Left"; IP="192.168.6.59";  User="Administrator"}
    @{Name="PackagingATE_Right";IP="192.168.6.60";  User="Administrator"}
)

$password = "rj"

# =============================================================================
# Step 1: THIS PC
# =============================================================================
Write-Host "  [STEP 1/3] Setting up SSH + Port 22 on THIS PC (192.168.6.56)..." -ForegroundColor Yellow

# Install OpenSSH if needed
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
if ($cap.State -ne "Installed") {
    Write-Host "    Installing OpenSSH Server..." -NoNewline
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" -ErrorAction SilentlyContinue | Out-Null
    Write-Host " DONE" -ForegroundColor Green
}

# Start and enable SSH service
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue

# Create firewall rules for port 22
$fwRule1 = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if ($fwRule1) {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
} else {
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server sshd" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True -ErrorAction SilentlyContinue | Out-Null
}

# Extra explicit rule
$fwRule2 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not $fwRule2) {
    New-NetFirewallRule -Name "Port22-Open" -DisplayName "Port22-Open" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True -ErrorAction SilentlyContinue | Out-Null
}

Write-Host "    ✅ Port 22 open on this PC" -ForegroundColor Green

# =============================================================================
# Step 2: SSH into stations with port 22 already open
# =============================================================================
Write-Host ""
Write-Host "  [STEP 2/3] Opening port 22 on stations via SSH..." -ForegroundColor Yellow

$sshStations = $stations | Where-Object { $_.IP -in @("192.168.6.50","192.168.6.51","192.168.6.90") }

foreach ($s in $sshStations) {
    Write-Host ("    Connecting to {0} ({1})..." -f $s.Name, $s.IP) -NoNewline
    
    # Create a temporary script to copy over
    $tempScript = @'
$ErrorActionPreference = "SilentlyContinue"
$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if ($cap.State -ne "Installed") {
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0"
}
Start-Service sshd
Set-Service sshd -StartupType Automatic
$rule = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
if ($rule) {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP"
} else {
    New-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -DisplayName "OpenSSH Server sshd" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
$r2 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not $r2) {
    New-NetFirewallRule -Name "Port22-Open" -DisplayName "Port22-Open" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True
}
Write-Host "DONE"
'@
    
    # Save temp script
    $tempFile = Join-Path $env:TEMP "enable_ssh_$($s.IP).ps1"
    $tempScript | Out-File -FilePath $tempFile -Encoding ASCII -Force
    
    try {
        # Copy the script to remote via SCP using SSH key or password
        # First try with password pipe (works with some SSH implementations)
        $result = $password | ssh -o BatchMode=no -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$($s.User)@$($s.IP)" "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Windows\Temp\enable_ssh.ps1" 2>&1
        
        # Also try SCP to copy the script first
        $password | scp -o StrictHostKeyChecking=no "$tempFile" "$($s.User)@$($s.IP):C:\Windows\Temp\enable_ssh.ps1" 2>$null
        
        # Run the remote script
        $result = ssh -o BatchMode=no -o StrictHostKeyChecking=no -o ConnectTimeout=5 "$($s.User)@$($s.IP)" "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Windows\Temp\enable_ssh.ps1" 2>&1
        
        Write-Host " DONE" -ForegroundColor Green
    } catch {
        Write-Host " FAILED" -ForegroundColor Red
        Write-Host ("      $_") -ForegroundColor DarkGray
    }
}

# =============================================================================
# Step 3: Try WinRM for remaining stations
# =============================================================================
Write-Host ""
Write-Host "  [STEP 3/3] Trying WinRM for remaining stations..." -ForegroundColor Yellow

$winrmStations = $stations | Where-Object { $_.IP -notin @("192.168.6.50","192.168.6.51","192.168.6.56","192.168.6.90") }

foreach ($s in $winrmStations) {
    Write-Host ("    {0,-25} {1,-15} " -f $s.Name, $s.IP) -NoNewline
    
    try {
        $secPass = ConvertTo-SecureString $password -AsPlainText -Force
        $cred = New-Object System.Management.Automation.PSCredential ("$($s.User)", $secPass)
        
        $session = New-PSSession -ComputerName $s.IP -Credential $cred -ErrorAction Stop -ErrorAction SilentlyContinue
        
        Invoke-Command -Session $session -ScriptBlock {
            $ErrorActionPreference = "SilentlyContinue"
            $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
            if ($cap.State -ne "Installed") { Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" }
            Start-Service sshd
            Set-Service sshd -StartupType Automatic
            Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
            Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue | Out-Null
            if (-not $?) { New-NetFirewallRule -Name "Port22-Open" -DisplayName "Port22-Open" -Direction Inbound -Protocol TCP -LocalPort 22 -Action Allow -Profile Any -Enabled True }
        } -ErrorAction SilentlyContinue | Out-Null
        
        Remove-PSSession $session -ErrorAction SilentlyContinue
        Write-Host "✅ WinRM OK - SSH enabled" -ForegroundColor Green
    } catch {
        Write-Host "❌ WinRM unavailable" -ForegroundColor Red
    }
}

# =============================================================================
# Final verification
# =============================================================================
Write-Host ""
Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║              Final Verification                 ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$openCount = 0
$closedCount = 0

foreach ($s in $stations) {
    Write-Host ("    {0,-25} {1,-15} " -f $s.Name, $s.IP) -NoNewline
    
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $async = $tcp.BeginConnect($s.IP, 22, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(1000)
        if ($wait -and $tcp.Connected) {
            $tcp.EndConnect($async)
            Write-Host "✅ Port 22 OPEN" -ForegroundColor Green
            $openCount++
        } else {
            Write-Host "❌ Closed" -ForegroundColor Red
            $closedCount++
        }
        $tcp.Close()
    } catch {
        Write-Host "❌ Error" -ForegroundColor Red
        $closedCount++
    }
}

Write-Host ""
Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor DarkGray
Write-Host "   Result: $openCount open  |  $closedCount closed" -ForegroundColor Cyan

if ($closedCount -gt 0) {
    Write-Host ""
    Write-Host "  Manual setup needed on closed stations:" -ForegroundColor Yellow
    Write-Host "  On each station, run PowerShell AS ADMIN:" -ForegroundColor Yellow
    Write-Host '    netsh advfirewall firewall add rule name="SSH Port 22" dir=in action=allow protocol=TCP localport=22' -ForegroundColor White
    Write-Host '    Start-Service sshd' -ForegroundColor White
    Write-Host '    Set-Service sshd -StartupType Automatic' -ForegroundColor White
}

Write-Host ""
Write-Host "  Press Enter to exit..." -NoNewline
Read-Host
