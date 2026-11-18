$stations = @(
  @{Name='WaveSolder';     IP='192.168.1.10'},
  @{Name='AOI';        IP='192.168.6.90'},
  @{Name='ICT';        IP='192.168.6.91'},
  @{Name='FCT';        IP='192.168.6.92'},
  @{Name='Router';      IP='192.168.6.93'},
  @{Name='BindCode';       IP='192.168.6.94'},
  @{Name='AssyATE';    IP='192.168.6.95'},
  @{Name='Ultrasonic';      IP='192.168.6.96'},
  @{Name='Aging';  IP='192.168.6.97'},
  @{Name='HiVolt';  IP='192.168.6.98'},
  @{Name='PackATE';    IP='192.168.6.99'},
  @{Name='Pack';       IP='192.168.6.100'}
)

Write-Host 'Testing WinRM (5985=HTTP, 5986=HTTPS) on all stations...' -ForegroundColor Cyan
Write-Host ('=' * 60)

$results = @()
foreach ($s in $stations) {
  $ip = $s.IP
  $name = $s.Name
  $http = $https = $false

  try {
    $c = [System.Net.Sockets.TcpClient]::new()
    $c.Connect($ip, 5985)
    $http = $true
    $c.Close()
  } catch {}

  try {
    $c2 = [System.Net.Sockets.TcpClient]::new()
    $c2.Connect($ip, 5986)
    $https = $true
    $c2.Close()
  } catch {}

  $status = switch ($true) {
    $http  { 'HTTP OK' }
    $https { 'HTTPS OK' }
    default { 'NOT LISTENING' }
  }
  $color = if ($http -or $https) { 'Green' } else { 'Red' }
  Write-Host ('{0,-12} {1,-16} {2}' -f $name, $ip, $status) -ForegroundColor $color

  $results += @{Name=$name; IP=$ip; HTTP=$http; HTTPS=$https}
}

Write-Host ''
$ok = ($results | Where-Object { $_.HTTP -or $_.HTTPS }).Count
Write-Host ('WinRM listening: {0} / {1}' -f $ok, $results.Count) -ForegroundColor Yellow
