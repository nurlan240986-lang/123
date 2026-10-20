@echo off
setlocal
cd /d "%~dp0"
title JARVIS App Setup
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_apps.py
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 setup_apps.py
  ) else (
    python setup_apps.py
  )
)
pause
