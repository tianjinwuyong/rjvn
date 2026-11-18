[CmdletBinding()]
param([string[]]$OnlyIp)

$ErrorActionPreference = 'Stop'
$mes = '192.168.6.155'
$stationDir = 'D:\stations'
$workspaceRoot = Split-Path -Parent $PSScriptRoot
$formalRoot = Get-ChildItem -LiteralPath $workspaceRoot -Directory |
    Where-Object Name -Like '*-*' |
    Where-Object { Get-ChildItem -LiteralPath $_.FullName -Directory -Filter '004-*' -ErrorAction SilentlyContinue } |
    Select-Object -First 1
if (!$formalRoot) {throw 'Formal station root was not found'}
$root = Get-ChildItem -LiteralPath $formalRoot.FullName -Directory -Filter '004-*' |
    Select-Object -First 1 -ExpandProperty FullName
$report = Join-Path $PSScriptRoot 'manual-line-deployment-report.json'

$targets = @(
    [pscustomobject]@{Ip='192.168.6.91';User='Admin';Dir='(03)*';Exe='ICT_Agent.exe';Task='RuijingICT';Source='D:\ICT';SourcePort=0},
    [pscustomobject]@{Ip='192.168.6.92';User='Administrator';Dir='(04)*';Exe='fct_agent.exe';Task='RuijingFCT';Source='D:\FCT';SourcePort=0},
    [pscustomobject]@{Ip='192.168.6.93';User='Administrator';Dir='(05)*';Exe='depanel.exe';Task='RuijingDepanel';Source=$null;SourcePort=0},
    [pscustomobject]@{Ip='192.168.6.94';User='Administrator';Dir='(06)*';Exe='qrbinding.exe';Task='RuijingShellBinding';Source=$null;SourcePort=0},
    [pscustomobject]@{Ip='192.168.6.95';User='Administrator';Dir='(07)*';Exe='assembly_ate_agent.exe';Task='RuijingAssemblyATE';Source='ATS_REPORT';SourcePort=0},
    [pscustomobject]@{Ip='192.168.6.96';User='PC';Dir='(08)*';Exe='supersonic_agent.exe';Task='RuijingSupersonic';Source=$null;SourcePort=1433},
    [pscustomobject]@{Ip='192.168.6.97';User='Administrator';Dir='(09)*';Exe='aging_cab_agent.exe';Task='RuijingAging';Source=$null;SourcePort=3306},
    [pscustomobject]@{Ip='192.168.6.98';User='Administrator';Dir='(10)*';Exe='hivolt_ate_agent.exe';Task='RuijingHighVoltATE';Source='ATS_REPORT';SourcePort=0},
    [pscustomobject]@{Ip='192.168.6.99';User='Administrator';Dir='(11)*';Exe='packing_ate_agent.exe';Task='RuijingPackingATE';Source='ATS_REPORT';SourcePort=0}
)
if ($OnlyIp) {$targets = @($targets | Where-Object Ip -in $OnlyIp)}

$results = foreach ($t in $targets) {
    $localDir = Get-ChildItem -LiteralPath $root -Directory -Filter $t.Dir | Select-Object -First 1
    $local = Join-Path $localDir.FullName "dist\$($t.Exe)"
    $r = [ordered]@{ip=$t.Ip;status='FAILED';phase='local_preflight';localHash=$null;remoteHash=$null;taskState=$null;processPath=$null;backup=$null;error=$null;checkedAt=(Get-Date).ToUniversalTime().ToString('o')}
    $s = $null
    try {
        if (!(Test-Path -LiteralPath $local -PathType Leaf)) {throw "Missing local EXE: $local"}
        $r.localHash = (Get-FileHash -LiteralPath $local -Algorithm SHA256).Hash
        $cred = Get-Credential -UserName $t.User -Message "Credentials for $($t.Ip) / $($t.User); not saved"
        if (!$cred) {throw 'Credential entry cancelled'}
        $r.phase = 'remote_preflight'
        $s = New-PSSession -ComputerName $t.Ip -Credential $cred -Authentication Negotiate
        $pre = Invoke-Command -Session $s -ArgumentList $mes,$t.Source,$t.SourcePort -ScriptBlock {
            param($mesHost,$source,$sourcePort)
            [pscustomobject]@{
                drive = Test-Path -LiteralPath 'D:\'
                source = if ($source -eq 'ATS_REPORT') {
                    $name = -join ([char[]](0x6D4B,0x8BD5,0x62A5,0x8868))
                    Test-Path -LiteralPath (Join-Path 'D:\ATS' $name)
                } elseif ($source) {Test-Path -LiteralPath $source} else {$true}
                sourcePort = if ($sourcePort) {Test-NetConnection 127.0.0.1 -Port $sourcePort -InformationLevel Quiet} else {$true}
                api = Test-NetConnection $mesHost -Port 8080 -InformationLevel Quiet
                web = Test-NetConnection $mesHost -Port 5178 -InformationLevel Quiet
            }
        }
        if (!$pre.drive -or !$pre.source -or !$pre.sourcePort -or !$pre.api -or !$pre.web) {
            throw "Preflight failed: drive=$($pre.drive), source=$($pre.source), sourcePort=$($pre.sourcePort), MES8080=$($pre.api), MES5178=$($pre.web)"
        }
        $remote = Join-Path $stationDir $t.Exe
        $r.phase = 'backup'
        $r.backup = Invoke-Command -Session $s -ArgumentList $stationDir,$remote,$t.Task -ScriptBlock {
            param($dir,$exe,$task)
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object {$_.ExecutablePath -and $_.ExecutablePath.Equals($exe,[StringComparison]::OrdinalIgnoreCase)} |
                ForEach-Object {Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue}
            Stop-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue
            if (Test-Path -LiteralPath $exe) {
                $bak = "$exe.$((Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')).bak"
                Copy-Item -LiteralPath $exe -Destination $bak -Force
                $bak
            }
        }
        $r.phase = 'copy'
        Copy-Item -LiteralPath $local -Destination $remote -ToSession $s -Force
        $r.phase = 'verify'
        $v = Invoke-Command -Session $s -ArgumentList $remote,$t.Task,$r.localHash,$t.User -ScriptBlock {
            param($exe,$task,$expected,$user)
            $action = New-ScheduledTaskAction -Execute $exe -WorkingDirectory (Split-Path -Parent $exe)
            $principal = New-ScheduledTaskPrincipal -UserId "$env:COMPUTERNAME\$user" -LogonType Interactive -RunLevel Highest
            $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero)
            Register-ScheduledTask -TaskName $task -Action $action -Principal $principal -Settings $settings -Force | Out-Null
            Start-ScheduledTask -TaskName $task
            Start-Sleep 8
            $hash = (Get-FileHash -LiteralPath $exe -Algorithm SHA256).Hash
            $proc = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object {$_.ExecutablePath -and $_.ExecutablePath.Equals($exe,[StringComparison]::OrdinalIgnoreCase)} |
                Select-Object -First 1
            [pscustomobject]@{hash=$hash;match=($hash -eq $expected);task=(Get-ScheduledTask -TaskName $task).State.ToString();path=$proc.ExecutablePath}
        }
        $r.remoteHash=$v.hash;$r.taskState=$v.task;$r.processPath=$v.path
        if (!$v.match) {throw 'Remote hash mismatch'}
        if (!$v.path) {throw 'Agent process did not remain running'}
        $r.phase='verified';$r.status='DEPLOYED'
    } catch {$r.error=$_.Exception.Message}
    finally {if ($s) {Remove-PSSession $s}}
    [pscustomobject]$r
}
$results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $report -Encoding UTF8
$results | Format-Table ip,status,phase,taskState,processPath,error -AutoSize
Write-Host "Report: $report"
Read-Host 'Press Enter to close'
