$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$releaseRoot = Split-Path -Parent $root
$dist = Join-Path $releaseRoot 'dist'
$config = Get-Content -Raw (Join-Path $root 'deployment_config.json') | ConvertFrom-Json

$stations = @(
  'manu_pda','manu_aoi','manu_ict','manu_fct','manu_depanel','manu_case_binding',
  'manu_assembly_ate','manu_supersonic','manu_aging','manu_hivolt_ate',
  'manu_packing_ate','manu_outer_box_binding','manu_pallet_binding',
  'auto_pda','auto_aoi','auto_ict','auto_fct','auto_depanel','auto_case_binding',
  'auto_assembly_ate','auto_supersonic','auto_aging','auto_hivolt_ate',
  'auto_packing_ate_left','auto_packing_ate_right','auto_outer_box_binding',
  'auto_pallet_binding'
)

$failures = [System.Collections.Generic.List[string]]::new()
$results = [System.Collections.Generic.List[object]]::new()

foreach ($station in $stations) {
  $exe = Join-Path $dist ("unified_{0}.exe" -f $station)
  if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    $failures.Add("Missing EXE: $exe")
    continue
  }

  $start = New-Object System.Diagnostics.ProcessStartInfo
  $start.FileName = $exe
  $start.Arguments = $station
  $start.WorkingDirectory = $dist
  $start.UseShellExecute = $false
  $start.CreateNoWindow = $true
  $start.RedirectStandardOutput = $true
  $start.RedirectStandardError = $true
  $process = $null
  try {
    $started = $false
    for ($attempt = 1; $attempt -le 3 -and -not $started; $attempt++) {
      $process = New-Object System.Diagnostics.Process
      $process.StartInfo = $start
      try {
        [void]$process.Start()
        $started = $true
      } catch {
        $process.Dispose()
        $process = $null
        if ($attempt -eq 3) { throw }
        Start-Sleep -Seconds 2
      }
    }
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) { throw "exit=$($process.ExitCode) $stderr" }
    $result = $stdout | ConvertFrom-Json
    $expectedLine = if ($station.StartsWith('manu_')) { 'MANUAL_LINE' } else { 'AUTO_LINE' }
    if (-not $result.ok) { throw 'result.ok is false' }
    if ($result.lineDomain -ne $expectedLine) { throw "lineDomain=$($result.lineDomain)" }
    if ($result.mesDomain -ne 'MES') { throw "mesDomain=$($result.mesDomain)" }
    if ($result.scanner.protocol -ne 'TCP_SERVER' -or $result.scanner.port -ne 1003) {
      throw "scanner=$($result.scanner.protocol):$($result.scanner.port)"
    }
    if (-not $result.stationId -or -not $result.lineId) { throw 'stationId/lineId missing' }
    if (@($result.expectedHostIps).Count -eq 0) { throw 'expectedHostIps missing' }
    $results.Add([pscustomobject]@{
      Exe = Split-Path -Leaf $exe
      Station = $result.stationCode
      Line = $result.lineDomain
      IP = @($result.expectedHostIps) -join ','
      Scanner = "TCP/$($result.scanner.port)"
      Status = 'PASS'
    })
  } catch {
    $failures.Add("$station : $($_.Exception.Message)")
  } finally {
    if ($process) { $process.Dispose() }
  }
}

$namingRoot = Get-ChildItem -LiteralPath $releaseRoot -Directory |
  Where-Object { @(Get-ChildItem -LiteralPath $_.FullName -Directory -Filter '004-*' -ErrorAction SilentlyContinue).Count -gt 0 } |
  Select-Object -First 1
$factoryRoot = Get-ChildItem -LiteralPath $namingRoot.FullName -Directory -Filter '004-*' |
  Sort-Object { $_.Name.Length } |
  Select-Object -First 1
$templateChecks = @(
  @{ Name='manual outer-box'; Prefix='(12)'; Count=3 },
  @{ Name='manual pallet'; Prefix='(13)'; Count=3 }
)
foreach ($check in $templateChecks) {
  $stationFolder = Get-ChildItem -LiteralPath $factoryRoot.FullName -Directory |
    Where-Object { $_.Name.StartsWith($check.Prefix) } |
    Select-Object -First 1
  $path = Join-Path $stationFolder.FullName 'print_templates'
  $count = @(Get-ChildItem -LiteralPath $path -File -Filter '*.btw' -ErrorAction SilentlyContinue).Count
  if ($count -ne $check.Count) { $failures.Add("$($check.Name) templates: expected $($check.Count), got $count") }
}

$results | Format-Table -AutoSize
if ($failures.Count) {
  Write-Host "PRECHECK FAILED ($($failures.Count))" -ForegroundColor Red
  $failures | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
  exit 1
}
Write-Host "PRECHECK PASSED: $($results.Count)/$($stations.Count) station executables" -ForegroundColor Green
