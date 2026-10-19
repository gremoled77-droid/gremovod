@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
title GremoVOD - Download 8 DaVinci training video ZIPs

rem Standalone downloader. Large media stay on this Windows PC, never in Git.
set "PROJECT_ROOT="
if exist "%~dp0..\..\..\backend\" for %%D in ("%~dp0..\..\..") do set "PROJECT_ROOT=%%~fD"
if not defined PROJECT_ROOT if exist "C:\AI_Workflow_Studio\backend\" set "PROJECT_ROOT=C:\AI_Workflow_Studio"
if not defined PROJECT_ROOT if exist "C:\AI_Workflow_Studio\GremoVOD\backend\" set "PROJECT_ROOT=C:\AI_Workflow_Studio\GremoVOD"
if not defined PROJECT_ROOT (
  echo Enter the FULL path to your GremoVOD project directory.
  echo Example: C:\AI_Workflow_Studio
  set /p "PROJECT_ROOT=Project folder: "
)
if not defined PROJECT_ROOT goto :no_project
if not exist "%PROJECT_ROOT%\" goto :no_project

where curl.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: Windows curl.exe was not found.
  pause
  exit /b 2
)
where powershell.exe >nul 2>nul
if errorlevel 1 (
  echo ERROR: Windows PowerShell was not found.
  pause
  exit /b 2
)

set "DEST_ROOT=%PROJECT_ROOT%\resources\training\davinci_resolve_20\downloaded\Training_Videos_ZIP"
echo.
echo GremoVOD: 8 selected training videos (official Blackmagic ZIP archives)
echo Output: "%DEST_ROOT%"
echo Nothing will be uploaded to GitHub.
echo.
set /a SUCCESS=0,FAILED=0

echo [1/8] Introduction to Editing - Part 1
call :grab "Edit" "DaVinci-Resolve-17-Edit-IntroductiontoEditingPart1.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20250923-xtr312/DaVinci-Resolve-17-Edit-IntroductiontoEditingPart1.zip"
echo.
echo [2/8] Introduction to Editing - Part 2
call :grab "Edit" "DaVinci-Resolve-17-Edit-IntroductiontoEditingPart2.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Edit-IntroductiontoEditingPart2.zip"
echo.
echo [3/8] Introduction to Sound Design
call :grab "Fairlight" "DaVinci-Resolve-17-Fairlight-IntroductiontoSoundDesign.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fairlight-IntroductiontoSoundDesign.zip"
echo.
echo [4/8] Introduction to Mixing
call :grab "Fairlight" "DaVinci-Resolve-17-Fairlight-IntroductiontoMixing.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fairlight-IntroductiontoMixing.zip"
echo.
echo [5/8] Recording VO and ADR
call :grab "Fairlight" "DaVinci-Resolve-17-Fairlight-RecordingVOandADR.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fairlight-RecordingVOandADR.zip"
echo.
echo [6/8] Visual Effects in the Edit Page
call :grab "Edit" "DaVinci-Resolve-17-Edit-VisualEffectsintheEditPage.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Edit-VisualEffectsintheEditPage.zip"
echo.
echo [7/8] Basic Compositing
call :grab "Fusion" "DaVinci-Resolve-17-Fusion-BasicCompositing.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20211222-xtr312/DaVinci-Resolve-17-Fusion-BasicCompositing.zip"
echo.
echo [8/8] Delivering Content
call :grab "Color" "DaVinci-Resolve-17-Color-DeliveringContent.zip" "https://downloads.blackmagicdesign.com/products/davinciresolve/training/videos/DR17/video-downloads/20220210-xtr313/DaVinci-Resolve-17-Color-DeliveringContent.zip"
echo.

echo ============================================================
echo Done: %SUCCESS% / 8 valid ZIP files. Errors: %FAILED%.
echo Files: "%DEST_ROOT%"
if exist "%DEST_ROOT%\" explorer.exe "%DEST_ROOT%"
echo.
if %FAILED% GTR 0 (
  echo Some downloads failed. Run this .cmd again to retry.
) else (
  echo All 8 selected downloads are present and valid ZIPs.
)
pause
if %FAILED% GTR 0 exit /b 1
exit /b 0

:no_project
echo ERROR: No valid project directory given.
pause
exit /b 2

:grab
set "SECTION=%~1"
set "NAME=%~2"
set "URL=%~3"
set "FOLDER=%DEST_ROOT%\%SECTION%"
set "DEST=%FOLDER%\%NAME%"
if not exist "%FOLDER%\" mkdir "%FOLDER%"
set "ZIP_TO_CHECK=%DEST%"
call :validate_zip
if not errorlevel 1 (
  echo [SKIP] Already downloaded: %NAME%
  set /a SUCCESS+=1
  exit /b 0
)
if exist "%DEST%" (
  echo Invalid existing file; moving it to .invalid instead of overwriting.
  move /Y "%DEST%" "%DEST%.invalid" >nul
)
echo [GET] %NAME%
curl.exe --fail --location --show-error --progress-bar --retry 4 --retry-delay 5 --connect-timeout 30 --continue-at - --output "%DEST%.part" "%URL%"
if errorlevel 1 (
  echo [RETRY] Cannot resume. Trying a new download.
  if exist "%DEST%.part" del /q "%DEST%.part"
  curl.exe --fail --location --show-error --progress-bar --retry 4 --retry-delay 5 --connect-timeout 30 --output "%DEST%.part" "%URL%"
  if errorlevel 1 (
    echo [ERROR] Could not download %NAME%. Check the internet or official source.
    set /a FAILED+=1
    exit /b 1
  )
)
set "ZIP_TO_CHECK=%DEST%.part"
call :validate_zip
if errorlevel 1 (
  echo [ERROR] Downloaded content is not a valid ZIP: %NAME%
  set /a FAILED+=1
  exit /b 1
)
move /Y "%DEST%.part" "%DEST%" >nul
if errorlevel 1 (
  echo [ERROR] Cannot finalize download: %NAME%
  set /a FAILED+=1
  exit /b 1
)
echo [OK] %NAME%
set /a SUCCESS+=1
exit /b 0

:validate_zip
if not exist "%ZIP_TO_CHECK%" exit /b 1
powershell.exe -NoProfile -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; $z = [IO.Compression.ZipFile]::OpenRead($env:ZIP_TO_CHECK); $z.Dispose(); exit 0 } catch { exit 1 }" >nul 2>nul
exit /b %ERRORLEVEL%
