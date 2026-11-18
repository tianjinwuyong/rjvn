# =============================================================================
# SSH Setup Tool — Download + Install OpenSSH (Third-Party Portable)
# =============================================================================
# WHAT:   Downloads the latest OpenSSH Win64 MSI from GitHub and installs it
#         on THIS machine. Works on ANY Windows (Win10/11/Server).
# WHY:    The built-in Add-WindowsCapability approach may fail on some
#         machines (no Windows Update, offline, old builds). This tool uses
#         the portable MSI directly from Microsoft's GitHub releases.
# USAGE:  Run as Administrator. Follow the menu.
# =============================================================================

#Requires -RunAsAdministrator
param(
    [switch]$Silent,
    [switch]$DownloadOnly
)

$ErrorActionPreference = "Continue"

# ── Config ───────────────────────────────────────────────────────────────────
$repoOwner = "PowerShell"
$repoName  = "Win32-OpenSSH"
$arch      = if ([Environment]::Is64BitOperatingSystem) { "Win64" } else { "Win32" }
$msiName   = "OpenSSH-$arch-v{0}.msi"
$tempDir   = Join-Path $env:TEMP "SSH-Setup-Tool"
$configDir = "$env:ProgramData\ssh"
$sshDir    = "$env:SystemDrive\OpenSSH"

# ── Helpers ──────────────────────────────────────────────────────────────────

function Get-IsAdmin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = [Security.Principal.WindowsPrincipal]::new($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║         SSH Setup Tool  v1.0                    ║" -ForegroundColor Cyan
    Write-Host "  ║  Download + Install OpenSSH (Portable MSI)      ║" -ForegroundColor Cyan
    Write-Host "  ╚══════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Msg)
    Write-Host ("  » {0} ... " -f $Msg) -NoNewline
}

function Write-OK {
    Write-Host "Done" -ForegroundColor Green
}

function Write-Fail {
    Write-Host "Failed!" -ForegroundColor Red
}

function Write-Info {
    Write-Host ("  {0}" -f $Args[0]) -ForegroundColor Gray
}

# ── GitHub API: get latest release ───────────────────────────────────────────

function Get-LatestRelease {
    Write-Step "Fetching latest OpenSSH release info from GitHub"
    try {
        $apiUrl = "https://api.github.com/repos/$repoOwner/$repoName/releases/latest"
        $release = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing -ErrorAction Stop
        Write-OK
        return $release
    } catch {
        # Fallback: use releases list
        Write-Host "" -NoNewline
        Write-Info "Fallback: fetching releases list..."
        $apiUrl = "https://api.github.com/repos/$repoOwner/$repoName/releases?per_page=5"
        $releases = Invoke-RestMethod -Uri $apiUrl -UseBasicParsing -ErrorAction Stop
        $release = $releases | Where-Object { -not $_.prerelease } | Select-Object -First 1
        if (-not $release) { $release = $releases[0] }
        Write-OK
        return $release
    }
}

function Find-MsiAsset {
    param([object]$Release)

    $pattern = "^OpenSSH-$arch-v[\d.]+\.msi$"
    $asset = $Release.assets | Where-Object { $_.name -match $pattern } | Select-Object -First 1

    if (-not $asset) {
        # Try broader match
        $asset = $Release.assets | Where-Object { $_.name -match "OpenSSH-$arch" -and $_.name -match "\.msi$" } | Select-Object -First 1
    }

    return $asset
}

function Get-LatestVersionFromRelease {
    param([object]$Release)
    # Try tag_name first
    $tag = $Release.tag_name
    # Remove leading 'v' and preview suffixes
    $version = $tag -replace '^v' -replace 'p\d+-Preview$' -replace 'p\d+$'
    return $version
}

# ── Download ─────────────────────────────────────────────────────────────────

function Download-Msi {
    param([object]$Asset)

    if (-not (Test-Path $tempDir)) {
        New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    }

    $msiPath = Join-Path $tempDir $Asset.name

    if (Test-Path $msiPath) {
        $existingSize = (Get-Item $msiPath).Length
        if ($existingSize -eq $Asset.size) {
            Write-Info "  (Already downloaded: $($Asset.name))"
            return $msiPath
        }
        Remove-Item $msiPath -Force
    }

    Write-Step "Downloading $($Asset.name) ($([math]::Round($Asset.size / 1MB, 1)) MB)"
    try {
        $url = $Asset.browser_download_url
        Write-Info "  URL: $url"
        Invoke-WebRequest -Uri $url -OutFile $msiPath -UseBasicParsing -ErrorAction Stop
        Write-OK
        return $msiPath
    } catch {
        Write-Fail
        Write-Host ("  Error: $_" ) -ForegroundColor Red
        return $null
    }
}

# ── Install ──────────────────────────────────────────────────────────────────

function Install-Msi {
    param([string]$MsiPath)

    Write-Step "Installing OpenSSH (msiexec)"
    try {
        $logFile = Join-Path $tempDir "install.log"
        $args = "/i `"$MsiPath`" /qn /norestart /log `"$logFile`" INSTALLDIR=`"$sshDir`""
        $proc = Start-Process -FilePath "msiexec.exe" -ArgumentList $args -Wait -PassThru -NoNewWindow
        if ($proc.ExitCode -eq 0 -or $proc.ExitCode -eq 1641 -or $proc.ExitCode -eq 3010) {
            Write-OK
            return $true
        } else {
            Write-Fail
            Write-Host ("  msiexec exit code: $($proc.ExitCode)") -ForegroundColor Red
            Write-Host "  Check log: $logFile" -ForegroundColor Yellow
            return $false
        }
    } catch {
        Write-Fail
        Write-Host ("  Error: $_") -ForegroundColor Red
        return $false
    }
}

# ── Configure Service ────────────────────────────────────────────────────────

function Configure-Service {
    Write-Step "Configuring sshd service (automatic start)"

    # Check if sshd.exe exists
    $sshdExe = Join-Path $sshDir "sshd.exe"
    if (-not (Test-Path $sshdExe)) {
        Write-Host "" -NoNewline
        Write-Info "  (sshd.exe not found at $sshdExe, checking PATH...)"
        $sshdExe = (Get-Command sshd -ErrorAction SilentlyContinue).Source
        if (-not $sshdExe) {
            Write-Fail
            Write-Host "  sshd.exe not found after install!" -ForegroundColor Red
            return $false
        }
    }

    # Check if service already exists
    $svc = Get-Service -Name "sshd" -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Host "" -NoNewline
        Write-Info "  (registering sshd service...)"

        # Find install-sshd.ps1
        $installScript = Join-Path (Split-Path $sshdExe -Parent) "install-sshd.ps1"
        if (Test-Path $installScript) {
            # Temporarily set execution policy for this script
            $oldPolicy = Get-ExecutionPolicy
            try {
                & $installScript
            } finally {
                # Restore
            }
        } else {
            # Manually register
            sc.exe create sshd binPath=$sshdExe start=auto depend="Tcpip" | Out-Null
        }
    } else {
        Write-Info "  (service already registered)"
    }

    # Configure start type
    Set-Service -Name sshd -StartupType Automatic -ErrorAction SilentlyContinue

    # Start service
    try {
        Start-Service sshd -ErrorAction Stop
        Write-OK
        return $true
    } catch {
        Write-Host "" -NoNewline
        Write-Info ("  Warning: Could not start sshd ({0})" -f $_.Exception.Message)
        Write-Info "  You may need to restart the computer."
        return $true
    }
}

# ── Firewall ─────────────────────────────────────────────────────────────────

function Configure-Firewall {
    $ruleName = "OpenSSH-Server-In-TCP"
    $rule = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue

    if ($rule) {
        Write-Step "Enabling existing firewall rule ($ruleName)"
        Enable-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
        Write-OK
    } else {
        Write-Step "Creating firewall rule: Port 22 (SSH)"
        New-NetFirewallRule -Name $ruleName `
            -DisplayName "OpenSSH Server (sshd)" `
            -Direction Inbound -Protocol TCP -LocalPort 22 `
            -Action Allow -Profile Any -Enabled True `
            -ErrorAction SilentlyContinue | Out-Null
        Write-OK
    }
}

# ── Quick Test ───────────────────────────────────────────────────────────────

function Test-Connection {
    param([string]$IP = "127.0.0.1")

    Write-Step "Testing SSH on port 22 ($IP)"
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $async = $tcp.BeginConnect($IP, 22, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(2000)
        if ($wait -and $tcp.Connected) {
            $tcp.EndConnect($async)
            Write-OK
            $tcp.Close()
            return $true
        }
        $tcp.Close()
        Write-Fail
        return $false
    } catch {
        Write-Fail
        return $false
    }
}

# ── Show Connection Info ─────────────────────────────────────────────────────

function Show-ConnectionInfo {
    $hostname = $env:COMPUTERNAME
    $username = $env:USERNAME

    Write-Host ""
    Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor DarkGray
    Write-Host "  ✅  SSH Server is READY" -ForegroundColor Green
    Write-Host "  ══════════════════════════════════════════════════" -ForegroundColor DarkGray
    Write-Host ""

    # Get IP addresses
    $ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object {
        $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" -and $_.InterfaceAlias -notlike "*Loopback*" -and $_.PrefixOrigin -ne "WellKnown"
    }

    Write-Host "  Computer Name : $hostname" -ForegroundColor White
    Write-Host "  User          : $username" -ForegroundColor White
    Write-Host "  SSH Port      : 22" -ForegroundColor White
    Write-Host "  SSH Server    : OpenSSH (from MSI)" -ForegroundColor White
    Write-Host ""
    Write-Host "  Connection Commands:" -ForegroundColor Yellow

    foreach ($ip in $ips) {
        Write-Host "    ssh $username@$($ip.IPAddress)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  Password      : (your Windows password)" -ForegroundColor Yellow
    Write-Host "  Or set up key auth for passwordless login." -ForegroundColor Gray

    # Check if sshd_config has password auth enabled
    $configFile = Join-Path $configDir "sshd_config"
    if (Test-Path $configFile) {
        $pwAuth = Select-String -Path $configFile -Pattern "^PasswordAuthentication" -SimpleMatch
        if ($pwAuth) {
            $val = $pwAuth.Line -replace '.*\s+(\w+)$', '$1'
            if ($val -eq "no") {
                Write-Host ""
                Write-Host "  ⚠  PasswordAuthentication is set to 'no' in $configFile" -ForegroundColor Yellow
                Write-Host "     Users must use SSH key authentication." -ForegroundColor Yellow
            }
        } else {
            Write-Host ""
            Write-Host "  ℹ  PasswordAuthentication not explicitly set (default: yes)" -ForegroundColor Gray
        }
    }
}

# ── SSH Key Generation ───────────────────────────────────────────────────────

function Setup-SSHKey {
    $keyDir = "$env:USERPROFILE\.ssh"
    $keyFile = Join-Path $keyDir "id_ed25519"
    $pubFile = "$keyFile.pub"

    if (Test-Path $pubFile) {
        Write-Info "  (SSH key already exists: $pubFile)"
        return
    }

    if (-not (Test-Path $keyDir)) {
        New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
    }

    Write-Step "Generating Ed25519 SSH key (no passphrase)"
    try {
        & ssh-keygen -t ed25519 -f $keyFile -N "" -C "$env:USERNAME@$env:COMPUTERNAME" -q
        Write-OK
    } catch {
        Write-Fail
        Write-Info "  Make sure ssh-keygen is available (install SSH client)."
    }
}

function Show-PublicKey {
    $pubFile = "$env:USERPROFILE\.ssh\id_ed25519.pub"
    if (Test-Path $pubFile) {
        $pubKey = Get-Content $pubFile -Raw
        Write-Host ""
        Write-Host "  Your PUBLIC KEY (copy this to remote servers):" -ForegroundColor Cyan
        Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host $pubKey.Trim() -ForegroundColor White
        Write-Host "  ─────────────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host ""

        # Try to add to authorized_keys for localhost
        $authFile = "$env:USERPROFILE\.ssh\authorized_keys"
        if (-not (Test-Path $authFile) -or -not (Get-Content $authFile -Raw).Contains($pubKey.Trim())) {
            Add-Content -Path $authFile -Value $pubKey.Trim() -ErrorAction SilentlyContinue
            Write-Info "  (also added to your own authorized_keys for localhost access)"
        }
    }
}

# ── Interactive Menu ─────────────────────────────────────────────────────────

function Show-Menu {
    Write-Banner

    # Check current status
    $svc = Get-Service -Name "sshd" -ErrorAction SilentlyContinue
    $sshdExe = Get-Command sshd -ErrorAction SilentlyContinue

    Write-Host "  Current Status:" -ForegroundColor Yellow
    if ($svc) {
        $color = if ($svc.Status -eq 'Running') { 'Green' } else { 'Red' }
        Write-Host "    SSH Service : " -NoNewline
        Write-Host $svc.Status -ForegroundColor $color
    } else {
        Write-Host "    SSH Service : Not installed" -ForegroundColor Red
    }
    if ($sshdExe) {
        Write-Host "    SSH Binary  : $($sshdExe.Source)" -ForegroundColor Gray
    }

    # Test port 22
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $async = $tcp.BeginConnect("127.0.0.1", 22, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne(500)
        if ($wait -and $tcp.Connected) {
            $tcp.EndConnect($async)
            Write-Host "    Port 22     : " -NoNewline
            Write-Host "OPEN (listening)" -ForegroundColor Green
        }
        $tcp.Close()
    } catch {}

    Write-Host ""
    Write-Host "  Options:" -ForegroundColor Yellow
    Write-Host "    [1]  Download + Install OpenSSH (from GitHub MSI)" -ForegroundColor White
    Write-Host "    [2]  Configure SSH service + Firewall only" -ForegroundColor White
    Write-Host "    [3]  Generate SSH key (Ed25519)" -ForegroundColor White
    Write-Host "    [4]  Show connection info" -ForegroundColor White
    Write-Host "    [5]  Test SSH connection (localhost)" -ForegroundColor White
    Write-Host "    [6]  Open config folder" -ForegroundColor White
    Write-Host "    [7]  View sshd_config" -ForegroundColor White
    Write-Host ""
    Write-Host "    [0]  Exit" -ForegroundColor Gray
    Write-Host ""
}

# ── Main ─────────────────────────────────────────────────────────────────────

function Main {
    if (-not (Get-IsAdmin)) {
        Write-Host "  ERROR: This tool must be run as Administrator!" -ForegroundColor Red
        Write-Host "  Right-click → 'Run as Administrator'" -ForegroundColor Yellow
        exit 1
    }

    # Check supported arch
    if (-not [Environment]::Is64BitOperatingSystem -and $arch -eq "Win64") {
        Write-Info "  Note: 32-bit OS detected, will download 32-bit MSI."
    }

    if ($Silent) {
        # Silent mode: download + install + configure
        Write-Banner
        $release = Get-LatestRelease
        if (-not $release) { exit 1 }
        $asset = Find-MsiAsset -Release $release
        if (-not $asset) { Write-Host "No MSI asset found!" -ForegroundColor Red; exit 1 }
        $msiPath = Download-Msi -Asset $asset
        if (-not $msiPath) { exit 1 }
        if ($DownloadOnly) {
            Write-Host "  Downloaded to: $msiPath" -ForegroundColor Green
            return
        }
        if (Install-Msi -MsiPath $msiPath) {
            Configure-Service
            Configure-Firewall
            Test-Connection
            Show-ConnectionInfo
        }
        return
    }

    # Interactive menu loop
    do {
        Show-Menu
        $choice = Read-Host "  Select option"

        switch ($choice) {
            "1" {
                Write-Host ""
                Write-Host "  ── Download + Install OpenSSH ──" -ForegroundColor Cyan
                Write-Host ""

                # Step 1: Get release info
                $release = Get-LatestRelease
                if (-not $release) {
                    Write-Host "  Could not fetch release info. Check your internet connection." -ForegroundColor Red
                    goto PressEnter
                }

                $version = Get-LatestVersionFromRelease -Release $release
                Write-Info "Latest version: $version"

                # Step 2: Find MSI asset
                $asset = Find-MsiAsset -Release $release
                if (-not $asset) {
                    Write-Host "  No MSI asset found for $arch!" -ForegroundColor Red
                    Write-Host "  Available assets:" -ForegroundColor Yellow
                    $release.assets | Where-Object { $_.name -match "OpenSSH" } | ForEach-Object {
                        Write-Host "    $($_.name)" -ForegroundColor Gray
                    }
                    goto PressEnter
                }

                # Step 3: Download
                $msiPath = Download-Msi -Asset $asset
                if (-not $msiPath) { goto PressEnter }

                # Step 4: Install
                Write-Host ""
                if (Install-Msi -MsiPath $msiPath) {
                    # Step 5: Configure
                    Write-Host ""
                    Configure-Service
                    Configure-Firewall
                    Write-Host ""
                    Test-Connection
                    Show-ConnectionInfo
                }

                # PressEnter
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
            "2" {
                Write-Host ""
                Write-Host "  ── Configure SSH Service + Firewall ──" -ForegroundColor Cyan
                Write-Host ""
                Configure-Service
                Configure-Firewall
                Test-Connection
                Show-ConnectionInfo
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
            "3" {
                Write-Host ""
                Write-Host "  ── SSH Key Generation ──" -ForegroundColor Cyan
                Write-Host ""
                Setup-SSHKey
                Show-PublicKey
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
            "4" {
                Write-Host ""
                Write-Host "  ── Connection Info ──" -ForegroundColor Cyan
                Show-ConnectionInfo
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
            "5" {
                Write-Host ""
                Write-Host "  ── Testing SSH ──" -ForegroundColor Cyan
                Write-Host ""
                Test-Connection -IP "127.0.0.1"
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
            "6" {
                $confDir = "$env:ProgramData\ssh"
                if (Test-Path $confDir) {
                    Write-Info "Opening: $confDir"
                    Invoke-Item $confDir
                } else {
                    Write-Info "Config directory not found: $confDir"
                    Write-Info "Install SSH Server first (option 1)."
                }
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
            "7" {
                $configFile = Join-Path $configDir "sshd_config"
                if (Test-Path $configFile) {
                    Write-Host ""
                    Write-Host "  ── sshd_config ──" -ForegroundColor Cyan
                    Write-Host ""
                    Get-Content $configFile | ForEach-Object {
                        if ($_ -match "^\s*(#|$)") {
                            Write-Host ("  {0}" -f $_) -ForegroundColor DarkGray
                        } else {
                            Write-Host ("  {0}" -f $_) -ForegroundColor White
                        }
                    }
                } else {
                    Write-Host "  sshd_config not found at $configFile" -ForegroundColor Yellow
                }
                Write-Host ""
                Write-Host "  Press Enter to continue..." -NoNewline
                Read-Host
            }
        }
    } while ($choice -ne "0")

    Write-Host ""
    Write-Host "  Bye!" -ForegroundColor Cyan
}

# ── Entry Point ──────────────────────────────────────────────────────────────
Main
