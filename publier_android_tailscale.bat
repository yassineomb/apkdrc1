@echo off
setlocal

set "TAILSCALE=%ProgramFiles%\Tailscale\tailscale.exe"
if not exist "%TAILSCALE%" (
    for /f "delims=" %%T in ('where tailscale 2^>nul') do set "TAILSCALE=%%T"
)
if not exist "%TAILSCALE%" (
    echo Tailscale CLI introuvable. Verifiez que Tailscale est installe et actif.
    pause
    exit /b 1
)

echo Publication HTTPS privee dans votre tailnet Tailscale...
echo Cette commande active Serve uniquement, jamais Funnel.
"%TAILSCALE%" serve --bg 8765
if errorlevel 1 (
    echo La publication a echoue. Verifiez Tailscale Serve et son autorisation.
    pause
    exit /b 1
)
echo.
"%TAILSCALE%" serve status
echo.
echo Utilisez l'adresse HTTPS Tailscale affichee sur le telephone.
echo Gardez le portail Android actif sur le PC serveur.
pause
