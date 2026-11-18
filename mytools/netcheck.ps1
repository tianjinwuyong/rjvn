# =============================================================================
# Network Check Tool - Test connectivity to hosts
# =============================================================================

param(
    [string]$Host = "8.8.8.8",
    [int]$Count = 4
)

Write-Host "=== Network Connectivity Test ===" -ForegroundColor Cyan
Write-Host ""

function Test-Host {
    param([string]$Target, [int]$Port = 0)
    
    $result = @{
        Host = $Target
        Port = $Port
        Success = $false
        ResponseTime = 0
        Error = $null
    }
    
    try {
        if ($Port -gt 0) {
            $tcp = New-Object System.Net.Sockets.TcpClient
            $connect = $tcp.BeginConnect($Target, $Port, $null, $null)
            $wait = $connect.AsyncWaitHandle.WaitOne(3000, $false)
            if ($wait) {
                try {
                    $tcp.EndConnect($connect)
                    $result.Success = $tcp.Connected
                } catch {
                    $result.Error = $_.Exception.Message
                }
            }
            $tcp.Close()
        } else {
            $ping = Test-Connection -ComputerName $Target -Count 1 -Quiet -ErrorAction SilentlyContinue
            $result.Success = $ping
        }
    } catch {
        $result.Error = $_.Exception.Message
    }
    
    return $result
}

$targets = @(
    @{ Host = "8.8.8.8"; Desc = "Google DNS" },
    @{ Host = "1.1.1.1"; Desc = "Cloudflare DNS" },
    @{ Host = "dns.google"; Desc = "Google DNS (hostname)" },
    @{ Host = $Host; Desc = "Custom Host" }
)

foreach ($t in $targets) {
    Write-Host "Testing: $($t.Desc) ($($t.Host))..." -NoNewline
    $r = Test-Host -Target $t.Host
    if ($r.Success) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAIL" -ForegroundColor Red
        if ($r.Error) { Write-Host "  Error: $($r.Error)" -ForegroundColor DarkGray }
    }
}

Write-Host ""
Write-Host "Testing common ports on $Host..." -ForegroundColor Yellow
$ports = @(21, 22, 23, 25, 53, 80, 110, 143, 443, 445, 3306, 3389, 5432, 8080, 1433)
foreach ($p in $ports) {
    Write-Host "  Port $p..." -NoNewline
    $r = Test-Host -Target $Host -Port $p
    if ($r.Success) {
        Write-Host " OPEN" -ForegroundColor Green
    } else {
        Write-Host " closed" -ForegroundColor DarkGray
    }
}
