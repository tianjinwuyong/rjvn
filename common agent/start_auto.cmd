@echo off
setlocal
set "PYTHONPATH=%~dp0;%PYTHONPATH%"
python "%~dp0auto_station.py" %*
endlocal
