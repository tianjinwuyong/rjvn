# =============================================================================
# Log Viewer - Tail/Follow log files
# =============================================================================

param(
    [string]$Path = "",
    [int]$Lines = 50,
    [switch]$Follow
)

if (-not $Path) {
    Write-Host "Usage:" -ForegroundColor Yellow
    Write-Host "  .\log_viewer.ps1 -Path <file> -Lines <n>     # Show last n lines"
    Write-Host "  .\log_viewer.ps1 -Path <file> -Follow        # Follow (tail -f)"
    Write-Host ""
    Write-Host "Examples:" -ForegroundColor Cyan
    Write-Host "  .\log_viewer.ps1 -Path C:\logs\app.log -Lines 100"
    Write-Host "  .\log_viewer.ps1 -Path C:\logs\app.log -Follow"
    Write-Host ""
    
    # Show common log locations
    Write-Host "Common log locations:" -ForegroundColor Yellow
    @(
        "$env:TEMP"
        "$env:windir\Logs"
        "$env:LOCALAPPDATA"
    ) | ForEach-Object {
        Get-ChildItem $_ -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "log|Log|LOG" } | Select-Object -First 5 | ForEach-Object {
            Write-Host "  $($_.FullName)"
        }
    }
    return
}

if (-not (Test-Path $Path)) {
    Write-Host "File not found: $Path" -ForegroundColor Red
    return
}

if ($Follow) {
    Write-Host "Following: $Path" -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Yellow
    Get-Content $Path -Wait -Tail $Lines
} else {
    Write-Host "=== $Path ===" -ForegroundColor Cyan
    Write-Host "Last $Lines lines:`n" -ForegroundColor DarkGray
    Get-Content $Path -Tail $Lines
}
