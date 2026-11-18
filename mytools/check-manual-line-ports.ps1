# check-manual-line-ports.ps1
param([switch]$All)

$Stations = @(
    @{Name="ICT";       IP="192.168.6.91";  Ports=@(22,135,139,445,1433,3306)},
    @{Name="FCT";       IP="192.168.6.92";  Ports=@(22,135,139,445,1433,3306)},
    @{Name="PanelSaw";  IP="192.168.6.93";  Ports=@(22,135,139,445)},
    @{Name="Labeling";  IP="192.168.6.94";  Ports=@(22,135,139,445)},
    @{Name="AssyATE";   IP="192.168.6.95";  Ports=@(22,135,139,445,1433,3306)},
    @{Name="Ultrasonic";IP="192.168.6.96";  Ports=@(22,135,139,445,1433,3306)},
    @{Name="WaveSolder";IP="192.168.6.97"; Ports=@(22,135,139,445,1433,3306)},
    @{Name="HiPotATE";  IP="192.168.6.98";  Ports=@(22,135,139,445,1433,3306)},
    @{Name="PackATE";   IP="192.168.6.99";  Ports=@(22,135,139,445,1433,3306)},
    @{Name="Packaging"; IP="192.168.6.100"; Ports=@(22,135,139,445)}
)

Write-Host ""
Write-Host "Manual Line Port Checker" -ForegroundColor Cyan
Write-Host ""

function Test-Port {
    param($IP, $Port, $Timeout=1500)
    try {
        $tcp = New-Object System.Net.Sockets.TcpClient
        $async = $tcp.BeginConnect($IP, $Port, $null, $null)
        $wait = $async.AsyncWaitHandle.WaitOne($Timeout, $false)
        $result = $wait -and $tcp.Connected
        $tcp.Close()
        return $result
    } catch { return $false }
}

foreach ($s in $Stations) {
    $ip = $s.IP
    Write-Host ($s.Name.PadRight(12) + " $ip") -NoNewline
    $openPorts = @()
    foreach ($port in $s.Ports) {
        if (Test-Port -IP $ip -Port $port) { $openPorts += $port }
    }
    if ($openPorts.Count -gt 0) {
        Write-Host (" OPEN: " + ($openPorts -join ",")) -ForegroundColor Green
    } else {
        Write-Host " -" -ForegroundColor Red
    }
}
Write-Host ""
