@echo off
setlocal
cd /d "%~dp0"
start "RJ Station" "%~dp0pallet_binding_2d_agent.exe"
exit /b 0
echo No station EXE found under %CD%
pause
