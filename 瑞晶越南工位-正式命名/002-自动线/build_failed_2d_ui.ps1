$ErrorActionPreference = 'Stop'
$autoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$factoryRoot = Split-Path -Parent $autoRoot
$manualRoot = Get-ChildItem -LiteralPath $factoryRoot -Directory |
  Where-Object { $_.Name -like '004-*' -and (Test-Path (Join-Path $_.FullName 'station_repair_workflow.py')) } |
  Select-Object -First 1 -ExpandProperty FullName
$reservoir = Join-Path $factoryRoot 'station-component-reservoir\python'
$manualCase = Get-ChildItem -LiteralPath $manualRoot -Directory |
  Where-Object { $_.Name -like '(12)*' } |
  Select-Object -First 1 -ExpandProperty FullName
$output = Join-Path (Split-Path -Parent $factoryRoot) 'dist\auto-ui'

if (-not $manualRoot) { throw 'Shared manual-line repair component was not found.' }
New-Item -ItemType Directory -Force -Path $output | Out-Null

$targets = @(
  @{ Prefix='(07)*'; Entry='assembly_ate_agent.py'; Name='auto_assembly_ate_ui' },
  @{ Prefix='(06)*'; Entry='qrbinding.py'; Name='auto_case_binding_ui' },
  @{ Prefix='(10)*'; Entry='hivolt_ate_agent.py'; Name='auto_hivolt_ate_ui' },
  @{ Prefix='(12)*'; Entry='outer_box_binding_agent.py'; Name='auto_outer_box_binding_ui' },
  @{ Prefix='(11)*'; Entry='packing_ate_agent.py'; Name='auto_packing_left_ui'; Side='left' },
  @{ Prefix='(11)*'; Entry='packing_ate_agent.py'; Name='auto_packing_right_ui'; Side='right' },
  @{ Prefix='(13)*'; Entry='pallet_binding_agent.py'; Name='auto_pallet_binding_ui' },
  @{ Prefix='(08)*'; Entry='supersonic_agent.py'; Name='auto_supersonic_ui' }
)

foreach ($target in $targets) {
  $stationCandidates = @(Get-ChildItem -LiteralPath $autoRoot -Directory | Where-Object { $_.Name -like $target.Prefix })
  if ($target.Side -eq 'left') { $stationDir = $stationCandidates | Sort-Object Name | Select-Object -Last 1 -ExpandProperty FullName }
  elseif ($target.Side -eq 'right') { $stationDir = $stationCandidates | Sort-Object Name | Select-Object -First 1 -ExpandProperty FullName }
  else { $stationDir = $stationCandidates | Select-Object -First 1 -ExpandProperty FullName }
  $entry = Join-Path $stationDir $target.Entry
  Write-Host "Building $($target.Name) ..."
  python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name $target.Name `
    --distpath $output `
    --workpath (Join-Path $stationDir "build-$($target.Name)") `
    --specpath $stationDir `
    --paths $stationDir `
    --paths $autoRoot `
    --paths $manualRoot `
    --paths $manualCase `
    --paths $reservoir `
    --add-data "$($manualRoot)\station_repair_workflow.py;manual_repair" `
    --add-data "$($manualRoot)\station_resource_viewer.py;manual_repair" `
    --add-data "$($manualRoot)\repair_work_order_store.py;manual_repair" `
    --add-data "$autoRoot\ng-routing.graph.json;manual_repair" `
    --hidden-import station_components `
    --hidden-import station_components.ng_closed_loop `
    --hidden-import station_components.repair_cycle_graph `
    --hidden-import station_common_agent `
    --hidden-import station_i18n `
    --hidden-import repair_work_order_store `
    --hidden-import station_resource_viewer `
    --hidden-import case_binding_core `
    --hidden-import tkinter.simpledialog `
    --hidden-import tkinter.messagebox `
    --hidden-import tkinter.ttk `
    $entry
  if ($LASTEXITCODE -ne 0) { throw "Build failed: $($target.Name)" }
}

Write-Host "Rebuilt $($targets.Count) auto-line 2D UI EXEs in $output"
