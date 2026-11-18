$ErrorActionPreference = 'Stop'

$source = '\\tsclient\D\codex-dist-53\Auto_Depanel_Agent.exe'
$targetDir = 'D:\stations'
$target = Join-Path $targetDir 'Auto_Depanel_Agent.exe'
$taskName = 'RuijingAutoDepanel'
$resultPath = '\\tsclient\D\codex-dist-53\auto-53-rdp-result.json'
$result = [ordered]@{
    status = 'FAILED'
    phase = 'preflight'
    localHash = $null
    remoteHash = $null
    backup = $null
    processPath = $null
    taskState = $null
    tcp1003 = $false
    error = $null
    checkedAt = (Get-Date).ToUniversalTime().ToString('o')
}

try {
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        throw "Redirected source is unavailable: $source"
    }
    if (-not (Test-NetConnection 192.168.6.155 -Port 8080 -InformationLevel Quiet)) {
        throw 'MES API 192.168.6.155:8080 is unavailable'
    }
    $result.localHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null

    $result.phase = 'backup'
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase) } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $target) {
        $backup = $target + '.' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + '.bak'
        Copy-Item -LiteralPath $target -Destination $backup -Force
        $result.backup = $backup
    }

    $result.phase = 'install'
    Copy-Item -LiteralPath $source -Destination $target -Force
    $action = New-ScheduledTaskAction -Execute $target -WorkingDirectory $targetDir
    $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$env:USERNAME" -LogonType Interactive -RunLevel Highest
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
    Register-ScheduledTask -TaskName $taskName -Action $action -Principal $principal -Settings $settings -Force | Out-Null
    Start-ScheduledTask -TaskName $taskName
    Start-Sleep -Seconds 8

    $result.phase = 'verify'
    $result.remoteHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    $process = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase) } |
        Select-Object -First 1
    $result.processPath = $process.ExecutablePath
    $result.taskState = (Get-ScheduledTask -TaskName $taskName).State.ToString()
    $result.tcp1003 = [bool](Get-NetTCPConnection -LocalPort 1003 -State Listen -ErrorAction SilentlyContinue)
    if ($result.remoteHash -ne $result.localHash) { throw 'Installed hash mismatch' }
    if (-not $result.processPath) { throw 'Installed process is not running' }
    if (-not $result.tcp1003) { throw 'TCP 1003 is not listening' }
    $result.phase = 'verified'
    $result.status = 'DEPLOYED'
}
catch {
    $result.error = $_.Exception.Message
}
finally {
    $result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $resultPath -Encoding UTF8
}

$result | Format-List
Read-Host 'Press Enter to close'
