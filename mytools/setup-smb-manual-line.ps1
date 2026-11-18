# ============================================================
# setup-smb-manual-line.ps1
# Ruijing Vietnam Factory - Manual Line Station SMB Setup
# Usage: .\setup-smb-manual-line.ps1 -StationNumber 92
# ============================================================
param(
    [Parameter(Mandatory=$true)]
    [ValidateRange(91,100)]
    [int]$StationNumber = 92,

    [Parameter(Mandatory=$false)]
    [string]$ShareName = "ManualLine",

    [Parameter(Mandatory=$false)]
    [string]$SMBUser = "Administrator",

    [Parameter(Mandatory=$false)]
    [string]$SMBPass = "rj"
)

$ErrorActionPreference = "Stop"
$IP = "192.168.6.$StationNumber"

$StationNames = @{
    91  = "ICT"
    92  = "FCT"
    93  = "PanelSaw"
    94  = "Labeling"
    95  = "AssyATE"
    96  = "Ultrasonic"
    97  = "WaveSolder"
    98  = "Aging"
    99  = "HiPotATE"
    100 = "PackATE"
}
$StationName = $StationNames[$StationNumber]

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  SMB Setup - Station .$StationNumber ($StationName)" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# -------------------------------------------------------
# Step 1: Enable SMB features (server Windows only)
# -------------------------------------------------------
Write-Host "[1/6] Enabling SMB features..." -ForegroundColor Yellow

try {
    $features = @(
        "SMB1.0/CIFS File Sharing Support",
        "SMB1.0/CIFS Client",
        "SMB1.0/CIFS Server"
    )
    foreach ($feat in $features) {
        $state = (Get-WindowsOptionalFeature -Online -FeatureName $feat -ErrorAction Stop).State
        if ($state -ne "Enabled") {
            Write-Host "    Enabling: $feat"
            Enable-WindowsOptionalFeature -Online -FeatureName $feat -NoRestart -ErrorAction Stop | Out-Null
        } else {
            Write-Host "    Already enabled: $feat"
        }
    }
} catch {
    Write-Host "    DISM skipped (not server Windows or no admin) - OK" -ForegroundColor DarkGray
}

# -------------------------------------------------------
# Step 2: Verify SMB user exists
# -------------------------------------------------------
Write-Host ""
Write-Host "[2/6] Verifying SMB user..." -ForegroundColor Yellow

$user = $null
try {
    $user = Get-LocalUser -Name $SMBUser -ErrorAction Stop
} catch {
    Write-Host "    $SMBUser not found, trying Admin..." -ForegroundColor Magenta
    try {
        $user = Get-LocalUser -Name "Admin" -ErrorAction Stop
        if ($user) { $SMBUser = "Admin" }
    } catch {
        Write-Host "    Admin not found either" -ForegroundColor Magenta
    }
}

if ($user) {
    Write-Host "    User $SMBUser exists"
    Write-Host "    IMPORTANT: Set password to '$SMBPass' via Control Panel -> User Accounts" -ForegroundColor Green
} else {
    Write-Host "    WARNING: Cannot verify user. Make sure $SMBUser exists and password is '$SMBPass'" -ForegroundColor Yellow
}

# -------------------------------------------------------
# Step 3: Create folder structure
# -------------------------------------------------------
Write-Host ""
Write-Host "[3/6] Creating folder structure..." -ForegroundColor Yellow

# Use ASCII-safe paths to avoid encoding issues
$BasePath    = "D:\ManualLine"
$StationPath = "D:\ManualLine\Station$StationNumber"
$DistPath    = "$StationPath\dist"

if (-not (Test-Path "D:\")) {
    Write-Host "    [ERROR] D: drive not found!" -ForegroundColor Red
    exit 1
}

foreach ($dir in @($BasePath, $StationPath, $DistPath)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "    Created: $dir"
    } else {
        Write-Host "    Exists:   $dir"
    }
}

# -------------------------------------------------------
# Step 4: Set NTFS permissions
# -------------------------------------------------------
Write-Host ""
Write-Host "[4/6] Setting NTFS permissions..." -ForegroundColor Yellow

$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
Write-Host "    Current user: $currentUser"

# Reset to allow inheritance
$acl = Get-Acl $StationPath
$acl.SetAccessRuleProtection($false, $true)
$acl | Set-Acl $StationPath

# Build access rules using proper enum values
$rights  = [System.Security.AccessControl.FileSystemRights]::FullControl
$inherit = [System.Security.AccessControl.InheritanceFlags]::ContainerInherit -bor `
           [System.Security.AccessControl.InheritanceFlags]::ObjectInherit
$prop    = [System.Security.AccessControl.PropagationFlags]::InheritOnly
$type    = [System.Security.AccessControl.AccessControlType]::Allow

$rule1 = New-Object System.Security.AccessControl.FileSystemAccessRule(
    "Everyone", $rights, $inherit, $prop, $type
)
$rule2 = New-Object System.Security.AccessControl.FileSystemAccessRule(
    $SMBUser, $rights, $inherit, $prop, $type
)

$acl = Get-Acl $StationPath
$acl.AddAccessRule($rule1)
$acl.AddAccessRule($rule2)
$acl | Set-Acl $StationPath
Write-Host "    NTFS permissions set"

# -------------------------------------------------------
# Step 5: Create SMB share
# -------------------------------------------------------
Write-Host ""
Write-Host "[5/6] Creating SMB share..." -ForegroundColor Yellow

$existing = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
if ($existing) {
    Remove-SmbShare -Name $ShareName -Force
    Write-Host "    Removed old share: $ShareName"
}

try {
    New-SmbShare -Name $ShareName `
        -Path $DistPath `
        -Description "Ruijing Manual Line Station $StationNumber Share" `
        -FullAccess "Everyone", $SMBUser `
        -ChangeAccess "Everyone" `
        -Force | Out-Null
    Write-Host "    Share created: \\$IP\$ShareName" -ForegroundColor Green
    Write-Host "    Share path: $DistPath" -ForegroundColor Green
} catch {
    Write-Host "    [WARN] Could not create share (need Admin rights)" -ForegroundColor Yellow
    Write-Host "    Manually share folder via: right-click folder -> Properties -> Sharing -> Share" -ForegroundColor Yellow
    Write-Host "    Or run PowerShell as Administrator and run this script again" -ForegroundColor Yellow
}

# -------------------------------------------------------
# Step 6: Firewall rules
# -------------------------------------------------------
Write-Host ""
Write-Host "[6/6] Configuring firewall..." -ForegroundColor Yellow

function Ensure-FirewallRule {
    param($Display, $Port)
    try {
        $rule = Get-NetFirewallRule -DisplayName $Display -ErrorAction Stop
        if ($rule.Action -ne "Allow") {
            Set-NetFirewallRule -DisplayName $Display -Action Allow -ErrorAction Stop
            Write-Host "    Rule enabled: $Display"
        } else {
            Write-Host "    Rule exists: $Display"
        }
    } catch {
        Write-Host "    [WARN] Could not set firewall rule (need Admin)" -ForegroundColor Yellow
        Write-Host "    Manually open port $Port via: Control Panel -> Windows Defender Firewall -> Advanced" -ForegroundColor Yellow
    }
}

Ensure-FirewallRule -Display "SMB-In-445" -Port 445
Ensure-FirewallRule -Display "SMB-In-139" -Port 139

# -------------------------------------------------------
# Done
# -------------------------------------------------------
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Done! SMB share configured." -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Station:  .$StationNumber ($StationName)" -ForegroundColor Cyan
Write-Host "  Share:    \\$IP\$ShareName" -ForegroundColor Cyan
Write-Host "  Path:     $DistPath" -ForegroundColor Cyan
Write-Host "  User:     $SMBUser" -ForegroundColor Cyan
Write-Host "  Pass:     $SMBPass" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next: Copy ate_center.db into the share, then update" -ForegroundColor White
Write-Host "  lineSupervisor.py with the correct share path." -ForegroundColor White
Write-Host ""
