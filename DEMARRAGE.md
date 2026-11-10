# Installation ANR sur Windows et Android

## Installateur Windows

1. Sur le PC Windows qui servira l'application, ouvre une fenêtre de commande
   dans le dossier du projet et lance `build_setup_exe.bat`.
2. À la fin, l'installateur se trouve dans `release\SetupApplicationANR.exe`.
   Copie ce fichier sur le PC voulu et exécute-le. Il installe l'application,
   le portail Android et leurs outils de configuration dans le profil Windows,
   puis ajoute les raccourcis au menu Démarrer.
3. Garde WAMP/MySQL installé et démarré sur le PC qui héberge la base. L'EXE
   installe le logiciel, mais ne déplace ni n'initialise pas ta base.

## Accès en consultation sur Android

Cette version Android est une application web installable (PWA), et non un APK.
Elle est prévue pour consulter et rechercher les fiches seulement. Le téléphone
ne se connecte jamais directement à MySQL.

1. Installe Tailscale sur le PC serveur et le téléphone, puis connecte-les au
   même tailnet avec des comptes autorisés.
2. Sur le PC serveur, ouvre le raccourci **Configurer le portail Android** du
   menu Démarrer. Crée un compte de lecture et un mot de passe fort d'au moins
   14 caractères. Fournis le compte MySQL administrateur local quand demandé :
   l'outil crée pour le portail le compte MySQL `anr_mobile`, limité à la lecture
   des fiches et à `localhost`.
3. Ouvre le raccourci **Lancer le portail Android** et laisse sa fenêtre ouverte.
4. Lance le raccourci **Publier le portail Android via Tailscale** dans le menu
   Démarrer. Si Tailscale demande l'activation
   d'HTTPS Serve, accepte uniquement pour ton tailnet. N'active pas Funnel.
   La commande affiche l'URL HTTPS privée du PC.
5. Sur le téléphone connecté à Tailscale, ouvre cette URL dans Chrome, connecte-
   toi avec le compte de lecture créé à l'étape 2, puis choisis **Installer
   l'application** ou **Ajouter à l'écran d'accueil** dans le menu du navigateur.

Le PC serveur doit rester allumé, connecté à Tailscale et exécuter le portail.
N'ouvre pas le port MySQL 3306 sur Internet et ne partage pas l'URL Tailscale
avec des personnes non autorisées.

La consultation mobile n'offre ni ajout, ni modification, ni suppression. Les
connexions MySQL de l'application de bureau sont distinctes de ce portail.
L'authentification mobile est locale au PC serveur; garde les fichiers de
configuration dans `%LOCALAPPDATA%\Application_ANR_MySQL\mobile_portal` privés.

Les comptes lecteur du portail ne sont pas individuels dans la version actuelle.
Les chemins des photos des fiches restent propres aux ordinateurs qui les ont
enregistrées; le portail mobile ne transfère ni n'affiche les photos.

## Installation depuis les sources

Pour développer au lieu d'utiliser l'installateur, installe Python 3.10+ avec
Tcl/Tk puis lance `installer.bat`. La base MySQL reste sur le PC serveur.
