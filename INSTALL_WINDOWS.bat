@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1 || (echo Install Python 3.12 or newer from python.org. & pause & exit /b 1)
where npm >nul 2>&1 || (echo Install Node.js LTS from nodejs.org. & pause & exit /b 1)
if not exist ".venv\Scripts\python.exe" (python -m venv .venv || (pause & exit /b 1))
".venv\Scripts\python.exe" -m pip install -r backend\requirements.lock.txt || (pause & exit /b 1)
pushd frontend
call npm ci
if errorlevel 1 (popd & pause & exit /b 1)
popd
echo Installation complete. Use START_WINDOWS.bat.
pause
