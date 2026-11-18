[CmdletBinding()]
param(
    [string[]]$OnlyIp
)

$ErrorActionPreference = 'Stop'
$mesHost = '192.168.6.155'
$stationDir = 'D:\stations'
$reportPath = Join-Path $PSScriptRoot 'auto-line-deployment-report.json'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$autoRoot = Get-ChildItem -LiteralPath $workspaceRoot -Directory -Recurse |
    Where-Object { $_.Name -like '002-*' } |
    Select-Object -First 1 -ExpandProperty FullName
if (-not $autoRoot) { throw 'Automatic-line source folder was not found.' }

function Resolve-Artifact([string]$name) {
    $matches = @(Get-ChildItem -LiteralPath $autoRoot -File -Recurse -Filter $name |
        Where-Object { $_.DirectoryName -like '*\dist' })
    if ($matches.Count -ne 1) {
        throw "Expected one automatic-line artifact named $name, found $($matches.Count)."
    }
    return $matches[0].FullName
}

$targets = @(
    [pscustomobject]@{ Ip='192.168.6.51'; User='Admin';         Station='AUTO_ICT';        Exe=(Resolve-Artifact 'Auto_ICT_Agent.exe');                 RemoteExe='Auto_ICT_Agent.exe';               Task='RuijingAutoICT' },
    [pscustomobject]@{ Ip='192.168.6.52'; User='Administrator'; Station='AUTO_FCT';        Exe=(Resolve-Artifact 'Auto_FCT_Agent.exe');                 RemoteExe='Auto_FCT_Agent.exe';               Task='RuijingAutoFCT' },
    [pscustomobject]@{ Ip='192.168.6.53'; User='Administrator'; Station='AUTO_DEPANEL';    Exe=(Resolve-Artifact 'Auto_Depanel_Agent.exe');             RemoteExe='Auto_Depanel_Agent.exe';           Task='RuijingAutoDepanel' },
    [pscustomobject]@{ Ip='192.168.6.54'; User='Administrator'; Station='AUTO_SHELL_BIND'; Exe=(Resolve-Artifact 'qrbinding_2d_win10.exe');              RemoteExe='qrbinding_2d_win10.exe';            Task='RuijingAutoShellBinding' },
    [pscustomobject]@{ Ip='192.168.6.55'; User='Administrator'; Station='AUTO_ASSEMBLY';   Exe=(Resolve-Artifact 'Auto_Assembly_ATE_Agent.exe');        RemoteExe='Auto_Assembly_ATE_Agent.exe';      Task='RuijingAutoAssemblyATE' },
    [pscustomobject]@{ Ip='192.168.6.56'; User='PC';            Station='AUTO_SUPERSONIC'; Exe=(Resolve-Artifact 'Auto_Supersonic_Agent.exe');          RemoteExe='Auto_Supersonic_Agent.exe';        Task='RuijingAutoSupersonic' },
    [pscustomobject]@{ Ip='192.168.6.57'; User='CH';            Station='AUTO_AGING';      Exe=(Resolve-Artifact 'Auto_Aging_Cab_Agent.exe');           RemoteExe='Auto_Aging_Cab_Agent.exe';         Task='RuijingAutoAging' },
    [pscustomobject]@{ Ip='192.168.6.58'; User='Administrator'; Station='AUTO_HIGHVOLT';   Exe=(Resolve-Artifact 'Auto_HighVolt_ATE_Agent.exe');        RemoteExe='Auto_HighVolt_ATE_Agent.exe';      Task='RuijingAutoHighVoltATE' },
    [pscustomobject]@{ Ip='192.168.6.59'; User='Administrator'; Station='AUTO_PACK_LEFT';  Exe=(Resolve-Artifact 'Auto_Packing_ATE_Left_Agent.exe');    RemoteExe='Auto_Packing_ATE_Left_Agent.exe';  Task='RuijingAutoPackingLeft' },
    [pscustomobject]@{ Ip='192.168.6.60'; User='Administrator'; Station='AUTO_PACK_RIGHT'; Exe=(Resolve-Artifact 'Auto_Packing_ATE_Right_Agent.exe');   RemoteExe='Auto_Packing_ATE_Right_Agent.exe'; Task='RuijingAutoPackingRight' },
    [pscustomobject]@{ Ip='192.168.6.61'; User='administrator'; Station='AUTO_OUTERBOX';   Exe=(Resolve-Artifact 'Auto_QRBinding_Agent.exe');           RemoteExe='Auto_QRBinding_Agent.exe';         Task='RuijingAutoQRBinding' }
)
if ($OnlyIp) {
    $targets = @($targets | Where-Object { $_.Ip -in $OnlyIp })
}

$credentials = @{}
$results = [System.Collections.Generic.List[object]]::new()

foreach ($target in $targets) {
    if (-not $credentials.ContainsKey($target.Ip)) {
        $credentials[$target.Ip] = Get-Credential -UserName $target.User -Message "Enter credentials for $($target.Ip) / $($target.User). They are not saved."
    }
    $credential = $credentials[$target.Ip]
    $result = [ordered]@{
        ip = $target.Ip
        station = $target.Station
        status = 'FAILED'
        phase = 'local_preflight'
        localHash = $null
        remoteHash = $null
        taskState = $null
        processPath = $null
        backup = $null
        error = $null
        checkedAt = (Get-Date).ToUniversalTime().ToString('o')
    }
    $session = $null
    try {
        if (-not (Test-Path -LiteralPath $target.Exe -PathType Leaf)) {
            throw "Local EXE missing: $($target.Exe)"
        }
        $result.localHash = (Get-FileHash -LiteralPath $target.Exe -Algorithm SHA256).Hash

        $result.phase = 'remote_preflight'
        $session = New-PSSession -ComputerName $target.Ip -Credential $credential -Authentication Negotiate
        $preflight = Invoke-Command -Session $session -ArgumentList $stationDir,$mesHost -ScriptBlock {
            param($dir,$mes)
            $api = Test-NetConnection -ComputerName $mes -Port 8080 -InformationLevel Quiet
            $web = Test-NetConnection -ComputerName $mes -Port 5178 -InformationLevel Quiet
            [pscustomobject]@{
                computer = $env:COMPUTERNAME
                installDrive = Test-Path -LiteralPath 'D:\'
                mesApi = [bool]$api
                mesWeb = [bool]$web
            }
        }
        if (-not $preflight.installDrive) { throw 'D: drive is unavailable' }
        if (-not $preflight.mesApi -or -not $preflight.mesWeb) {
            throw "MES connectivity failed: api=$($preflight.mesApi), web=$($preflight.mesWeb)"
        }

        $result.phase = 'backup'
        $remotePath = Join-Path $stationDir $target.RemoteExe
        $backup = Invoke-Command -Session $session -ArgumentList $stationDir,$remotePath,$target.Task -ScriptBlock {
            param($dir,$exe,$task)
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            $existing = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($exe,[StringComparison]::OrdinalIgnoreCase) }
            foreach ($process in $existing) {
                Stop-Process -Id $process.ProcessId -Force -ErrorAction SilentlyContinue
            }
            Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $exe) {
                $stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
                $bak = "$exe.$stamp.bak"
                Copy-Item -LiteralPath $exe -Destination $bak -Force
                return $bak
            }
            return $null
        }
        $result.backup = $backup

        $result.phase = 'copy'
        Copy-Item -LiteralPath $target.Exe -Destination $remotePath -ToSession $session -Force

        $result.phase = 'register_and_start'
        $verification = Invoke-Command -Session $session -ArgumentList $remotePath,$target.Task,$result.localHash,$target.User -ScriptBlock {
            param($exe,$task,$expectedHash,$runAsUser)
            $action = New-ScheduledTaskAction -Execute $exe -WorkingDirectory (Split-Path -Parent $exe)
            $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$runAsUser" -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
            Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings -Force | Out-Null
            Start-ScheduledTask -TaskName $task
            Start-Sleep -Seconds 8
            $hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
            $taskInfo = Get-ScheduledTaskInfo -TaskName $task
            $process = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.ExecutablePath -and $_.ExecutablePath.Equals($exe,[StringComparison]::OrdinalIgnoreCase) } |
                Select-Object -First 1
            [pscustomobject]@{
                hash = $hash
                hashMatches = ($hash -eq $expectedHash)
                taskState = (Get-ScheduledTask -TaskName $task).State.ToString()
                taskLastResult = $taskInfo.LastTaskResult
                processPath = $process.ExecutablePath
            }
        }
        $result.remoteHash = $verification.hash
        $result.taskState = $verification.taskState
        $result.processPath = $verification.processPath
        if (-not $verification.hashMatches) { throw 'Remote SHA-256 does not match local artifact' }
        if (-not $verification.processPath) { throw "Agent process did not remain running; task result=$($verification.taskLastResult)" }

        $result.phase = 'verified'
        $result.status = 'DEPLOYED'
    }
    catch {
        $result.error = $_.Exception.Message
    }
    finally {
        if ($session) { Remove-PSSession $session }
        $results.Add([pscustomobject]$result)
    }
}

$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $reportPath -Encoding UTF8
$results | Format-Table ip,station,status,phase,taskState,processPath,error -AutoSize
Write-Host ""
Write-Host "Deployment report: $reportPath"
Read-Host 'Press Enter to close'
