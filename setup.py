import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


ROOT = Path(__file__).resolve().parent
NAVY = "#1b2a47"
YELLOW = "#f7d618"


class SetupWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Installation — Application ANR")
        self.geometry("560x390")
        self.resizable(False, False)
        self.configure(bg="white")
        self.events = queue.Queue()

        self.logo = tk.Canvas(
            self, width=500, height=145, bg="white", highlightthickness=0
        )
        self.logo.pack(pady=(18, 8))
        self._draw_logo()

        tk.Label(
            self,
            text="Installation de l’application ANR",
            font=("Segoe UI", 16, "bold"),
            fg=NAVY,
            bg="white",
        ).pack()
        tk.Label(
            self,
            text="Prépare les composants nécessaires sur cet ordinateur.",
            font=("Segoe UI", 10),
            fg="#52627a",
            bg="white",
        ).pack(pady=(5, 14))

        self.status = tk.StringVar(value="Prêt à installer.")
        tk.Label(
            self, textvariable=self.status, font=("Segoe UI", 9), fg=NAVY, bg="white"
        ).pack(pady=(0, 7))
        self.progress = ttk.Progressbar(self, mode="indeterminate", length=440)
        self.progress.pack()

        self.install_button = tk.Button(
            self,
            text="Installer",
            command=self.install,
            font=("Segoe UI", 10, "bold"),
            fg="white",
            bg=NAVY,
            activebackground="#293d60",
            activeforeground="white",
            relief="flat",
            padx=30,
            pady=8,
            cursor="hand2",
        )
        self.install_button.pack(pady=18)
        tk.Label(
            self,
            text="Python 3.10+ et WAMP/MySQL doivent être installés séparément.",
            font=("Segoe UI", 8),
            fg="#6b7280",
            bg="white",
        ).pack()
        self.after(100, self._check_events)

    def _draw_logo(self):
        canvas = self.logo
        canvas.create_rectangle(12, 12, 142, 142, fill=NAVY, outline="")
        canvas.create_polygon(
            77, 29, 86, 51, 110, 54, 92, 70, 97, 94, 77, 82,
            57, 94, 62, 70, 44, 54, 68, 51, fill=YELLOW, outline=""
        )
        canvas.create_text(
            77, 116, text="ANR", fill="white", font=("Arial", 24, "bold")
        )
        canvas.create_text(
            174, 62, text="ANR", fill=NAVY, font=("Arial", 34, "bold"), anchor="w"
        )
        canvas.create_text(
            176, 97, text="RENSEIGNEMENT", fill="#52627a",
            font=("Arial", 12), anchor="w"
        )
        for x, color in ((12, "#007fff"), (55, YELLOW), (98, "#ce1021")):
            canvas.create_rectangle(x, 138, x + 44, 144, fill=color, outline="")

    def install(self):
        self.install_button.configure(state="disabled")
        self.status.set("Installation des dépendances en cours…")
        self.progress.start(10)
        threading.Thread(target=self._install, daemon=True).start()

    def _install(self):
        python = sys.executable
        commands = [
            ([python, "-m", "venv", str(ROOT / ".venv")], "Création de l’environnement…"),
            (
                [
                    str(ROOT / ".venv" / "Scripts" / "python.exe"),
                    "-m",
                    "pip",
                    "install",
                    "-r",
                    str(ROOT / "requirements.txt"),
                ],
                "Installation des dépendances…",
            ),
        ]
        try:
            for command, status in commands:
                self.events.put(("status", status))
                subprocess.run(command, cwd=ROOT, check=True)
            self.events.put(("success", None))
        except (OSError, subprocess.CalledProcessError) as error:
            self.events.put(("error", str(error)))

    def _check_events(self):
        try:
            while True:
                event, detail = self.events.get_nowait()
                if event == "status":
                    self.status.set(detail)
                elif event == "success":
                    self.progress.stop()
                    self.status.set("Installation terminée.")
                    self.install_button.configure(
                        text="Terminer", state="normal", command=self.destroy
                    )
                    messagebox.showinfo(
                        "Installation terminée",
                        "Les dépendances sont prêtes. Lancez lancer_app.bat pour "
                        "ouvrir l’application.",
                        parent=self,
                    )
                else:
                    self.progress.stop()
                    self.status.set("L’installation a échoué.")
                    self.install_button.configure(state="normal")
                    messagebox.showerror(
                        "Erreur d’installation",
                        f"{detail}\n\nVérifiez votre connexion Internet et réessayez.",
                        parent=self,
                    )
        except queue.Empty:
            pass
        self.after(100, self._check_events)


if __name__ == "__main__":
    SetupWindow().mainloop()
