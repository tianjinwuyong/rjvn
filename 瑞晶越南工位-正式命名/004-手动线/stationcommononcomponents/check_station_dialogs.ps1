param(
    [string]$ProcessName = "aging_cab_agent"
)

$processes = Get-CimInstance Win32_Process -Filter "Name='$ProcessName.exe'" -ErrorAction SilentlyContinue

Write-Host "Process: $ProcessName"
if (-not $processes) {
    Write-Host "No matching process is running."
    exit 0
}

$processes |
    Select-Object ProcessId, ParentProcessId, CreationDate, ExecutablePath, CommandLine |
    Format-List

Write-Host "Window titles:"
Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
    Select-Object Id, MainWindowTitle, Responding, StartTime |
    Format-Table -AutoSize

Write-Host "Recent Application events mentioning this process:"
Get-WinEvent -LogName Application -MaxEvents 100 -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match [regex]::Escape($ProcessName) } |
    Select-Object -First 10 TimeCreated, ProviderName, LevelDisplayName, Message |
    Format-List
