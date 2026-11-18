$ErrorActionPreference = 'Continue'
$py = 'C:\Users\tianj\AppData\Local\Programs\Python\Python38\python.exe'
$formal = 'C:\Users\tianj\Desktop\越南工厂瑞晶\瑞晶越南工位-正式命名'
$common = Join-Path $formal '004-手动线\(07)组装ATE\stationcommononcomponents_clean'
$pkg = Join-Path $formal 'station-component-reservoir\python'
$diag = Join-Path $formal 'manualine20260823\diagnostics'
New-Item -ItemType Directory -Force -Path $diag | Out-Null
$env:PYTHONPATH = "$common;$pkg"
$scripts = @(
  @{n='PDA'; p=(Join-Path $formal '004-手动线\(01)PDA扫码上料\pda_heartbeat_agent.py')},
  @{n='AOI'; p=(Join-Path $formal '004-手动线\(02)AOI质量工位\aoi_heartbeat_agent.py')},
  @{n='ICT'; p=(Join-Path $formal '004-手动线\(03)ICT\ict_agent.py')},
  @{n='FCT'; p=(Join-Path $formal '004-手动线\(04)FCT\fct_agent.py')},
  @{n='Depanel'; p=(Join-Path $formal '004-手动线\(05)PCBA分板工位\depanel_heartbeat_agent.py')},
  @{n='QRBinding'; p=(Join-Path $formal '004-手动线\(06)PCBA外壳绑码\reverseqrbinding.py')},
  @{n='Assembly'; p=(Join-Path $formal '004-手动线\(07)组装ATE\assembly_ate_agent.py')},
  @{n='Supersonic'; p=(Join-Path $formal '004-手动线\(08)超声\supersonic_agent.py')},
  @{n='Aging'; p=(Join-Path $formal '004-手动线\(09)成品老化\aging_cab_agent.py')},
  @{n='HiVolt'; p=(Join-Path $formal '004-手动线\(10)高压ATE\hivolt_ate_agent.py')},
  @{n='Packing'; p=(Join-Path $formal '004-手动线\(11)包装ATE\packing_ate_agent.py')},
  @{n='OuterBox'; p=(Join-Path $formal '004-手动线\(12)外箱绑码\outer_box_binding_agent.py')},
  @{n='Pallet'; p=(Join-Path $formal '004-手动线\(13)栈板绑码\pallet_binding_agent.py')}
)
foreach ($item in $scripts) {
  $err = Join-Path $diag ($item.n + '.err.txt')
  $out = Join-Path $diag ($item.n + '.out.txt')
  Remove-Item -LiteralPath $err,$out -Force -ErrorAction SilentlyContinue
  $proc = Start-Process -FilePath $py -ArgumentList @('-u', $item.p) -WorkingDirectory (Split-Path $item.p) -RedirectStandardError $err -RedirectStandardOutput $out -PassThru -WindowStyle Hidden
  Start-Sleep -Seconds 3
  if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Milliseconds 200
  $text = if (Test-Path $err) { (Get-Content -LiteralPath $err -Raw).Trim() } else { '' }
  if ($text) { Write-Output "=== $($item.n) ==="; Write-Output $text } else { Write-Output "=== $($item.n): no stderr ===" }
}
