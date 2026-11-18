@echo off
setlocal
set "SCRIPT_DIR=%~dp0"
node "%SCRIPT_DIR%packages\coding-agent\dist\bundle\cli.js" %*
