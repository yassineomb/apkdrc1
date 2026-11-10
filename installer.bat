@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if errorlevel 1 (
echo Python 3 is not installed or the Python launcher is unavailable.
echo Install Python 3.10 or later, including Tcl/Tk, then run this installer again.
pause
exit /b 1
)

py -3 setup.py
if errorlevel 1 (
echo Setup failed. Check that Python was installed with Tcl/Tk.
pause
exit /b 1
)
