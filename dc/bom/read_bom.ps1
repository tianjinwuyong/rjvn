$files = @(
  "F:\越南工厂瑞晶\dc\bom\Anker A2672 CD版 1C 100WGaN插墙式电源适配器黑色（US版) SKU：B2672111-001  Vietnam版 2026.5.19 越南东泰.xls",
  "F:\越南工厂瑞晶\dc\bom\NBT 12V1.5A美规插墙式电源适配器冷灰色 产品型号：EPS18R1G AI版 Vietnam版 试产BOM 2023.05.23.xls",
  "F:\越南工厂瑞晶\dc\bom\NBT 12V4A美规桌面式电源适配器冷灰色 产品型号：EPS48R1-36 AI版 Vietnam版 试产BOM 2024.02.24(1).xls"
)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
try {
  foreach ($f in $files) {
    Write-Host "=== FILE: $f ==="
    $wb = $xl.Workbooks.Open($f)
    foreach ($ws in $wb.Sheets) {
      Write-Host "--- Sheet: $($ws.Name) ---"
      $used = $ws.UsedRange
      $maxRow = [Math]::Min($used.Rows.Count, 80)
      $maxCol = [Math]::Min($used.Columns.Count, 15)
      for ($r = 1; $r -le $maxRow; $r++) {
        $row = @()
        for ($c = 1; $c -le $maxCol; $c++) {
          $val = $ws.Cells.Item($r, $c).Text
          if ($val -and $val.Trim() -ne "") { $row += $val }
        }
        if ($row.Count -gt 0) { Write-Host ($row -join " | ") }
      }
      Write-Host ""
    }
    $wb.Close($false)
  }
} catch {
  Write-Host "ERROR: $_"
}
$xl.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($xl) | Out-Null