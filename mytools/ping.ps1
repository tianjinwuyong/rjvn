# =============================================================================
# Quick Ping - Ping hosts quickly
# =============================================================================

param(
    [string]$Host = "8.8.8.8",
    [int]$Count = 4,
    [switch]$Continuous
)

function Ping-HostCustom {
    param([string]$Target, [int]$C)
    
    Write-Host "Pinging $Target with $C bytes:" -ForegroundColor Cyan
    
    try {
        $ping = Test-Connection -ComputerName $Target -Count $C -ErrorAction Stop
        $avg = $ping | Measure-Object ResponseTime -Average
        
        Write-Host ""
        Write-Host "Reply from $($ping[0].Address" -ForegroundColor Green
        Write-Host "  Packets: Sent=$C, Received=$($ping.Count), Lost=$($C - $ping.Count) ($([math]::Round((1 - $ping.Count/$C)*100, 0))% loss)"
        Write-Host "  Min=$($ping.ResponseTime | Measure-Object -Minimum).Minimum ms, Max=$($ping.ResponseTime | Measure-Object -Maximum).Maximum ms, Avg=$([math]::Round($avg.Average, 2)) ms"
    } catch {
        Write-Host "Request timed out or host unreachable" -ForegroundColor Red
    }
}

if ($Continuous) {
    Write-Host "Continuous ping to $Host. Press Ctrl+C to stop" -ForegroundColor Yellow
    Write-Host ""
    while ($true) {
        $result = Test-Connection -ComputerName $Host -Count 1 -ErrorAction SilentlyContinue
        if ($result) {
            Write-Host "$((Get-Date).ToString('HH:mm:ss')) Reply from $($result.Address): time=$($result.ResponseTime)ms" -ForegroundColor Green
        } else {
            Write-Host "$((Get-Date).ToString('HH:mm:ss')) Request timed out" -ForegroundColor Red
        }
        Start-Sleep -Seconds 1
    }
} else {
    Ping-HostCustom -Target $Host -C $Count
}
