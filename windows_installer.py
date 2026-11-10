import os
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


PRODUCT_NAME = "Application ANR"
PROGRAMS_DIR = Path(os.environ["LOCALAPPDATA"]) / "Programs"
INSTALL_DIR = PROGRAMS_DIR / PRODUCT_NAME
START_MENU_DIR = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / PRODUCT_NAME
PAYLOAD_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "payload"


def create_shortcut(shortcut_path, target_path, working_directory):
    def quote(value):
        return str(value).replace("'", "''")

    script = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$shortcut = $shell.CreateShortcut('{quote(shortcut_path)}'); "
        f"$shortcut.TargetPath = '{quote(target_path)}'; "
        f"$shortcut.WorkingDirectory = '{quote(working_directory)}'; "
        "$shortcut.Save()"
    )
    encoded = __import__("base64").b64encode(script.encode("utf-16le")).decode("ascii")
    subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-EncodedCommand",
            encoded,
        ],
        check=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class Installer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Installation — Application ANR")
        self.geometry("520x370")
        self.resizable(False, False)
        self.configure(bg="white")

        canvas = tk.Canvas(self, width=480, height=135, bg="white", highlightthickness=0)
        canvas.pack(pady=(15, 5))
        canvas.create_rectangle(12, 12, 132, 132, fill="#1b2a47", outline="")
        canvas.create_polygon(
            72, 25, 81, 47, 105, 50, 87, 66, 92, 90, 72, 78,
            52, 90, 57, 66, 39, 50, 63, 47, fill="#f7d618", outline=""
        )
        canvas.create_text(72, 106, text="ANR", fill="white", font=("Arial", 23, "bold"))
        canvas.create_text(
            158, 57, text="ANR", fill="#1b2a47", font=("Arial", 32, "bold"), anchor="w"
        )
        canvas.create_text(
            160, 88, text="RENSEIGNEMENT", fill="#52627a", font=("Arial", 11), anchor="w"
        )

        tk.Label(
            self,
            text="Installation de l’application ANR",
            font=("Segoe UI", 16, "bold"),
            fg="#1b2a47",
            bg="white",
        ).pack()
        tk.Label(
            self,
            text=f"Installation pour cet utilisateur dans :\n{INSTALL_DIR}",
            font=("Segoe UI", 9),
            fg="#52627a",
            bg="white",
            wraplength=480,
        ).pack(pady=(8, 14))
        self.status = tk.StringVar(value="Prêt à installer.")
        tk.Label(self, textvariable=self.status, fg="#1b2a47", bg="white").pack(pady=5)
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=420)
        self.progress.pack(pady=4)
        self.install_button = tk.Button(
            self,
            text="Installer",
            command=self.install,
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg="#1b2a47",
            activebackground="#293d60",
            activeforeground="white",
            relief="flat",
            padx=28,
            pady=8,
            cursor="hand2",
        )
        self.install_button.pack(pady=16)
        tk.Label(
            self,
            text="WAMP/MySQL reste nécessaire sur le PC serveur.",
            font=("Segoe UI", 8),
            fg="#6b7280",
            bg="white",
        ).pack()

    def install(self):
        if not (PAYLOAD_DIR / "ApplicationANR" / "ApplicationANR.exe").is_file():
            messagebox.showerror(
                "Fichiers d’installation manquants",
                "Le contenu de l’installation est incomplet. Retéléchargez le programme.",
                parent=self,
            )
            return
        self.install_button.configure(state="disabled")
        self.progress.start(10)
        self.status.set("Copie des fichiers de l’application…")
        self.update_idletasks()
        try:
            PROGRAMS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copytree(PAYLOAD_DIR, INSTALL_DIR, dirs_exist_ok=True)
            START_MENU_DIR.mkdir(parents=True, exist_ok=True)
            create_shortcut(
                START_MENU_DIR / "Application ANR.lnk",
                INSTALL_DIR / "ApplicationANR" / "ApplicationANR.exe",
                INSTALL_DIR / "ApplicationANR",
            )
            create_shortcut(
                START_MENU_DIR / "Configurer le portail Android.lnk",
                INSTALL_DIR / "ConfigurerPortailAndroid" / "ConfigurerPortailAndroid.exe",
                INSTALL_DIR / "ConfigurerPortailAndroid",
            )
            create_shortcut(
                START_MENU_DIR / "Lancer le portail Android.lnk",
                INSTALL_DIR / "PortailAndroid" / "PortailAndroid.exe",
                INSTALL_DIR / "PortailAndroid",
            )
            create_shortcut(
                START_MENU_DIR / "Publier le portail Android via Tailscale.lnk",
                INSTALL_DIR / "publier_android_tailscale.bat",
                INSTALL_DIR,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            self.progress.stop()
            self.status.set("L’installation a échoué.")
            self.install_button.configure(state="normal")
            messagebox.showerror(
                "Erreur d’installation",
                f"Impossible de terminer l’installation : {error}",
                parent=self,
            )
            return

        self.progress.stop()
        self.status.set("Installation terminée.")
        self.install_button.configure(text="Terminer", command=self.destroy, state="normal")
        messagebox.showinfo(
            "Installation terminée",
            "L’application ANR est installée. Les raccourcis sont dans le menu "
            "Démarrer. Pour Android, configurez le portail puis publiez-le avec "
            "Tailscale Serve.",
            parent=self,
        )


if __name__ == "__main__":
    Installer().mainloop()
