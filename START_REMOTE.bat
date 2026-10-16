@echo off
chcp 65001 >nul
rem Запуск студии с доступом с телефона (Tailscale или домашняя сеть). Пароль не сохраняется: задаётся только на время работы.
echo Студия с доступом с телефона.
set /p STUDIO_REMOTE_HOSTS=Адрес компьютера (например 100.101.102.103):
set /p STUDIO_ACCESS_PASSWORD=Пароль для входа с телефона (12 и больше символов):
echo Останавливаю прежний запуск студии...
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
cd /d "%~dp0"
.venv\Scripts\python.exe scripts\start_studio.py --no-browser
echo.
echo На телефоне открой: http://%STUDIO_REMOTE_HOSTS%:5173/login
pause
