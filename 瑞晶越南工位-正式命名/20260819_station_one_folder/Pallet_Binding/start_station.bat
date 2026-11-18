@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "Pallet Binding Agent" /D "%~dp0pallet_binding_2d" "%~dp0pallet_binding_2d\pallet_binding_2d_agent.exe"

