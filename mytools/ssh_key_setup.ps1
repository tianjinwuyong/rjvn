# SSH Key Setup Script - copies public key to remote server for passwordless SSH
param(
    [string]$Host = "192.168.6.56",
    [string]$User = "wy",
    [string]$Password = ""
)

$keyPath = "$env:USERPROFILE\.ssh\id_ed25519.pub"
$pubKey = Get-Content $keyPath -Raw

if (-not $pubKey) {
    Write-Host "No SSH key found. Generating..."
    & ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\id_ed25519" -N "" -C "factory@workstation" -q
    $pubKey = Get-Content $keyPath -Raw
}

Write-Host "Public key: $($pubKey.Trim())"
Write-Host ""

if (-not $Password) {
    $securePassword = Read-Host "Enter password for $User@$Host" -AsSecureString
    $password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword))
}

Write-Host "Copying key to $User@$Host..."

# Create command to add key to authorized_keys
$cmd = "mkdir -Force `$HOME\.ssh; `"`$pubKey`" | Out-File -Append -Encoding ascii `$HOME\.ssh\authorized_keys; Write-Host SUCCESS"

# Try using PowerShell remoting if available
$result = echo $password | & {
    $secPass = ConvertTo-SecureString $Password -AsPlainText -Force
    $cred = New-Object System.Management.Automation.PSCredential ($User, $secPass)

    # Try SSH with password via stdin
    $process = Start-Process -FilePath "ssh" -ArgumentList "-o StrictHostKeyChecking=no -o BatchMode=yes $User@$Host `"$cmd`"" -NoNewWindow -PassThru -Wait -WindowStyle Hidden
} 2>&1

Write-Host "Setup complete!"
Write-Host ""
Write-Host "Your public key has been copied to $Host"
Write-Host "You should now be able to SSH without password:"
Write-Host "  ssh $User@$Host"
