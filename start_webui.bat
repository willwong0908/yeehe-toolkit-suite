@echo off
setlocal
cd /d "%~dp0"

title Yeehe Toolkit Suite

if exist "%~dp0\.git" (
  python webui_launcher.py
) else if exist "%~dp0program\Yeehe_Toolkit_Suite.exe" (
  "%~dp0program\Yeehe_Toolkit_Suite.exe"
) else (
  python webui_launcher.py
)
exit /b %ERRORLEVEL%
