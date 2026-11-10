@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Application dependencies are not installed.
    echo Run installer.bat first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" app.py
if errorlevel 1 (
    echo.
    echo The application stopped because of an error.
    pause
    exit /b 1
)
