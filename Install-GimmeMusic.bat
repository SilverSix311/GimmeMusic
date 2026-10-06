@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Portable.ps1"
if errorlevel 1 (
  echo.
  echo Installation stopped. Fix the error above, then run this file again to resume.
  pause
  exit /b 1
)
pause
