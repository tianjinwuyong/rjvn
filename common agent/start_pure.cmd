@echo off
setlocal
set "PYTHONPATH=%~dp0versions\pure;%PYTHONPATH%"
python "%~dp0versions\launch_station.py" --mode pure %*
endlocal
