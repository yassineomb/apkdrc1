@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Installez d'abord les dépendances avec installer.bat.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" mobile_portal.py
if errorlevel 1 (
    echo.
    echo Le portail Android s'est arrêté sur une erreur.
    pause
    exit /b 1
)
