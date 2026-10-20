@echo off
setlocal
cd /d "%~dp0"
title JARVIS Windows Assistant
if exist ".venv\Scripts\python.exe" goto installed
where py >nul 2>nul
if not errorlevel 1 (
  py -3 -m venv .venv
) else (
  python -m venv .venv
)
if errorlevel 1 goto python_error
:installed
".venv\Scripts\python.exe" -c "import psutil" >nul 2>nul
if not errorlevel 1 goto run
echo Installing the system metrics module. Internet is required once.
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto install_error
:run
".venv\Scripts\python.exe" app.py
pause
exit /b
:python_error
echo Install Python 3.11 or newer from https://www.python.org/downloads/windows/
echo Select "Add python.exe to PATH", then run START.bat again.
pause
exit /b 1
:install_error
echo Installation failed. Check your internet connection and try again.
pause
exit /b 1
