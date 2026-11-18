@echo off
setlocal
set "PYTHONPATH=%~dp0"
python "%~dp0modular_manual_line.py" %*
endlocal
