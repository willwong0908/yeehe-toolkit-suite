@echo off
setlocal
cd /d "%~dp0"

set "APP_TITLE=AI Term Extractor WebUI"
title %APP_TITLE%

echo ==============================================
echo %APP_TITLE%
echo.
echo URL: http://127.0.0.1:8765
echo State: starting
echo.
echo A browser window will open automatically.
echo Keep this window open while the app is running.
echo Close this window or press Ctrl+C to stop the app.
echo ==============================================
echo.

start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'"

if exist "%~dp0program\AI_Term_Extractor_WebUI.exe" (
  "%~dp0program\AI_Term_Extractor_WebUI.exe"
) else (
  python term_extractor_app\web_app.py
)

echo.
echo WebUI stopped.
echo Press any key to close this window...
pause >nul
