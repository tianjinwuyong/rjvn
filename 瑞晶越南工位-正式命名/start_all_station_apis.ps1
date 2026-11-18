$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = 'C:\Users\tianj\AppData\Local\Programs\Python\Python38\python.exe' }
if (-not (Test-Path -LiteralPath $Python)) { throw 'Python was not found' }

& $Python (Join-Path $Root 'open_station_api_ports.py')

foreach ($domain in @('MANUAL_LINE','AUTO_LINE')) {
    $running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*station_local_info_api_host.py*--line-domain $domain*"
    }
    if (-not $running) {
        Start-Process -FilePath $Python -ArgumentList @(
            (Join-Path $Root 'station_local_info_api_host.py'), '--line-domain', $domain
        ) -WorkingDirectory $Root -WindowStyle Normal | Out-Null
        Write-Host "Started $domain station APIs"
    } else {
        Write-Host "$domain station APIs already running"
    }
}

Write-Host 'Manual API ports: 12001-12013'
Write-Host 'Auto API ports:    12101-12113'
