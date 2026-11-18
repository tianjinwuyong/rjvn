$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path (Split-Path $root -Parent) 'dist'
New-Item -ItemType Directory -Force -Path $dist | Out-Null
python -m PyInstaller --noconfirm --clean --onefile --name unified_ict_station `
  --add-data "$root\deployment_config.json;." `
  --add-data "$root\station_profiles.json;." `
  --add-data "$root\stations.json;." `
  --add-data "$root\legacy_ui_manifest.json;." `
  --paths "$root" "$root\unified_ict_station.py"
Copy-Item "$root\deployment_config.json" "$dist\deployment_config.json" -Force
Copy-Item "$root\station_profiles.json" "$dist\station_profiles.json" -Force
Copy-Item "$root\stations.json" "$dist\stations.json" -Force
Copy-Item "$root\legacy_ui_manifest.json" "$dist\legacy_ui_manifest.json" -Force
Write-Host "Built: $dist\unified_ict_station.exe"
