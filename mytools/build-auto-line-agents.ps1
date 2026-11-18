$ErrorActionPreference = 'Continue'

$workspace = Split-Path -Parent $PSScriptRoot
$stationRoot = Get-ChildItem -LiteralPath $workspace -Directory |
    Where-Object { $_.Name -like '*-*' } |
    Where-Object {
        Get-ChildItem -LiteralPath $_.FullName -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like '002-*' }
    } |
    Select-Object -First 1
if (-not $stationRoot) {
    throw 'Station source root was not found.'
}
$root = (Get-ChildItem -LiteralPath $stationRoot.FullName -Directory |
    Where-Object { $_.Name -like '002-*' } |
    Select-Object -First 1).FullName
$specs = Get-ChildItem -LiteralPath $root -Recurse -File -Filter '*.spec' |
    Where-Object { $_.Name -notmatch 'Debug' } |
    Sort-Object FullName

$failed = @()
foreach ($spec in $specs) {
    Write-Output ("BUILD_START {0}" -f $spec.FullName)
    Push-Location $spec.DirectoryName
    try {
        & python -m PyInstaller --noconfirm --clean $spec.Name
        if ($LASTEXITCODE -ne 0) {
            $failed += $spec.FullName
            Write-Output ("BUILD_FAIL {0} exit={1}" -f $spec.Name, $LASTEXITCODE)
        } else {
            Write-Output ("BUILD_OK {0}" -f $spec.Name)
        }
    } finally {
        Pop-Location
    }
}

Write-Output ("BUILD_SUMMARY total={0} failed={1}" -f $specs.Count, $failed.Count)
$failed | ForEach-Object { Write-Output ("FAILED {0}" -f $_) }
if ($failed.Count) {
    exit 1
}
