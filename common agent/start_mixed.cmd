@echo off
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
if "%~1"=="" (
  python "%~dp0modular_manual_line.py" --gallery
) else (
  python "%~dp0versions\launch_station.py" --mode mixed %*
)
endlocal
