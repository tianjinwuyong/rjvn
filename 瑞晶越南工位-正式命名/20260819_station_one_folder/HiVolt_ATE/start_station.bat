@echo off
cd /d "%~dp0"
start "NG Sync Service" /D "%~dp0common_ng_sync_service" "%~dp0common_ng_sync_service\station_ng_sync_service.exe"
timeout /t 2 /nobreak >nul
start "HiVolt ATE" /D "%~dp0hivolt_ate_agent" "%~dp0hivolt_ate_agent\hivolt_ate_agent.exe"

