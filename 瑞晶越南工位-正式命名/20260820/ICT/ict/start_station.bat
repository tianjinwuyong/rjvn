@echo off
setlocal
cd /d "%~dp0"
for %%E in (*.exe) do (
  start "RJ Station" "%%~fE"
  exit /b 0
)
echo No station EXE found in %CD%
pause
