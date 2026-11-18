$ErrorActionPreference = 'Stop'
$rules = @(
  @{ Name = 'RJ Manual Station Local Info API'; Ports = '12001-12013'; Description = 'MES read-only local-info API for MANUAL_LINE' },
  @{ Name = 'RJ Auto Station Local Info API'; Ports = '12101-12113'; Description = 'MES read-only local-info API for AUTO_LINE' }
)
foreach ($rule in $rules) {
  & netsh advfirewall firewall delete rule "name=$($rule.Name)" | Out-Null
  & netsh advfirewall firewall add rule "name=$($rule.Name)" dir=in action=allow protocol=TCP "localport=$($rule.Ports)" "remoteip=192.168.6.0/24" profile=domain,private "description=$($rule.Description)" | Out-Null
}
Write-Host 'MES read-only local API ports enabled: manual 12001-12013; auto 12101-12113.'
foreach ($rule in $rules) { & netsh advfirewall firewall show rule "name=$($rule.Name)" }
