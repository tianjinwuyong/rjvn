@echo off
chcp 65001 >nul
title Install fixed Auto FCT Agent on 192.168.6.92
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Deploy-AutoFct-Station92.ps1"
if errorlevel 1 pause
