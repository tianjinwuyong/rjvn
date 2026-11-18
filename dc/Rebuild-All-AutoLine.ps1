$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot

# Resolve the factory folders by their numeric line prefix; this avoids encoding
# corruption in scripts that embed the Chinese folder name.
$factoryRoot = Get-ChildItem -LiteralPath $workspace -Directory -ErrorAction Stop |
    Where-Object {
        @(Get-ChildItem -LiteralPath $_.FullName -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^002-' }).Count -gt 0
    } | Select-Object -First 1
if (-not $factoryRoot) { throw 'Factory source folder was not found.' }
$autoRoot = Get-ChildItem -LiteralPath $factoryRoot.FullName -Directory -ErrorAction Stop |
    Where-Object { $_.Name -match '^002-' } | Select-Object -First 1 -ExpandProperty FullName
if ([string]::IsNullOrWhiteSpace($autoRoot)) { throw 'Automatic-line source folder was not found.' }

$specNames = @(
    'ICT_Agent.spec','FCT_Agent.spec','Depanel_Agent.spec','qrbinding_2d_win10.spec',
    'Auto_Assembly_ATE_Agent.spec','Auto_Supersonic_Agent.spec','Auto_Aging_Cab_Agent.spec',
    'Auto_HighVolt_ATE_Agent.spec','Auto_Packing_ATE_Left_Agent.spec',
    'Auto_Packing_ATE_Right_Agent.spec','Auto_QRBinding_Agent.spec','Auto_Pallet_Binding_Agent.spec'
)

$env:TEMP = Join-Path $workspace '.runtime\auto-rebuild-temp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP,(Join-Path $workspace '.runtime\auto-rebuild') | Out-Null

$results = [System.Collections.Generic.List[object]]::new()
foreach ($specName in $specNames) {
    $result = [ordered]@{ spec=$specName; status='FAILED'; dist=$null; exe=$null; sha256=$null; backup=@(); error=$null }
    try {
        $matches = @(Get-ChildItem -LiteralPath $autoRoot -File -Recurse -Filter $specName -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch '\\build\\' })
        if ($matches.Count -eq 0) {
            $result.status='SKIPPED'; $result.error="Spec not present: $specName"
            $results.Add([pscustomobject]$result); continue
        }
        if ($matches.Count -ne 1) { throw "Expected one $specName, found $($matches.Count)" }
        $spec=$matches[0]; $dist=Join-Path $spec.DirectoryName 'dist'; $work=Join-Path (Join-Path $workspace '.runtime\auto-rebuild') $spec.BaseName
        New-Item -ItemType Directory -Force -Path $dist,$work | Out-Null
        $result.dist=$dist
        foreach ($file in @(Get-ChildItem -LiteralPath $dist -File -Filter '*.exe')) {
            $backup=$file.FullName+'.'+(Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')+'.bak'
            Copy-Item -LiteralPath $file.FullName -Destination $backup -Force; $result.backup += $backup
        }
        & python -m PyInstaller --noconfirm --clean --workpath $work --distpath $dist $spec.FullName
        if ($LASTEXITCODE -ne 0) { throw "PyInstaller exited with $LASTEXITCODE" }
        $built=@(Get-ChildItem -LiteralPath $dist -File -Filter '*.exe' | Sort-Object LastWriteTime -Descending)
        if (-not $built) { throw 'No EXE was produced' }
        $result.exe=$built[0].FullName; $result.sha256=(Get-FileHash $built[0].FullName -Algorithm SHA256).Hash; $result.status='BUILT'
    } catch { $result.error=$_.Exception.Message }
    $results.Add([pscustomobject]$result)
    $results | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'auto-line-build-report.json') -Encoding UTF8
}
$results | Format-Table spec,status,exe,error -AutoSize
