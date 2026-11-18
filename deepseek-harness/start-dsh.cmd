@echo off
cd /d "%~dp0"
echo Starting DSH web on http://127.0.0.1:3081
call pnpm dsh web --host 127.0.0.1 --port 3081 --no-open
pause
