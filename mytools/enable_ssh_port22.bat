@echo off
title Enable SSH + Port 22
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0enable_ssh_port22.ps1"
pause
