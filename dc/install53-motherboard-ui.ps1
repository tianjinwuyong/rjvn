$ErrorActionPreference = "Stop"
$stationDir = "D:\stations"
New-Item -ItemType Directory -Path $stationDir -Force | Out-Null
$destination = Join-Path $stationDir "Auto_Depanel_Agent.exe"
$candidate = Join-Path $stationDir "Auto_Depanel_Agent.new.exe"

Invoke-WebRequest `
  "http://192.168.6.155:8099/Auto_Depanel_Agent.exe" `
  -OutFile $candidate `
  -UseBasicParsing

Get-Process Auto_Depanel_Agent -ErrorAction SilentlyContinue |
  Stop-Process -Force
Start-Sleep -Seconds 3

if (Test-Path $destination) {
  $backup = "$destination.$(Get-Date -Format 'yyyyMMddHHmmss').bak"
  Copy-Item $destination $backup -Force
}
Move-Item $candidate $destination -Force

$hash = (Get-FileHash $destination -Algorithm SHA256).Hash
$process = Start-Process $destination -PassThru
@"
HASH=$hash
PID=$($process.Id)
TIME=$(Get-Date -Format o)
"@ | Set-Content (Join-Path $stationDir "install53-motherboard-ui.txt")

Write-Host "INSTALL53_OK" $hash $process.Id
