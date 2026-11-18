@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "Assembly ATE" /D "%~dp0assembly_ate_agent" "%~dp0assembly_ate_agent\assembly_ate_agent.exe"

