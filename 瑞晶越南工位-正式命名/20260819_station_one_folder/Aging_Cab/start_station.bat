@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "Aging Cab Agent" /D "%~dp0aging_cab" "%~dp0aging_cab\aging_cab_agent.exe"

