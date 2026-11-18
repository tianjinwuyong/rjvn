$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path (Split-Path $root -Parent) 'dist'
New-Item -ItemType Directory -Force -Path $dist | Out-Null
$stations = @('pda','aoi','ict','fct','depanel','case_binding','assembly_ate','supersonic','aging','hivolt_ate','packing_ate','outer_box_binding','pallet_binding')
foreach ($station in $stations) {
  python -m PyInstaller --noconfirm --clean --onefile --name "unified_manu_$station" `
    --add-data "$root\deployment_config.json;." `
    --add-data "$root\station_profiles.json;." `
    --add-data "$root\stations.json;." `
    --add-data "$root\legacy_ui_manifest.json;." `
    --paths "$root" "$root\unified_station.py" | Out-Null
}
Copy-Item "$root\deployment_config.json" "$dist\deployment_config.json" -Force
Copy-Item "$root\station_profiles.json" "$dist\station_profiles.json" -Force
Copy-Item "$root\legacy_ui_manifest.json" "$dist\legacy_ui_manifest.json" -Force
Write-Host "Built $($stations.Count) unified manual station EXEs in $dist"
