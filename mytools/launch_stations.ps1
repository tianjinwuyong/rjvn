# launch_stations.ps1 - Starts all station exe from D:\Stations
# Run on each station PC at startup

$ErrorActionPreference = "SilentlyContinue"
$stations = @(
  @{Folder="ICT";         Exes=@("ICT_station.exe")},
  @{Folder="FCT";         Exes=@("FCT_station.exe")},
  @{Folder="分板机";      Exes=@("PCBADividerStation.exe")},
  @{Folder="QRBinding";   Exes=@("QRBinding_v2.exe")},
  @{Folder="AssemblyATE"; Exes=@("AssemblyATE.exe","ScannerHelper_ATE.exe")},
  @{Folder="Ultrasonic";  Exes=@("UltrasonicStation.exe")},
  @{Folder="AgingCab";    Exes=@("AgingCab.exe")},
  @{Folder="HiVoltATE";   Exes=@("HiVoltATE.exe")},
  @{Folder="PackingATE";  Exes=@("PackingATE.exe")},
  @{Folder="PackStation"; Exes=@("PackingStation.exe")}
)

foreach ($st in $stations) {
  $base = "D:\Stations\$($st.Folder)"
  if (-not (Test-Path $base)) { continue }
  foreach ($exe in $st.Exes) {
    $path = Join-Path $base $exe
    if (Test-Path $path) {
      $name = Split-Path $path -Leaf
      $running = Get-Process -Name $name.Replace(".exe","") -ErrorAction SilentlyContinue
      if (-not $running) {
        Start-Process $path -WindowStyle Hidden
        Write-Host "[START] $path"
      } else {
        Write-Host "[SKIP]  $path already running"
      }
    } else {
      Write-Host "[MISS]  $path not found"
    }
  }
}
