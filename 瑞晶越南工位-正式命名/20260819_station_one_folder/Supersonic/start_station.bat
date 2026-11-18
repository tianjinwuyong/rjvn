@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "Supersonic Agent" /D "%~dp0supersonic_2d" "%~dp0supersonic_2d\supersonic_agent.exe"

