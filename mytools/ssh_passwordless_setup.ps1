# =============================================================================
# SSH Passwordless Setup Script
# =============================================================================

param(
    [string]$Host = "192.168.6.56",
    [string]$User = "wy"
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "=== SSH Passwordless Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if SSH key exists
$keyPath = "$env:USERPROFILE\.ssh\id_ed25519.pub"
if (-not (Test-Path $keyPath)) {
    Write-Host "Generating SSH key..." -ForegroundColor Yellow
    & ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -N "" -C "factory@workstation" -q
}

$pubKey = Get-Content $keyPath -Raw
Write-Host "Public key ready: $($pubKey.Trim())"
Write-Host ""

# Method 1: Try sshpass if available
$hasSshpass = $null -ne (Get-Command sshpass -ErrorAction SilentlyContinue)

if ($hasSshpass) {
    Write-Host "sshpass found. Setting up passwordless SSH..." -ForegroundColor Green
    Write-Host "Enter password when prompted:"
    sshpass -p "$(Read-Host 'Password' -AsSecureString)" ssh-copy-id -o StrictHostKeyChecking=no "$User@$Host"
} else {
    Write-Host "sshpass not found." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "=== Manual Setup Required ===" -ForegroundColor Red
    Write-Host ""
    Write-Host "Option 1: Copy this public key to remote server:" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  COPY THIS LINE:" -ForegroundColor Green
    Write-Host "  $($pubKey.Trim())" -ForegroundColor White
    Write-Host ""
    Write-Host "  Then on $User@$Host, run:" -ForegroundColor Yellow
    Write-Host '  echo "PUBKEY" >> ~/.ssh/authorized_keys' -ForegroundColor White
    Write-Host ""
    Write-Host "Option 2: Use this Python script after installing sshpass" -ForegroundColor Cyan
    Write-Host "  pip install sshpass" -ForegroundColor White
    Write-Host "  sshpass -p YOUR_PASSWORD ssh-copy-id $User@$Host" -ForegroundColor White
}

Write-Host ""
Write-Host "After setup, test with:" -ForegroundColor Cyan
Write-Host "  ssh $User@$Host" -ForegroundColor Green
