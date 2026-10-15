@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0tools\ffmpeg\bin\ffmpeg.exe" set "PATH=%~dp0tools\ffmpeg\bin;%PATH%"
echo === AI Workflow Studio - Windows diagnostics ===
echo.
where python 2>nul
python --version 2>nul
python -m pip --version 2>nul
where py 2>nul
py -V 2>nul
where node 2>nul
node --version 2>nul
where npm 2>nul
call npm --version 2>nul
where ffmpeg 2>nul
ffmpeg -version 2>nul | findstr /b "ffmpeg version"
echo.
echo If Python Manager .msix fails with 0x80070005, install the classic Python 3.12 64-bit .exe from python.org instead.
echo Do not share API keys or passwords in bug reports.
pause
