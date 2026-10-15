# Windows 10 — DISM Error 2 / Installer 2502 + 2503

Observed: DISM 10.0.19041.3636; OS image 10.0.19044.4291; RestoreHealth fails at 56.6% with Error 2 (file not found). This does **not** identify which file is missing.

1. In Administrator CMD run: `DISM /Online /Cleanup-Image /ScanHealth` and `sfc /scannow` (one at a time).
2. In Administrator PowerShell export recent error lines: `Select-String -Path 'C:\Windows\Logs\DISM\dism.log' -Pattern 'Error','0x80070002','Failed' | Select-Object -Last 35 | Out-File "$env:USERPROFILE\Desktop\dism_errors.txt"`
3. Examine the log before choosing a repair source. If using Windows repair ISO, its version/edition/language must match; avoid generic commands that use a mismatched source.
4. Avoid recursive changes to Windows Installer/Temp permissions or deleting WinSxS; these can cause further damage.
5. For AI Studio, prefer a regular Python executable installer, not `python-manager-*.msix`. The application runs as a normal user after setup.
