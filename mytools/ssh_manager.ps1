# =============================================================================
# SSH Server Setup Script
# Usage: Run as Administrator
# =============================================================================

param(
    [string]$Action = "status"
)

$ErrorActionPreference = "Continue"

function Get-IsAdmin {
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($currentUser)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Status {
    Write-Host "`n=== SSH Server Status ===" -ForegroundColor Cyan
    
    $service = Get-Service -Name "sshd" -ErrorAction SilentlyContinue
    
    if ($service) {
        Write-Host "Service: sshd" -ForegroundColor Yellow
        Write-Host "  Status: $($service.Status)" -ForegroundColor $(if ($service.Status -eq 'Running') { 'Green' } else { 'Red' })
        Write-Host "  StartType: $($service.StartType)"
        
        $listening = Get-NetTCPConnection -LocalPort 22 -State Listen -ErrorAction SilentlyContinue
        if ($listening) {
            Write-Host "`nListening on:" -ForegroundColor Green
            $listening | ForEach-Object { Write-Host "  $($_.LocalAddress):$($_.LocalPort)" }
        }
        
        $ips = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "::*" }
        Write-Host "`nIP Addresses:" -ForegroundColor Yellow
        $ips | ForEach-Object { Write-Host "  $($_.IPAddress)" }
        
        $localUser = $env:USERNAME
        Write-Host "`nConnection:" -ForegroundColor Cyan
        Write-Host "  ssh $localUser@$($ips[0].IPAddress)" -ForegroundColor Green
    } else {
        Write-Host "SSH Server not installed" -ForegroundColor Red
        Write-Host "Run with -Action install" -ForegroundColor Yellow
    }
}

function Install-SSH {
    if (-not (Get-IsAdmin)) {
        Write-Host "Please run as Administrator" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Installing SSH Server..." -ForegroundColor Cyan
    
    $cap = Get-WindowsCapability -Online -Name "OpenSSH.Server*" -ErrorAction SilentlyContinue
    if ($cap) {
        Add-WindowsCapability -Online -Name "OpenSSH.Server~~~~0.0.1.0" -ErrorAction SilentlyContinue
        Write-Host "SSH Server installed" -ForegroundColor Green
    } else {
        Write-Host "OpenSSH capability not available" -ForegroundColor Red
    }
}

function Start-SSH {
    Start-Service sshd -ErrorAction SilentlyContinue
    Set-Service sshd -StartupType Automatic -ErrorAction SilentlyContinue
    Enable-NetFirewallRule -Name "OpenSSH-Server-In-TCP" -ErrorAction SilentlyContinue
    Write-Host "SSH Server started" -ForegroundColor Green
}

function Stop-SSH {
    Stop-Service sshd -ErrorAction SilentlyContinue
    Write-Host "SSH Server stopped" -ForegroundColor Yellow
}

function Restart-SSH {
    Restart-Service sshd -ErrorAction SilentlyContinue
    Write-Host "SSH Server restarted" -ForegroundColor Green
}

# Main
Write-Host "=== SSH Server Manager ===" -ForegroundColor Magenta

switch ($Action.ToLower()) {
    "status" { Show-Status }
    "install" { Install-SSH; Start-SSH; Show-Status }
    "start" { Start-SSH }
    "stop" { Stop-SSH }
    "restart" { Restart-SSH }
    "full" {
        Install-SSH
        Start-SSH
        Show-Status
    }
    default {
        Write-Host "`nUsage: .\ssh_manager.ps1 -Action <action>" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Actions:" -ForegroundColor Cyan
        Write-Host "  status   - Show current status (default)"
        Write-Host "  install  - Install and start SSH server"
        Write-Host "  start    - Start SSH server"
        Write-Host "  stop     - Stop SSH server"
        Write-Host "  restart  - Restart SSH server"
        Write-Host "  full     - Full setup (install + start + status)"
        Write-Host ""
        Write-Host "Example:" -ForegroundColor Cyan
        Write-Host "  .\ssh_manager.ps1 -Action full"
    }
}
