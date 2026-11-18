@echo off
setlocal
cd /d "%~dp0"
for /r "%~dp0" %%E in (*.exe) do (
  start "RJ Station" "%%~fE"
  exit /b 0
)
echo No station EXE found under %CD%
pause
