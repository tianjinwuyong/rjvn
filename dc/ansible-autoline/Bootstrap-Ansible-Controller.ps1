[CmdletBinding()]
param(
    [string]$Controller = '192.168.6.122',
    [Parameter(Mandatory)]
    [string]$ControllerUser
)

$ErrorActionPreference = 'Stop'
$project = $PSScriptRoot
$remoteParent = '~/ruijing-deployment'

Write-Host "Copying Ansible project to $ControllerUser@$Controller ..." -ForegroundColor Cyan
ssh "$ControllerUser@$Controller" "mkdir -p $remoteParent"
scp -r $project "$ControllerUser@${Controller}:$remoteParent/"

Write-Host 'Installing the Ansible Windows prerequisites and validating the playbook ...' -ForegroundColor Cyan
ssh -t "$ControllerUser@$Controller" @"
set -e
sudo apt-get update
sudo apt-get install -y ansible sshpass python3-winrm
cd $remoteParent/ansible-autoline
chmod 700 run-deploy.sh
ansible-galaxy collection install -r requirements.yml
ansible-playbook --syntax-check deploy.yml
echo ANSIBLE_CONTROLLER_READY
"@

Write-Host ''
Write-Host 'Controller preparation is complete.' -ForegroundColor Green
Write-Host "To deploy: ssh -t $ControllerUser@$Controller '$remoteParent/ansible-autoline/run-deploy.sh'"
