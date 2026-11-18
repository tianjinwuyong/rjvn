$ErrorActionPreference = 'Stop'
$hostIp = '192.168.6.56'
$credential = Get-Credential -UserName 'PC' -Message 'Station 56 PC credential; not saved'
if (!$credential) {throw 'Credential entry cancelled'}
$command = 'powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Enable-PSRemoting -Force -SkipNetworkProfileCheck; Set-Service WinRM -StartupType Automatic; Start-Service WinRM; New-NetFirewallRule -DisplayName Ruijing-WinRM-LocalSubnet -Direction Inbound -Protocol TCP -LocalPort 5985 -RemoteAddress LocalSubnet -Action Allow -ErrorAction SilentlyContinue"'
$result = Invoke-WmiMethod -Class Win32_Process -Name Create -ComputerName $hostIp -Credential $credential -ArgumentList $command
if ($result.ReturnValue -ne 0) {throw "Remote process creation failed: $($result.ReturnValue)"}
Write-Host "Remote WinRM setup started, PID $($result.ProcessId)"
$deadline = (Get-Date).AddSeconds(45)
do {
    Start-Sleep -Seconds 3
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connected = $client.ConnectAsync($hostIp,5985).Wait(1500) -and $client.Connected
    } finally {
        $client.Dispose()
    }
    if ($connected) {break}
} while ((Get-Date) -lt $deadline)
if (!$connected) {throw 'WinRM port 5985 did not open'}
Write-Host 'STATION 56 WINRM READY' -ForegroundColor Green
Read-Host 'Press Enter to close'
