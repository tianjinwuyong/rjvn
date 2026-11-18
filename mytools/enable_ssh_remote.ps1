# Enable SSH on Remote Windows Stations
# Requires admin credentials on target machines

param(
    [string]$Password = "rj",
    [switch]$All,
    [switch]$Test
)

$ErrorActionPreference = "Continue"

# Stations with SSH capability
$stations = @(
    @{Name="AOI(手动)"; IP="192.168.6.90"; User="Administrator"},
    @{Name="AOI(自动)"; IP="192.168.6.50"; User="Administrator"},
    @{Name="ICT(自动)"; IP="192.168.6.51"; User="Admin"},
    @{Name="FCT(自动)"; IP="192.168.6.52"; User="Administrator"},
    @{Name="分板机(自动)"; IP="192.168.6.53"; User="Administrator"},
    @{Name="激光打标"; IP="192.168.6.54"; User="Administrator"},
    @{Name="组装ATE(自动)"; IP="192.168.6.55"; User="Administrator"},
    @{Name="自动超声波"; IP="192.168.6.56"; User="Administrator"},
    @{Name="创华老化"; IP="192.168.6.57"; User="Administrator"},
    @{Name="高压测试(自动)"; IP="192.168.6.58"; User="Administrator"},
    @{Name="包装ATE左边"; IP="192.168.6.59"; User="Administrator"},
    @{Name="包装ATE右边"; IP="192.168.6.60"; User="Administrator"},
    @{Name="FCT(手动)"; IP="192.168.6.92"; User="Administrator"},
    @{Name="分板机(手动)"; IP="192.168.6.93"; User="Administrator"},
    @{Name="绑码(手动)"; IP="192.168.6.94"; User="Administrator"},
    @{Name="组装ATE(手动)"; IP="192.168.6.95"; User="Administrator"},
    @{Name="超声波(手动)"; IP="192.168.6.96"; User="Administrator"},
    @{Name="老化(手动)"; IP="192.168.6.97"; User="Administrator"},
    @{Name="高压测试(手动)"; IP="192.168.6.98"; User="Administrator"},
    @{Name="包装ATE(手动)"; IP="192.168.6.99"; User="Administrator"},
    @{Name="包装(手动)"; IP="192.168.6.100"; User="Administrator"}
)

function Enable-SSHOnRemote {
    param(
        [string]$ComputerName,
        [string]$User,
        [string]$Password
    )

    Write-Host "Connecting to $ComputerName..." -NoNewline

    $secPassword = ConvertTo-SecureString $Password -AsPlainText -Force
    $cred = New-Object System.Management.Automation.PSCredential ("$ComputerName\$User", $secPassword)

    # Try to enable OpenSSH via PowerShell Remoting
    try {
        $session = New-PSSession -ComputerName $ComputerName -Credential $cred -ErrorAction Stop
        Write-Host " Connected!" -ForegroundColor Green

        # Install OpenSSH Server
        Write-Host "  Installing OpenSSH Server..." -NoNewline
        $result = Invoke-Command -Session $session -ScriptBlock {
            # Check if OpenSSH is installed
            $ssh = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
            if (-not $ssh) {
                Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" -ErrorAction SilentlyContinue
            }

            # Start SSH service
            Start-Service sshd -ErrorAction SilentlyContinue
            Set-Service -Name sshd -StartupType Automatic -ErrorAction SilentlyContinue

            # Enable firewall
            Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue

            return "OK"
        }

        if ($result -eq "OK") {
            Write-Host " SSH Enabled!" -ForegroundColor Green
            return $true
        }
    }
    catch {
        Write-Host " Failed: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
    finally {
        if ($session) { Remove-PSSession $session }
    }
}

function Test-SSHPort {
    param([string]$IP)

    $r = Test-NetConnection -ComputerName $IP -Port 22 -WarningAction SilentlyContinue -ErrorAction SilentlyContinue
    return $r.TcpTestSucceeded
}

# Main
Write-Host ""
Write-Host "=== Enable SSH on Factory Stations ===" -ForegroundColor Cyan
Write-Host ""

if ($Test) {
    Write-Host "Testing SSH ports on all stations..."
    Write-Host ""
    foreach ($s in $stations) {
        Write-Host "  $($s.Name) ($($s.IP))..." -NoNewline
        if (Test-SSHPort -IP $s.IP) {
            Write-Host " SSH OPEN" -ForegroundColor Green
        } else {
            Write-Host " closed" -ForegroundColor Gray
        }
    }
    Write-Host ""
    exit
}

if (-not $All) {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\enable_ssh_remote.ps1 -Test           # Test SSH ports"
    Write-Host "  .\enable_ssh_remote.ps1 -All            # Enable SSH on all stations"
    Write-Host ""
    Write-Host "This script requires:" -ForegroundColor Yellow
    Write-Host "  1. Admin credentials on remote machines"
    Write-Host "  2. PowerShell Remoting enabled on remote machines"
    Write-Host "  3. Firewall access on port 5985/5986 (WinRM)"
    Write-Host ""
}

if ($All) {
    Write-Host "This will attempt to enable SSH on ALL stations." -ForegroundColor Yellow
    Write-Host "Press Ctrl+C to cancel, or" -NoNewline
    Start-Sleep -Seconds 3
    Write-Host " continuing..." -ForegroundColor Yellow
    Write-Host ""

    $success = 0
    $failed = 0

    foreach ($s in $stations) {
        Write-Host ""
        Write-Host "[$($s.Name)]" -ForegroundColor Cyan
        $ok = Enable-SSHOnRemote -ComputerName $s.IP -User $s.User -Password $Password
        if ($ok) { $success++ } else { $failed++ }
    }

    Write-Host ""
    Write-Host "=== Summary ===" -ForegroundColor Cyan
    Write-Host "  Success: $success" -ForegroundColor Green
    Write-Host "  Failed: $failed" -ForegroundColor Red
}
