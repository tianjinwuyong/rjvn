# Open firewall ports on all manual line stations
# Run from the server PC (this machine)

$stations = @(
    @{ip="192.168.6.91";  name="ICT";          httpPort=10080; wsPort=1004},
    @{ip="192.168.6.92";  name="FCT";          httpPort=10080; wsPort=1004},
    @{ip="192.168.6.93";  name="Depanel";      httpPort=10080; wsPort=1004},
    @{ip="192.168.6.94";  name="QRBinding";    httpPort=10086; wsPort=1004},
    @{ip="192.168.6.95";  name="AssemblyATE";  httpPort=10080; wsPort=1004},
    @{ip="192.168.6.96";  name="Ultrasonic";    httpPort=10080; wsPort=1004},
    @{ip="192.168.6.97";  name="AgingCab";     httpPort=10080; wsPort=1004},
    @{ip="192.168.6.98";  name="HiVoltATE";    httpPort=10080; wsPort=1004},
    @{ip="192.168.6.99";  name="PackagingATE";  httpPort=10080; wsPort=1004},
    @{ip="192.168.6.100"; name="Packing";       httpPort=10080; wsPort=1004}
)

$pass = ConvertTo-SecureString "rj" -AsPlainText -Force
$creds = New-Object PSCredential("Administrator", $pass)

foreach ($s in $stations) {
    Write-Host "=== $($s.name) ($($s.ip)) ==="
    try {
        Invoke-Command -ComputerName $s.ip -Credential $creds -Authentication Basic -SessionOption (New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck) -ScriptBlock {
            param($httpPort, $wsPort, $name)

            # Open WinRM port 5985
            $winrmRule = "WinRM_HTTPS"
            $winrmPort = 5985
            $existing = Get-NetFirewallRule -DisplayName $winrmRule -ErrorAction SilentlyContinue
            if ($existing) {
                Remove-NetFirewallRule -DisplayName $winrmRule
                Write-Host "  [DEL] $winrmRule"
            }
            try {
                New-NetFirewallRule -DisplayName $winrmRule -Direction Inbound -Action Allow -LocalPort $winrmPort -Protocol TCP -Enabled True -Profile Any -ErrorAction Stop | Out-Null
                Write-Host "  [OK]  WinRM port $winrmPort opened"
            } catch {
                Write-Host "  [ERR] WinRM port $winrmPort failed: $_"
            }

            # Open station helper ports
            $ports = @($httpPort, $wsPort)
            foreach ($port in $ports) {
                $ruleName = "StationHelper_Port$port"
                $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
                if ($existing) {
                    Remove-NetFirewallRule -DisplayName $ruleName
                    Write-Host "  [DEL] $ruleName"
                }
                try {
                    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -LocalPort $port -Protocol TCP -Enabled True -Profile Any -ErrorAction Stop | Out-Null
                    Write-Host "  [OK]  Port $port opened"
                } catch {
                    Write-Host "  [ERR] Port $port failed: $_"
                }
            }
        } -ArgumentList $s.httpPort, $s.wsPort, $s.name -ErrorAction Stop
    } catch {
        Write-Host "  [ERR] WinRM failed: $_"
    }
    Write-Host ""
}
Write-Host "All done."