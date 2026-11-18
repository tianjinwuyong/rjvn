# =============================================================================
# Disk Usage - Show disk space and large files
# =============================================================================

param(
    [string]$Path = "C:\",
    [int]$Top = 20
)

Write-Host "=== Disk Usage Report ===" -ForegroundColor Cyan
Write-Host ""

# Show all drives
Write-Host "DRIVES:" -ForegroundColor Yellow
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    $total = [math]::Round($_.Size / 1GB, 1)
    $free = [math]::Round($_.FreeSpace / 1GB, 1)
    $used = [math]::Round(($_.Size - $_.FreeSpace) / 1GB, 1)
    $pct = [math]::Round((($_.Size - $_.FreeSpace) / $_.Size) * 100, 1)
    
    $color = if ($pct -gt 90) { "Red" } elseif ($pct -gt 75) { "Yellow" } else { "Green" }
    
    Write-Host ""
    Write-Host "  $($_.DeviceID)" -ForegroundColor Cyan
    Write-Host "    Total: $total GB" 
    Write-Host "    Used:  $used GB ($pct%)" -ForegroundColor $color
    Write-Host "    Free:  $free GB"
}

# Scan for large files if path exists
if (Test-Path $Path) {
    Write-Host ""
    Write-Host "=== Large Files in $Path ===" -ForegroundColor Yellow
    Write-Host "Top $Top largest files:`n" -ForegroundColor DarkGray
    
    Get-ChildItem $Path -Recurse -File -ErrorAction SilentlyContinue | 
        Sort-Object Length -Descending | 
        Select-Object -First $Top | 
        ForEach-Object {
            $size = if ($_.Length -gt 1GB) { "$([math]::Round($_.Length/1GB, 2)) GB" }
                    elseif ($_.Length -gt 1MB) { "$([math]::Round($_.Length/1MB, 2)) MB" }
                    else { "$([math]::Round($_.Length/1KB, 2)) KB" }
            Write-Host "  $size  $($_.FullName)"
        }
}
