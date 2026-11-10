@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Installez d'abord les dépendances avec installer.bat.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" setup_android.py
if errorlevel 1 (
    echo.
    echo La configuration du portail Android a échoué.
    pause
    exit /b 1
)
pause
