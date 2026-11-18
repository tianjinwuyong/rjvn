@echo off
title Open Port 22 on All Stations
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open_port22_all_stations.ps1"
pause
