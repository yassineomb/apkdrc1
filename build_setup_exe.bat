@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Installez d'abord les dependances avec installer.bat.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 (
    echo Installation des outils de compilation echouee.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" build_windows.py
if errorlevel 1 (
    echo La generation du Setup EXE a echoue.
    pause
    exit /b 1
)

echo.
echo Installateur genere dans release\SetupApplicationANR.exe
pause
