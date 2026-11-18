# =============================================================================
# System Info Tool - Shows system information
# =============================================================================

Write-Host "=== System Information ===" -ForegroundColor Cyan
Write-Host ""

$os = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor
$cs = Get-CimInstance Win32_ComputerSystem

Write-Host "Computer:" -ForegroundColor Yellow
Write-Host "  Name: $($cs.Name)"
Write-Host "  Domain: $($cs.Domain)"
Write-Host "  Manufacturer: $($cs.Manufacturer)"
Write-Host "  Model: $($cs.Model)"
Write-Host ""

Write-Host "Operating System:" -ForegroundColor Yellow
Write-Host "  $($os.Caption)"
Write-Host "  Version: $($os.Version)"
Write-Host "  Build: $($os.BuildNumber)"
Write-Host "  Architecture: $($os.OSArchitecture)"
Write-Host ""

Write-Host "Processor:" -ForegroundColor Yellow
Write-Host "  $($cpu.Name)"
Write-Host "  Cores: $($cpu.NumberOfCores)"
Write-Host "  Logical Processors: $($cpu.NumberOfLogicalProcessors)"
Write-Host "  Max Speed: $($cpu.MaxClockSpeed) MHz"
Write-Host ""

Write-Host "Memory:" -ForegroundColor Yellow
Write-Host "  Total: $([math]::Round($cs.TotalPhysicalMemory / 1GB, 2)) GB"
Write-Host "  Free: $([math]::Round($os.FreePhysicalMemory / 1MB, 2)) MB"
Write-Host ""

Write-Host "Storage:" -ForegroundColor Yellow
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    $free = [math]::Round($_.FreeSpace / 1GB, 2)
    $total = [math]::Round($_.Size / 1GB, 2)
    Write-Host "  $($_.DeviceID) - $free GB free of $total GB"
}
Write-Host ""

Write-Host "Network:" -ForegroundColor Yellow
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } | ForEach-Object {
    Write-Host "  $($_.IPAddress) ($($_.InterfaceAlias))"
}
