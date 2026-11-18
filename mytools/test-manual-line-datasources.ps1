# ============================================================
# test-manual-line-datasources.ps1
# Test all manual line data sources connectivity
# Run from a PC on the factory network (192.168.6.x)
# ============================================================
param(
    [string]$StationIP = "",
    [switch]$All
)

$ErrorActionPreference = "Continue"

# Station data source config
$Stations = @(
    @{ Name="ICT";       IP="192.168.6.91"; Type="SMB";     Desc="CSV D:\SRC";       Cred=@{User="Admin";Pass="rj"} },
    @{ Name="FCT";       IP="192.168.6.92"; Type="SMB";     Desc="Excel D:\ATS";     Cred=@{User="Administrator";Pass="rj"} },
    @{ Name="分板机";     IP="192.168.6.93"; Type="None";    Desc="无数据" },
    @{ Name="绑码";       IP="192.168.6.94"; Type="None";    Desc="无数据" },
    @{ Name="组装ATE";    IP="192.168.6.95"; Type="SMB";     Desc="Excel D:\ATS";     Cred=@{User="Administrator";Pass="rj"} },
    @{ Name="超声波";     IP="192.168.6.96"; Type="SQLServer"; Desc="sa/888888 DB=MESDB"; Cred=@{User="sa";Pass="888888"}; DB="MESDB" },
    @{ Name="安托森老化";  IP="192.168.6.97"; Type="MySQL";   Desc="root/8712234";     Cred=@{User="root";Pass="8712234"}; DB="ps" },
    @{ Name="高压ATE";   IP="192.168.6.98"; Type="SMB";     Desc="Excel D:\ATS";     Cred=@{User="Administrator";Pass="rj"} },
    @{ Name="包装ATE";   IP="192.168.6.99"; Type="SMB";     Desc="Excel D:\ATS";     Cred=@{User="Administrator";Pass="rj"} },
    @{ Name="包装";       IP="192.168.6.100"; Type="None";   Desc="无数据" }
)

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Manual Line Data Source Tester" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# Test SMB connectivity and file access
# ============================================================
function Test-SMBShare {
    param($IP, $User, $Pass, $SharePath, $TestFile)

    $result = @{
        OK = $false
        Message = ""
        Data = $null
    }

    try {
        # Map SMB connection via WMI
        $wmiHost = "\\$IP\root\cimv2"
        $session = New-CimSession -ComputerName $IP -Credential (New-Object PSCredential("$IP\$User", (ConvertTo-SecureString $Pass -AsPlainText -Force)) -ErrorAction Stop

        # Try to get file listing via SMB
        $files = Get-ChildItem -Path "\\$IP\$SharePath" -ErrorAction Stop | Select-Object -First 5 Name
        $result.OK = $true
        $result.Message = "Connected - $($files.Count) files"
        $result.Data = $files
        $session | Remove-CimSession

    } catch {
        $result.Message = "SMB Error: $($_.Exception.Message)"
    }

    return $result
}

# ============================================================
# Test SQL Server
# ============================================================
function Test-SQLServer {
    param($IP, $User, $Pass, $Database)

    $result = @{
        OK = $false
        Message = ""
        Data = $null
    }

    try {
        $conn = New-Object System.Data.SqlClient.SqlConnection
        $conn.ConnectionString = "Server=$IP;Database=$Database;User ID=$User;Password=$Pass;TrustServerCertificate=True;Connection Timeout=5"
        $conn.Open()

        $cmd = $conn.CreateCommand()
        $cmd.CommandText = "SELECT TOP 3 * FROM ps_station_log ORDER BY tested_at DESC"
        $reader = $cmd.ExecuteReader()

        $data = @()
        while ($reader.Read()) {
            $row = @{}
            for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                $row[$reader.GetName($i)] = $reader.GetValue($i)
            }
            $data += $row
        }

        $result.OK = $true
        $result.Message = "Connected - $($data.Count) rows"
        $result.Data = $data

        $conn.Close()
    } catch {
        $result.Message = "SQL Error: $($_.Exception.Message)"
    }

    return $result
}

# ============================================================
# Test MySQL
# ============================================================
function Test-MySQL {
    param($IP, $User, $Pass, $Database)

    $result = @{
        OK = $false
        Message = ""
        Data = $null
    }

    try {
        # Try using MySQL ODBC or direct connection
        # First try - check if we have MySQL CLI
        $mysqlPath = (Get-Command mysql -ErrorAction SilentlyContinue).Source
        if ($mysqlPath) {
            $output = & mysql -h $IP -u $User -p$Pass -e "USE $Database; SELECT * FROM ps_station_log ORDER BY tested_at DESC LIMIT 3;" 2>&1
            if ($LASTEXITCODE -eq 0) {
                $result.OK = $true
                $result.Message = "MySQL Connected"
                $result.Data = $output
            } else {
                $result.Message = "MySQL Error: $output"
            }
        } else {
            # Try ODBC
            $connStr = "Driver={MySQL ODBC 8.0 Unicode Driver};Server=$IP;Database=$Database;User=$User;Password=$Pass;"
            $conn = New-Object System.Data.Odbc.OdbcConnection($connStr)
            $conn.Open()
            $cmd = $conn.CreateCommand()
            $cmd.CommandText = "SELECT * FROM ps_station_log ORDER BY tested_at DESC LIMIT 3"
            $reader = $cmd.ExecuteReader()

            $data = @()
            while ($reader.Read()) {
                $row = @{}
                for ($i = 0; $i -lt $reader.FieldCount; $i++) {
                    $row[$reader.GetName($i)] = $reader.GetValue($i)
                }
                $data += $row
            }

            $result.OK = $true
            $result.Message = "MySQL Connected - $($data.Count) rows"
            $result.Data = $data

            $conn.Close()
        }
    } catch {
        $result.Message = "MySQL Error: $($_.Exception.Message)"
    }

    return $result
}

# ============================================================
# Test a specific station
# ============================================================
function Test-Station {
    param($Station)

    $name = $Station.Name
    $ip = $Station.IP
    $type = $Station.Type
    $desc = $Station.Desc

    Write-Host "[$name] $ip ($type) - $desc" -ForegroundColor Yellow

    # Ping test first
    $ping = Test-Connection -ComputerName $IP -Count 1 -Quiet -ErrorAction SilentlyContinue
    if (-not $ping) {
        Write-Host "  FAIL: Ping failed" -ForegroundColor Red
        return
    }
    Write-Host "  Ping: OK" -ForegroundColor Green

    switch ($type) {
        "SMB" {
            Write-Host "  Testing SMB access..." -ForegroundColor Gray
            $r = Test-SMBShare -IP $Station.IP -User $Station.Cred.User -Pass $Station.Cred.Pass -SharePath "D$\ATS"
            if ($r.OK) {
                Write-Host "  SMB: OK - $($r.Message)" -ForegroundColor Green
                if ($r.Data) {
                    Write-Host "  Files:" -ForegroundColor Cyan
                    $r.Data | ForEach-Object { Write-Host "    $($_.Name)" -ForegroundColor Gray }
                }
            } else {
                Write-Host "  SMB: $($r.Message)" -ForegroundColor Red
            }
        }
        "SQLServer" {
            Write-Host "  Testing SQL Server..." -ForegroundColor Gray
            $r = Test-SQLServer -IP $Station.IP -User $Station.Cred.User -Pass $Station.Cred.Pass -Database $Station.DB
            if ($r.OK) {
                Write-Host "  SQL Server: OK - $($r.Message)" -ForegroundColor Green
                if ($r.Data) {
                    Write-Host "  Sample data:" -ForegroundColor Cyan
                    $r.Data | ForEach-Object { Write-Host "    $($_.SN) | $($_.Result) | $($_.tested_at)" -ForegroundColor Gray }
                }
            } else {
                Write-Host "  SQL Server: $($r.Message)" -ForegroundColor Red
            }
        }
        "MySQL" {
            Write-Host "  Testing MySQL..." -ForegroundColor Gray
            $r = Test-MySQL -IP $Station.IP -User $Station.Cred.User -Pass $Station.Cred.Pass -Database $Station.DB
            if ($r.OK) {
                Write-Host "  MySQL: OK - $($r.Message)" -ForegroundColor Green
                if ($r.Data) {
                    Write-Host "  Sample data:" -ForegroundColor Cyan
                    $r.Data | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
                }
            } else {
                Write-Host "  MySQL: $($r.Message)" -ForegroundColor Red
            }
        }
        "None" {
            Write-Host "  No data source - SKIP" -ForegroundColor DarkGray
        }
    }

    Write-Host ""
}

# ============================================================
# Main
# ============================================================
if ($StationIP) {
    # Test specific station
    $s = $Stations | Where-Object { $_.IP -eq $StationIP }
    if ($s) {
        Test-Station $s
    } else {
        Write-Host "Unknown station IP: $StationIP" -ForegroundColor Red
        Write-Host "Available: $($Stations.IP -join ', ')"
    }
} elseif ($All) {
    # Test all stations
    foreach ($s in $Stations) {
        Test-Station $s
    }
} else {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\$($MyInvocation.MyCommand.Name) -StationIP 192.168.6.92   # Test one station"
    Write-Host "  .\$($MyInvocation.MyCommand.Name) -All                       # Test all stations"
    Write-Host ""
    Write-Host "Stations:" -ForegroundColor Cyan
    $Stations | ForEach-Object { Write-Host "  $($_.IP) - $($_.Name) [$_($_.Type)]" }
}
