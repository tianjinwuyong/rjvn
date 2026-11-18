$ErrorActionPreference = 'Stop'
$hostIp = '192.168.6.92'
$localExe = Join-Path $PSScriptRoot 'dist\Auto_FCT_Agent.exe'
$reportPath = Join-Path $PSScriptRoot 'station92-deploy-report.json'
if (-not (Test-Path -LiteralPath $localExe)) { throw "Missing package: $localExe" }

$credential = Get-Credential -UserName 'MicrosoftAccount\administrator' -Message 'Station 192.168.6.92 administrator credentials'
try { Set-Item WSMan:\localhost\Client\TrustedHosts -Value $hostIp -Concatenate -Force } catch {}
$session = New-PSSession -ComputerName $hostIp -Credential $credential -Authentication Negotiate
try {
    $preflight = Invoke-Command -Session $session -ScriptBlock {
        $processes = @(Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match 'FCT' -or $_.CommandLine -match 'fct_agent|Auto_FCT'
        } | Select-Object ProcessId,Name,ExecutablePath,CommandLine)
        $tasks = @(Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
            $_.TaskName -match 'FCT' -or ($_.Actions.Execute -join ';') -match 'FCT'
        } | Select-Object TaskName,State,@{n='Execute';e={$_.Actions.Execute -join ';'}})
        [pscustomobject]@{
            Computer = $env:COMPUTERNAME
            MesApi = Test-NetConnection 192.168.6.155 -Port 8080 -InformationLevel Quiet
            MesWeb = Test-NetConnection 192.168.6.155 -Port 5178 -InformationLevel Quiet
            SourceDir = Test-Path -LiteralPath 'D:\电源自动测试系统\数据库'
            Processes = $processes
            Tasks = $tasks
            LoggedOnUser = (Get-CimInstance Win32_ComputerSystem).UserName
        }
    }
    if (-not $preflight.MesApi -or -not $preflight.MesWeb) { throw 'Station 92 cannot reach MES 8080/5178' }
    if (-not $preflight.SourceDir) { throw 'Station 92 source directory D:\电源自动测试系统\数据库 is missing' }

    $runningTarget = @($preflight.Processes | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.EndsWith('.exe') } | Select-Object -First 1).ExecutablePath
    $targetExe = if ($runningTarget) { $runningTarget } else { 'D:\stations\Auto_FCT_Agent.exe' }
    $targetDir = Split-Path -Parent $targetExe
    $stageExe = Join-Path $targetDir 'Auto_FCT_Agent.new.exe'
    Invoke-Command -Session $session -ScriptBlock { param($dir) New-Item -ItemType Directory -Path $dir -Force | Out-Null } -ArgumentList $targetDir
    Copy-Item -LiteralPath $localExe -Destination $stageExe -ToSession $session -Force
    $localHash = (Get-FileHash -LiteralPath $localExe -Algorithm SHA256).Hash

    $result = Invoke-Command -Session $session -ScriptBlock {
        param($target,$stage,$expectedHash,$loggedOnUser)
        $stageHash = (Get-FileHash -LiteralPath $stage -Algorithm SHA256).Hash
        if ($stageHash -ne $expectedHash) { throw 'Staged EXE hash mismatch' }
        $backup = $null
        if (Test-Path -LiteralPath $target) {
            $backup = "$target.$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')).bak"
            Copy-Item -LiteralPath $target -Destination $backup -Force
        }
        $matching = @(Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase)
        })
        foreach ($process in $matching) { Stop-Process -Id $process.ProcessId -Force }
        Move-Item -LiteralPath $stage -Destination $target -Force
        $task = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object {
            ($_.Actions.Execute -join ';').Equals($target,[StringComparison]::OrdinalIgnoreCase) -or $_.TaskName -eq 'RuijingAutoFCT'
        } | Select-Object -First 1
        if (-not $task) {
            $user = if ($loggedOnUser) { $loggedOnUser } else { $env:USERNAME }
            $action = New-ScheduledTaskAction -Execute $target -WorkingDirectory (Split-Path -Parent $target)
            $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
            $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Highest
            Register-ScheduledTask -TaskName 'RuijingAutoFCT' -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
            $task = Get-ScheduledTask -TaskName 'RuijingAutoFCT'
        }
        Start-ScheduledTask -InputObject $task
        Start-Sleep -Seconds 4
        $installedHash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
        $running = @(Get-CimInstance Win32_Process | Where-Object {
            $_.ExecutablePath -and $_.ExecutablePath.Equals($target,[StringComparison]::OrdinalIgnoreCase)
        } | Select-Object ProcessId,Name,ExecutablePath)
        [pscustomobject]@{ Target=$target; Backup=$backup; Hash=$installedHash; HashMatch=($installedHash -eq $expectedHash);
            Task=$task.TaskName; Processes=$running }
    } -ArgumentList $targetExe,$stageExe,$localHash,$preflight.LoggedOnUser

    [pscustomobject]@{ ok=$true; host=$hostIp; preflight=$preflight; install=$result; completedAt=(Get-Date).ToString('o') } |
        ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Host 'INSTALL COMPLETE' -ForegroundColor Green
    Write-Host "Target: $($result.Target)"
    Write-Host "Hash verified: $($result.HashMatch)"
    Write-Host 'This window will close in 8 seconds.'
    Start-Sleep -Seconds 8
} catch {
    [pscustomobject]@{ ok=$false; host=$hostIp; error=$_.Exception.Message; completedAt=(Get-Date).ToString('o') } |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
    Write-Host "INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Read-Host 'Press Enter to close'
    throw
} finally {
    if ($session) { Remove-PSSession $session }
    $credential = $null
}
