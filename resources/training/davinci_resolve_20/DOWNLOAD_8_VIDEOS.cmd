@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title GremoVOD - Check and Download 8 DaVinci Training Videos

rem The authoritative downloader uses Python zipfile instead of the older
rem PowerShell validator. This prevents false "not a valid ZIP" reports.
set "PROJECT_ROOT="
if exist "%~dp0..\..\..\backend\" for %%D in ("%~dp0..\..\..") do set "PROJECT_ROOT=%%~fD"
if not defined PROJECT_ROOT if exist "C:\AI_Workflow_Studio\backend\" set "PROJECT_ROOT=C:\AI_Workflow_Studio"
if not defined PROJECT_ROOT if exist "C:\AI_Workflow_Studio\GremoVOD\backend\" set "PROJECT_ROOT=C:\AI_Workflow_Studio\GremoVOD"
if not defined PROJECT_ROOT (
  echo Enter the FULL path to the GremoVOD project directory.
  echo Example: C:\AI_Workflow_Studio
  set /p "PROJECT_ROOT=Project folder: "
)
if not defined PROJECT_ROOT goto :no_project
if not exist "%PROJECT_ROOT%\" goto :no_project

set "SCRIPT=%PROJECT_ROOT%\resources\training\davinci_resolve_20\download_videos.py"
if not exist "%SCRIPT%" (
  echo.
  echo ERROR: Cannot find "%SCRIPT%"
  echo Open PowerShell in your GremoVOD project folder and run: git pull
  echo Then start this .cmd again.
  pause
  exit /b 2
)

set "PY="
where py.exe >nul 2>nul
if not errorlevel 1 set "PY=py -3"
if not defined PY (
  where python.exe >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Python 3 was not found in PATH. The GremoVOD project requires Python.
  pause
  exit /b 2
)

echo ==============================================================
echo GremoVOD - 8 official Blackmagic training video ZIP archives
echo Output stays on this PC. NOTHING will be uploaded to GitHub.
echo ==============================================================
echo.
echo [STEP 1] Diagnosing previously downloaded .zip and .part files...
%PY% "%SCRIPT%" --priority-eight --verify-only
if errorlevel 1 (
  echo Could not perform the local file check.
  pause
  exit /b 2
)
echo.
echo Please inspect the results above.
echo Press Y to download any missing archives now. Press N to stop.
choice /C YN /M "Download missing archives"
if errorlevel 2 exit /b 0

echo.
echo [STEP 2] Downloading missing or invalid ZIP files...
echo Download will STOP at the first failure and show the reason.
%PY% "%SCRIPT%" --priority-eight --stop-on-error
set "RESULT=%ERRORLEVEL%"
echo.
echo Archive folder:
echo "%PROJECT_ROOT%\resources\training\davinci_resolve_20\downloaded\Training_Videos_ZIP"
if %RESULT% NEQ 0 (
  echo.
  echo Download or ZIP validation error. Do NOT repeat all 8 downloads.
  echo Show the diagnostic message above so the exact problem can be fixed.
)
pause
exit /b %RESULT%

:no_project
echo ERROR: Project directory not found.
pause
exit /b 2
