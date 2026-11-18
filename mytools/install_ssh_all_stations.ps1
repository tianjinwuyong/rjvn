# install_ssh_all_stations.ps1
# Master script - run from ANY ONE station with WinRM access
# Pushes SSH (port 22) + firewall (port 445) to ALL Windows stations
# No parameters needed - just run

param(
    [string]$CredUser = "Administrator",
    [string]$CredPass = "rj"
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " SSH Installer - All 手动线 Windows Stations" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# All Windows stations (AOI 192.168.6.90 is Linux - skip)
$stations = @(
    @{Name="ICT";         IP="192.168.6.91"},
    @{Name="FCT";         IP="192.168.6.92"},
    @{Name="分板机";        IP="192.168.6.93"},
    @{Name="绑码";         IP="192.168.6.94"},
    @{Name="组装ATE";      IP="192.168.6.95"},
    @{Name="超声波";        IP="192.168.6.96"},
    @{Name="安托森老化";    IP="192.168.6.97"},
    @{Name="高压测试仪";    IP="192.168.6.98"},
    @{Name="包装ATE";      IP="192.168.6.99"},
    @{Name="包装";         IP="192.168.6.100"},
    @{Name="波峰焊";       IP="192.168.1.10"}
)

# Create credential
$secPass = ConvertTo-SecureString $CredPass -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential "$env:USERDOMAIN\$CredUser", $secPass

# PowerShell script to run on each remote station
$remoteScript = @"
`$ErrorActionPreference = "SilentlyContinue"
Write-Host "Installing OpenSSH..."

# Install OpenSSH
`$cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*"
if (`$cap.State -ne "Installed") {
    Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" | Out-Null
}

# Start and enable sshd
Start-Service sshd -ErrorAction SilentlyContinue
Set-Service sshd -StartupType Automatic

# Firewall rules
`$r22 = Get-NetFirewallRule -Name "Port22-Open" -ErrorAction SilentlyContinue
if (-not `$r22) {
    New-NetFirewallRule -Name "Port22-Open" -DisplayName "SSH Port 22" `
        -Direction Inbound -Protocol TCP -LocalPort 22 `
        -Action Allow -Profile Any -Enabled True | Out-Null
}
`$r445 = Get-NetFirewallRule -Name "Port445-Open" -ErrorAction SilentlyContinue
if (-not `$r445) {
    New-NetFirewallRule -Name "Port445-Open" -DisplayName "SMB Port 445" `
        -Direction Inbound -Protocol TCP -LocalPort 445 `
        -Action Allow -Profile Any -Enabled True | Out-Null
}
`$rSSH = Get-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
if (`$rSSH -and `$rSSH.Action -ne "Allow") {
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" | Out-Null
}

# Verify
`$port22 = `$null
`$port445 = `$null
try {
    `$c = [System.Net.Sockets.TcpClient]::new()
    `$c.Connect("127.0.0.1", 22)
    `$port22 = `$true
    `$c.Close()
} catch {}
try {
    `$c2 = [System.Net.Sockets.TcpClient]::new()
    `$c2.Connect("127.0.0.1", 445)
    `$port445 = `$true
    `$c2.Close()
} catch {}

Write-Host "PORT22=`$(`$port22) PORT445=`$(`$port445)"
"@

$total = $stations.Count
$current = 0
$ok = 0
$fail = 0

foreach ($s in $stations) {
    $ip = $s.IP
    $name = $s.Name
    $current++
    Write-Host "[$current/$total] $($name.PadRight(10)) $ip ... " -NoNewline

    # Check if already done
    $testPort22 = $false
    try {
        $c = [System.Net.Sockets.TcpClient]::new()
        $c.Connect($ip, 22)
        $testPort22 = $true
        $c.Close()
    } catch {}

    if ($testPort22) {
        Write-Host "SKIP (port 22 already open)" -ForegroundColor Gray
        continue
    }

    # Try WinRM connection
    try {
        $session = New-PSSession -ComputerName $ip -Credential $cred `
            -Authentication Default -ErrorAction Stop

        $result = Invoke-Command -Session $session -ScriptBlock ([scriptblock]::Create($remoteScript)) `
            -ErrorAction Stop

        if ($result -match "PORT22=True") {
            Write-Host "OK" -ForegroundColor Green
            $ok++
        } else {
            Write-Host "PARTIAL (check manually)" -ForegroundColor Yellow
        }

        Remove-PSSession $session

    } catch {
        Write-Host "FAIL - $_" -ForegroundColor Red
        $fail++
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Done: $ok OK, $fail FAILED" -ForegroundColor $(if($fail -eq 0){'Green'}else{'Yellow'})
Write-Host ""
Write-Host "All stations with port 22 open:" -ForegroundColor Cyan
foreach ($s in $stations) {
    $open = $false
    try {
        $c = [System.Net.Sockets.TcpClient]::new()
        $c.Connect($s.IP, 22)
        $open = $true
        $c.Close()
    } catch {}
    $sym = if ($open) { "SSH OK" } else { "---" }
    Write-Host ("  {0,-10} {1,-16} {2}" -f $s.Name, $s.IP, $sym) -ForegroundColor $(if($open){'Green'}else{'DarkGray'})
}

Read-Host "Press Enter to exit"
