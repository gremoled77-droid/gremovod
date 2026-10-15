@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Run INSTALL_WINDOWS.bat first. & pause & exit /b 1)
".venv\Scripts\python.exe" scripts\start_studio.py
if errorlevel 1 pause
