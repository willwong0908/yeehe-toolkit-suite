@echo off
setlocal
cd /d "%~dp0"

echo Stopping WebUI on port 8765...

for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8765 .*LISTENING"') do (
  taskkill /PID %%p /F >nul 2>nul
)

echo Done.
echo Press any key to close this window...
pause >nul
