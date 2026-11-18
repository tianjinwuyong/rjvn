@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "Depanel Agent" /D "%~dp0depanel_2d" "%~dp0depanel_2d\depanel.exe"

