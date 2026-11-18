@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "Outer Box Agent" /D "%~dp0outer_box_2d" "%~dp0outer_box_2d\outer_box_binding_2d_agent.exe"

