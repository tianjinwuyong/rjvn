# install_ssh_smb_silent.ps1
# Silent version - no prompts, suitable for PSEXEC / remote deployment
# Usage: install_ssh_smb_silent.ps1
# Exit codes: 0=success, 1=partial, 2=failed

param(
    [string]$Output = "json"  # "json" or "text"
)

$ErrorActionPreference = "SilentlyContinue"
$result = @{
    hostname = $env:COMPUTERNAME
    ip = $null
    port22 = $false
    port445 = $false
    sshd_running = $false
    errors = @()
}

try {
    $result.ip = (Get-NetIPAddress -AddressFamily IPv4 -PrefixOrigin Manual | Where-Object { $_.IPAddress -notlike "127.*" } | Select-Object -First 1).IPAddress
} catch { }

# Install OpenSSH
try {
    $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
    if ($cap.State -ne "Installed") {
        Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" | Out-Null
    }
} catch {
    $result.errors += "OpenSSH install failed: $_"
}

# Start sshd
try {
    $svc = Get-Service -Name sshd -ErrorAction SilentlyContinue
    if ($svc) {
        Start-Service sshd -ErrorAction SilentlyContinue
        Set-Service sshd -StartupType Automatic
        $result.sshd_running = $svc.Status -eq "Running"
    }
} catch {
    $result.errors += "sshd start failed: $_"
}

# Firewall rule port 22
try {
    $r22 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
    if (-not $r22) {
        New-NetFirewallRule -Name "Port22-Open" `
            -DisplayName "SSH (Port 22)" `
            -Direction Inbound -Protocol TCP -LocalPort 22 `
            -Action Allow -Profile Any -Enabled True | Out-Null
    } else {
        Enable-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
    }
    $r22b = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
    if ($r22b -and $r22b.Action -ne "Allow") {
        Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" | Out-Null
    }
} catch {
    $result.errors += "Port 22 firewall failed: $_"
}

# Firewall rule port 445
try {
    $r445 = Get-NetFirewallRule -Name "Port445-Open" -ErrorAction SilentlyContinue
    if (-not $r445) {
        New-NetFirewallRule -Name "Port445-Open" `
            -DisplayName "SMB (Port 445)" `
            -Direction Inbound -Protocol TCP -LocalPort 445 `
            -Action Allow -Profile Any -Enabled True | Out-Null
    } else {
        Enable-NetFirewallRule -Name "Port445-Open" -ErrorAction SilentlyContinue
    }
} catch {
    $result.errors += "Port 445 firewall failed: $_"
}

# Verify port 22
try {
    $c = [System.Net.Sockets.TcpClient]::new()
    $c.Connect("127.0.0.1", 22)
    $result.port22 = $true
    $c.Close()
} catch { }

# Verify port 445
try {
    $c2 = [System.Net.Sockets.TcpClient]::new()
    $c2.Connect("127.0.0.1", 445)
    $result.port445 = $true
    $c2.Close()
} catch { }

# Output
if ($Output -eq "json") {
    $result | ConvertTo-Json -Compress
} else {
    $status = if ($result.port22 -and $result.sshd_running) { "SUCCESS" } elseif ($result.errors.Count -gt 0) { "FAILED" } else { "PARTIAL" }
    Write-Host "HOST=$($result.hostname) IP=$($result.ip) PORT22=$($result.port22) PORT445=$($result.port445) SSHD=$($result.sshd_running) STATUS=$status"
    foreach ($e in $result.errors) { Write-Host "ERROR: $e" }
}

# Exit code
if ($result.port22 -and $result.sshd_running) { exit 0 }
elseif ($result.errors.Count -gt 0) { exit 2 }
else { exit 1 }
