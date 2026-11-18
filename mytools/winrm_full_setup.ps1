# ============================================================
# WinRM Full Setup for 瑞晶 Manual Line Stations
# Run once on a source station (e.g. 95) with Admin rights
# Handles ALL prerequisites: service, firewall, auth, TrustedHosts
# ============================================================

param(
    [string[]]$Targets = @(
        "192.168.6.91",
        "192.168.6.92",
        "192.168.6.93",
        "192.168.6.94",
        "192.168.6.95",
        "192.168.6.96",
        "192.168.6.97",
        "192.168.6.98",
        "192.168.6.99",
        "192.168.6.100",
        "192.168.6.1.10"
    ),
    [PSCredential]$Credential = (New-Object System.Management.Automation.PSCredential "Administrator", (ConvertTo-SecureString "rj" -AsPlainText -Force)),
    [switch]$SkipManualCheck   # Use this to skip stations needing manual RDP
)

$ErrorActionPreference = "Continue"
$ProgressCount = 0
$Total = $Targets.Count

# ============================================================
# STEP 0: Detect if we need to self-configure first
# ============================================================
$self = $env:COMPUTERNAME
$selfIP = (Get-NetIPAddress -InterfaceAlias "*Ethernet*" -AddressFamily IPv4 -ErrorAction SilentlyContinue | Select-Object -First 1).IPAddress
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " WinRM Full Setup — 瑞晶 Manual Line" -ForegroundColor Cyan
Write-Host " Source: $self ($selfIP)" -ForegroundColor Cyan
Write-Host " Target count: $Total" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Self: enable unencrypted + TrustedHosts
Write-Host ""
Write-Host "[SELF] Configuring local WinRM client..." -ForegroundColor Yellow
Set-Item WSMan:\localhost\Client\AllowUnencrypted -Value true -Force -ErrorAction SilentlyContinue
$allTargets = $Targets -join ","
Set-Item WSMan:\localhost\Client\TrustedHosts -Value $allTargets -Force -ErrorAction SilentlyContinue
Write-Host "  Local unencrypted + TrustedHosts set" -ForegroundColor Green

# ============================================================
# STEP 1: Quick scan all targets
# ============================================================
Write-Host ""
Write-Host "[STEP 1] Scanning WinRM (5985) on all targets..." -ForegroundColor Yellow

$scanResults = @{}
foreach ($t in $Targets) {
    $ProgressCount++
    Write-Host "  [$ProgressCount/$Total] $t ... " -NoNewline
    try {
        $r = Test-NetConnection $t -Port 5985 -WarningAction SilentlyContinue -ErrorAction Stop
        if ($r.TcpTestSucceeded) {
            $scanResults[$t] = $true
            Write-Host "OPEN" -ForegroundColor Green
        } else {
            $scanResults[$t] = $false
            Write-Host "CLOSED" -ForegroundColor Red
        }
    } catch {
        $scanResults[$t] = $false
        Write-Host "ERROR" -ForegroundColor Red
    }
}

# ============================================================
# STEP 2: For CLOSED targets — try to open via WMI/exec
#         (alternative to RDP, uses port 135445445 DCOM)
# ============================================================
$closedTargets = $scanResults.Keys | Where-Object { -not $scanResults[$_] }

if ($closedTargets.Count -gt 0 -and -not $SkipManualCheck) {
    Write-Host ""
    Write-Host "[STEP 2] Attempting to open 5985 on CLOSED targets via WMI..." -ForegroundColor Yellow

    foreach ($t in $closedTargets) {
        Write-Host "  $t — trying WMI/DCOM..." -NoNewline
        try {
            # Try WMI to open firewall rule remotely
            $wmiOpts = New-CimInstance -Namespace root/Microsoft/Windows/WindowsFirewall -ClassName MSFT_NetFirewallRule -ErrorAction Stop
            $session = New-CimSession -ComputerName $t -Credential $Credential -Authentication Basic -SessionOption (New-CimSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck) -ErrorAction Stop

            # Enable WinRM service via WMI
            Invoke-CimMethod -CimSession $session -Namespace root/Microsoft/Windows/WindowsFirewall -ClassName MSFT_NetFirewallRule -MethodName Create -Arguments @{
                Name = "WinRM-HTTP-In"
                DisplayName = "Windows Remote Management HTTP-In"
                Direction = "Inbound"
                Action = "Allow"
                Protocol = "TCP"
                LocalPort = 5985
                Profile = "Any"
            } -ErrorAction SilentlyContinue | Out-Null

            Remove-CimSession $session
            Write-Host " WMI OK" -ForegroundColor Green
            $scanResults[$t] = $true
        } catch {
            Write-Host (" WMI FAILED: " + $_.Exception.Message.Split("`n")[0]) -ForegroundColor Red
            Write-Host "  -> MANUAL RDP REQUIRED for $t" -ForegroundColor Yellow
        }
    }
}

# ============================================================
# STEP 3: Configure OPEN targets via PSRemoting
# ============================================================
$openTargets = $scanResults.Keys | Where-Object { $scanResults[$_] }
$successTargets = @()
$failTargets = @()

if ($openTargets.Count -gt 0) {
    Write-Host ""
    Write-Host "[STEP 3] Configuring WinRM on OPEN targets via PSRemoting..." -ForegroundColor Yellow

    $sessionOpt = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck

    foreach ($t in $openTargets) {
        $ProgressCount++
        Write-Host "  [$ProgressCount/$Total] $t ... " -NoNewline
        try {
            $session = New-PSSession -ComputerName $t -Credential $Credential -Authentication Basic -SessionOption $sessionOpt -ErrorAction Stop

            Invoke-Command -Session $session -ScriptBlock {
                param($tName)

                $changes = @()

                # 1. Ensure WinRM service running
                if ((Get-Service WinRM).Status -ne "Running") {
                    Start-Service WinRM -ErrorAction SilentlyContinue
                    $changes += "WinRM Started"
                }
                if ((Get-Service WinRM).StartType -ne "Automatic") {
                    Set-Service WinRM -StartupType Automatic -ErrorAction SilentlyContinue
                    $changes += "WinRM Auto"
                }

                # 2. Open firewall
                $fwRule = Get-NetFirewallRule -Name "WinRM-HTTP-In" -ErrorAction SilentlyContinue
                if (-not $fwRule) {
                    Enable-PSRemoting -Force -ErrorAction SilentlyContinue
                    $changes += "FW Enabled"
                } elseif ($fwRule.Action -ne "Allow") {
                    Set-NetFirewallRule -Name "WinRM-HTTP-In" -Enabled True -Action Allow -ErrorAction SilentlyContinue
                    $changes += "FW Updated"
                }

                # 3. Enable Basic auth
                $basicCurrent = (Get-Item WSMan:\localhost\Service\Auth\Basic -ErrorAction SilentlyContinue).Value
                if ($basicCurrent -ne "true") {
                    Set-Item WSMan:\localhost\Service\Auth\Basic -Value true -Force -ErrorAction SilentlyContinue
                    $changes += "BasicAuth"
                }

                # 4. Enable unencrypted
                $encCurrent = (Get-Item WSMan:\localhost\Service\AllowUnencrypted -ErrorAction SilentlyContinue).Value
                if ($encCurrent -ne "true") {
                    Set-Item WSMan:\localhost\Service\AllowUnencrypted -Value true -Force -ErrorAction SilentlyContinue
                    $changes += "Unencrypted"
                }

                if ($changes.Count -eq 0) {
                    Write-Host "Already configured" -ForegroundColor Gray
                } else {
                    Write-Host ("Configured: " + ($changes -join ",")) -ForegroundColor Green
                }
            } -ArgumentList $t -ErrorAction Stop

            Remove-PSSession $session
            $successTargets += $t

        } catch {
            $err = $_.Exception.Message.Split("`n")[0]
            Write-Host ("FAILED: " + $err) -ForegroundColor Red
            $failTargets += $t
        }
    }
}

# ============================================================
# STEP 4: Summary
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Write-Host ""
Write-Host "OPEN & CONFIGURED:" -ForegroundColor Green
foreach ($t in $successTargets) { Write-Host "  [OK] $t" -ForegroundColor Green }

Write-Host ""
Write-Host "OPEN but FAILED (need manual fix):" -ForegroundColor Yellow
foreach ($t in $failTargets) {
    Write-Host "  [FAIL] $t" -ForegroundColor Yellow
    Write-Host "    Run via RDP on $t (Admin PShell):" -ForegroundColor Yellow
    Write-Host "      winrm set winrm/config/service/Auth Basic true" -ForegroundColor Gray
    Write-Host "      winrm set winrm/config/service/AllowUnencrypted true" -ForegroundColor Gray
}

$stillClosed = $scanResults.Keys | Where-Object { -not $scanResults[$_] }
Write-Host ""
Write-Host "STILL CLOSED (need RDP):" -ForegroundColor Red
foreach ($t in $stillClosed) {
    Write-Host "  [CLOSED] $t" -ForegroundColor Red
    Write-Host "    RDP into $t → Admin PowerShell → run:" -ForegroundColor Red
    Write-Host "      winrm quickconfig" -ForegroundColor Gray
    Write-Host "      winrm set winrm/config/service/Auth Basic true" -ForegroundColor Gray
    Write-Host "      winrm set winrm/config/service/AllowUnencrypted true" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " After manual fixes, re-run this script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
