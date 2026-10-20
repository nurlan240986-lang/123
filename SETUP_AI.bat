@echo off
setlocal
cd /d "%~dp0"
title JARVIS AI Setup
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_ai.py
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 setup_ai.py
  ) else (
    python setup_ai.py
  )
)
pause
