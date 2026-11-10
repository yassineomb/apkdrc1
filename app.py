import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import customtkinter as ctk
import os
import tempfile
import html
import base64
import mimetypes
import pymysql
import hashlib
import hmac
import io
import re
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "anr_renseignement_db",
    "cursorclass": pymysql.cursors.DictCursor,
}
AUTHENTICATION_ENABLED = False
ALERT_STATUSES = {
    "recherche": "Recherche",
    "condamne": "Condamné",
    "condamné": "Condamné",
    "interpelle": "Interpellé",
    "interpellé": "Interpellé",
    "detenu": "Détenu",
    "détenu": "Détenu",
    "en fuite": "En fuite",
    "classe": "Classé",
    "classé": "Classé",
}


def get_alert_reasons(row):
    status = (row.get("statut_procedural") or "").strip().casefold()
    danger = (row.get("niveau_dangerosite") or "").strip().casefold()
    reasons = []
    if status in ALERT_STATUSES:
        reasons.append(ALERT_STATUSES[status])
    if danger in ("eleve", "élevé"):
        reasons.append("Dangerosité élevée")
    return reasons

def get_db_connection():
    return pymysql.connect(**DB_CONFIG)


def create_app_icon():
    from PIL import Image, ImageDraw

    image = Image.new("RGBA", (64, 64), "#1b2a47")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (2, 2, 61, 61), radius=13, fill="#1b2a47", outline="#f7d618", width=3
    )
    draw.polygon(
        [(32, 9), (35, 18), (45, 18), (37, 24), (40, 34),
         (32, 28), (24, 34), (27, 24), (19, 18), (29, 18)],
        fill="#f7d618",
    )
    draw.text((11, 38), "ANR", fill="#ffffff")
    draw.rectangle((12, 53, 26, 56), fill="#007fff")
    draw.rectangle((27, 53, 41, 56), fill="#f7d618")
    draw.rectangle((42, 53, 52, 56), fill="#ce1021")
    return image


def exporter_fiche_pdf(data, entry_labels, fiche_id=None):
    from PIL import Image
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Flowable
    from reportlab.platypus import (
        Image as ReportLabImage,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    class FitToPage(Flowable):
        def __init__(self, content, content_width):
            super().__init__()
            self.content = content
            self.content_width = content_width
            self.scale = 1
            self.content_height = 0

        def wrap(self, available_width, available_height):
            self.content_width, self.content_height = self.content.wrap(
                available_width, available_height
            )
            self.scale = min(
                1,
                available_width / self.content_width,
                available_height / self.content_height,
            )
            self.width = available_width
            self.height = self.content_height * self.scale
            return self.width, self.height

        def draw(self):
            self.canv.saveState()
            self.canv.scale(self.scale, self.scale)
            horizontal_offset = (
                self.width - self.content_width * self.scale
            ) / (2 * self.scale)
            self.content.drawOn(self.canv, horizontal_offset, 0)
            self.canv.restoreState()

    output_dir = Path(__file__).with_name("pdf document")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(
        r"[^\w-]+", "_", data["nom_complet"], flags=re.UNICODE
    ).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    id_part = f"{fiche_id}_" if fiche_id is not None else ""
    output_path = output_dir / f"fiche_{id_part}{safe_name}_{timestamp}.pdf"

    navy = colors.HexColor("#1b2a47")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "FicheTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        textColor=navy,
        alignment=TA_CENTER,
        spaceAfter=1 * mm,
    )
    subtitle_style = ParagraphStyle(
        "FicheSubtitle",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#66758a"),
        alignment=TA_CENTER,
    )
    section_style = ParagraphStyle(
        "FicheSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=11,
        textColor=colors.white,
    )
    label_style = ParagraphStyle(
        "FicheLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=8,
        textColor=navy,
    )
    value_style = ParagraphStyle(
        "FicheValue",
        parent=styles["Normal"],
        fontSize=7,
        leading=8,
        textColor=colors.HexColor("#263445"),
    )
    page_width, _ = A4
    content_width = page_width - 20 * mm
    photo_flowable = Paragraph(
        "Aucune photo enregistrée",
        ParagraphStyle(
            "NoPhoto",
            parent=styles["Normal"],
            fontSize=8,
            textColor=colors.HexColor("#66758a"),
            alignment=TA_CENTER,
        ),
    )
    photo_path = data.get("photo_path")
    if photo_path:
        if not os.path.isfile(photo_path):
            raise OSError(f"Le fichier photo est introuvable : {photo_path}")
        with Image.open(photo_path) as source_image:
            photo = source_image.convert("RGB")
            photo.thumbnail((34 * mm, 40 * mm), Image.Resampling.LANCZOS)
            photo_buffer = io.BytesIO()
            photo.save(photo_buffer, format="JPEG")
        photo_buffer.seek(0)
        photo_flowable = ReportLabImage(
            photo_buffer, width=34 * mm, height=40 * mm, kind="proportional"
        )

    heading = Table(
        [[
            photo_flowable,
            [
                Paragraph("FICHE INDIVIDUELLE DE RENSEIGNEMENT", title_style),
                Paragraph("ANR — Fiche de renseignement", subtitle_style),
            ],
        ]],
        colWidths=[42 * mm, content_width - 42 * mm],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "CENTER"),
            ("BOX", (0, 0), (0, 0), 0.6, colors.HexColor("#c6ced8")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 1.5, navy),
        ]),
    )

    sections = [
        ("Identité de la personne", [
            "nom_complet", "alias_surnom", "sexe", "date_lieu_naissance",
            "nationalite", "piece_identite", "domicile_habituel",
            "residence_actuelle", "profession_activite", "situation_familiale",
            "personne_a_prevenir", "telephone",
        ]),
        ("Signalement", [
            "taille_corpulence", "signes_particuliers", "langues_accents",
            "num_photo_dossier",
        ]),
        ("Faits et procédure", [
            "qualification_penale", "categorie", "sous_categorie",
            "date_heure_lieu_faits", "mode_operatoire", "groupe_organisation",
            "armes_objets", "niveau_dangerosite", "statut_procedural",
            "date_lieu_interpellation", "lieu_detention",
        ]),
    ]
    def make_section(section_title, keys):
        title = Table(
            [[Paragraph(html.escape(section_title), section_style)]],
            colWidths=[content_width / 2 - 3 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), navy),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]),
        )
        rows = []
        for key in keys:
            label = entry_labels.get(key, key.replace("_", " ").capitalize())
            value = str(data.get(key) or "").strip() or "Non renseigné"
            rows.append([
                Paragraph(html.escape(label), label_style),
                Paragraph(html.escape(value).replace("\n", "<br/>"), value_style),
            ])
        table = Table(
            rows,
            colWidths=[
                (content_width / 2 - 3 * mm) * 0.4,
                (content_width / 2 - 3 * mm) * 0.6,
        ])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d9e0e8")),
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f4f8")),
            ("ROWBACKGROUNDS", (1, 0), (1, -1), [
                colors.white, colors.HexColor("#fbfcfd")
            ]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        return [title, table]

    left_column = (
        make_section(*sections[0])
        + [Spacer(1, 2 * mm)]
        + make_section(*sections[1])
    )
    right_column = make_section(*sections[2])
    columns = Table(
        [[left_column, right_column]],
        colWidths=[content_width / 2, content_width / 2],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    )
    observation_title = Table(
        [[Paragraph("Observations", section_style)]],
        colWidths=[content_width],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), navy),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]),
    )
    observation_text = str(data.get("observations") or "").strip() or "Non renseigné"
    observation = Paragraph(
        html.escape(observation_text).replace("\n", "<br/>"),
        ParagraphStyle(
            "FicheObservations",
            parent=value_style,
            fontName="Helvetica-Bold",
            borderColor=colors.HexColor("#d9e0e8"),
            borderWidth=0.6,
            borderPadding=8,
            backColor=colors.HexColor("#fbfcfd"),
            spaceBefore=3 * mm,
            spaceAfter=3 * mm,
        ),
    )
    observations = Table(
        [[observation]],
        colWidths=[content_width],
        style=TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#d9e0e8")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfcfd")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]),
    )
    page_content = Table(
        [
            [heading],
            [Spacer(1, 3 * mm)],
            [columns],
            [Spacer(1, 2 * mm)],
            [observation_title],
            [observations],
        ],
        colWidths=[content_width],
        style=TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]),
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
        title=f"Fiche individuelle - {data['nom_complet']}",
        author="ANR",
    )
    document.build([FitToPage(page_content, content_width)])
    return output_path


def exporter_fiches_excel(conn, output_path=None):
    import pandas as pd

    if output_path is None:
        output_path = Path(__file__).with_name("fiches_anr_export.xlsx")
    else:
        output_path = Path(output_path)
    output_dir = output_path.parent
    dataframe = pd.read_sql("SELECT * FROM fiches", conn)
    with tempfile.NamedTemporaryFile(
        dir=output_dir,
        prefix="fiches_anr_export_",
        suffix=".xlsx",
        delete=False
    ) as temp_file:
        temporary_path = Path(temp_file.name)

    try:
        dataframe.to_excel(
            temporary_path,
            index=False,
            sheet_name="Fiches Renseignement"
        )
        try:
            os.replace(temporary_path, output_path)
            return output_path
        except PermissionError:
            fallback_path = output_dir / (
                "fiches_anr_export_"
                + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                + ".xlsx"
            )
            os.replace(temporary_path, fallback_path)
            return fallback_path
    finally:
        temporary_path.unlink(missing_ok=True)


class AuthStore:
    HASH_ITERATIONS = 310_000
    ROLES = {"Admin", "Consultation"}

    def __init__(self):
        app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        auth_dir = app_data / "Application_ANR_MySQL"
        auth_dir.mkdir(parents=True, exist_ok=True)
        self.path = auth_dir / "auth_users.sqlite3"
        with self.connection() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY COLLATE NOCASE,
                    password_salt BLOB NOT NULL,
                    password_hash BLOB NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('Admin', 'Consultation')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )"""
            )

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def user_count(self):
        with self.connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    def create_user(self, username, role):
        username = username.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
            raise ValueError("Le nom doit contenir 3 à 32 caractères : lettres, chiffres, point, tiret ou soulignement.")
        if role not in self.ROLES:
            raise ValueError("Rôle utilisateur invalide.")
        password = secrets.token_urlsafe(24)
        salt = secrets.token_bytes(16)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, self.HASH_ITERATIONS
        )
        try:
            with self.connection() as conn:
                conn.execute(
                    "INSERT INTO users (username, password_salt, password_hash, role) VALUES (?, ?, ?, ?)",
                    (username, salt, password_hash, role),
                )
        except sqlite3.IntegrityError as e:
            raise ValueError("Ce nom d'utilisateur existe déjà.") from e
        return password

    def authenticate(self, username, password):
        with self.connection() as conn:
            user = conn.execute(
                "SELECT username, password_salt, password_hash, role FROM users WHERE username = ?",
                (username.strip(),),
            ).fetchone()
        if user is None:
            return None
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), user["password_salt"], self.HASH_ITERATIONS
        )
        if hmac.compare_digest(candidate, user["password_hash"]):
            return {"username": user["username"], "role": user["role"]}
        return None

    def list_users(self):
        with self.connection() as conn:
            return conn.execute(
                "SELECT username, role, created_at FROM users ORDER BY username COLLATE NOCASE"
            ).fetchall()

    def delete_user(self, username, acting_user):
        if username.casefold() == acting_user.casefold():
            raise ValueError("Vous ne pouvez pas supprimer votre propre compte.")
        with self.connection() as conn:
            target = conn.execute(
                "SELECT role FROM users WHERE username = ?", (username,)
            ).fetchone()
            if target is None:
                raise ValueError("Cet utilisateur n'existe plus.")
            if target["role"] == "Admin":
                admin_count = conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'Admin'"
                ).fetchone()[0]
                if admin_count <= 1:
                    raise ValueError("Impossible de supprimer le dernier compte Admin.")
            conn.execute("DELETE FROM users WHERE username = ?", (username,))


class AuthDialog(ctk.CTkToplevel):
    def __init__(self, parent, auth_store):
        super().__init__(parent)
        self.auth_store = auth_store
        self.result = None
        self.first_setup = auth_store.user_count() == 0
        self.title("Créer le compte Admin" if self.first_setup else "Connexion")
        self.geometry("460x300" if self.first_setup else "420x270")
        self.resizable(False, False)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.transient(parent)
        self.grab_set()

        title = "Création du premier compte Admin" if self.first_setup else "Connexion à l'application"
        self.title_label = ctk.CTkLabel(self, text=title, font=("Arial", 17, "bold"))
        self.title_label.pack(pady=(22, 14))
        self.form = ctk.CTkFrame(self, fg_color="transparent")
        self.form.pack(fill="x", padx=35)

        ctk.CTkLabel(self.form, text="Nom d'utilisateur").pack(anchor="w", pady=(5, 2))
        self.username_entry = ctk.CTkEntry(self.form, width=340)
        self.username_entry.pack(fill="x")
        if self.first_setup:
            self.username_entry.insert(0, "Admin")

        if self.first_setup:
            self.password_entry = None
        else:
            ctk.CTkLabel(self.form, text="Mot de passe").pack(anchor="w", pady=(10, 2))
            self.password_entry = ctk.CTkEntry(self.form, width=340, show="*")
            self.password_entry.pack(fill="x")
            self.username_entry.bind("<Return>", lambda _event: self.password_entry.focus_set())
            self.password_entry.bind("<Return>", lambda _event: self.submit())

        self.error_label = ctk.CTkLabel(self, text="", text_color="#c0392b", wraplength=360)
        self.error_label.pack(pady=(8, 0))
        button_text = "Générer le compte Admin" if self.first_setup else "Se connecter"
        ctk.CTkButton(self, text=button_text, command=self.submit).pack(pady=12)
        self.username_entry.focus_set()

    def submit(self):
        username = self.username_entry.get().strip()
        try:
            if self.first_setup:
                password = self.auth_store.create_user(username, "Admin")
                self.result = {"username": username, "role": "Admin"}
                self.show_generated_password(username, password)
            else:
                self.result = self.auth_store.authenticate(username, self.password_entry.get())
                if self.result is None:
                    raise ValueError("Nom d'utilisateur ou mot de passe incorrect.")
                self.destroy()
        except ValueError as e:
            self.error_label.configure(text=str(e))

    def show_generated_password(self, username, password):
        for widget in self.winfo_children():
            if widget is not self.title_label:
                widget.destroy()
        self.unbind("<Return>")
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.geometry("500x250")
        ctk.CTkLabel(
            self,
            text=f"Compte Admin « {username} » créé.\nCopiez et conservez ce mot de passe : il ne sera plus affiché.",
            wraplength=440,
            justify="center"
        ).pack(padx=20, pady=(20, 12))
        password_entry = ctk.CTkEntry(self, width=420)
        password_entry.pack(padx=20, pady=5)
        password_entry.insert(0, password)
        password_entry.configure(state="readonly")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(pady=12)

        def copy_password():
            self.clipboard_clear()
            self.clipboard_append(password)
            self.update()
            messagebox.showinfo("Mot de passe copié", "Conservez-le dans un endroit sûr.", parent=self)

        ctk.CTkButton(actions, text="Copier", command=copy_password).pack(side="left", padx=6)
        ctk.CTkButton(
            actions,
            text="Continuer",
            command=self.destroy
        ).pack(side="left", padx=6)


class UserManagementDialog(ctk.CTkToplevel):
    def __init__(self, parent, auth_store, acting_user):
        super().__init__(parent)
        self.auth_store = auth_store
        self.acting_user = acting_user
        self.title("Gestion des utilisateurs")
        self.geometry("650x480")
        self.transient(parent)
        self.grab_set()

        ctk.CTkLabel(self, text="Comptes utilisateurs", font=("Arial", 17, "bold")).pack(pady=(14, 8))
        self.users_tree = ttk.Treeview(
            self, columns=("username", "role", "created"), show="headings", height=10
        )
        self.users_tree.heading("username", text="Utilisateur")
        self.users_tree.heading("role", text="Rôle")
        self.users_tree.heading("created", text="Créé le")
        self.users_tree.column("username", width=180)
        self.users_tree.column("role", width=140, anchor="center")
        self.users_tree.column("created", width=220, anchor="center")
        self.users_tree.pack(fill="both", expand=True, padx=15, pady=8)

        form = ctk.CTkFrame(self)
        form.pack(fill="x", padx=15, pady=8)
        self.new_username = ctk.CTkEntry(form, placeholder_text="Nouvel utilisateur")
        self.new_username.pack(side="left", fill="x", expand=True, padx=5, pady=8)
        self.new_role = ctk.CTkComboBox(form, values=["Consultation", "Admin"], width=130)
        self.new_role.set("Consultation")
        self.new_role.pack(side="left", padx=5, pady=8)

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=15, pady=(0, 12))
        ctk.CTkButton(actions, text="Ajouter", command=self.add_user).pack(side="left", padx=5)
        ctk.CTkButton(
            actions,
            text="Supprimer l'utilisateur sélectionné",
            fg_color="#c0392b",
            hover_color="#922b21",
            command=self.delete_user
        ).pack(side="left", padx=5)
        self.refresh_users()

    def refresh_users(self):
        for item in self.users_tree.get_children():
            self.users_tree.delete(item)
        for user in self.auth_store.list_users():
            self.users_tree.insert(
                "", "end",
                values=(user["username"], user["role"], user["created_at"])
            )

    def add_user(self):
        try:
            username = self.new_username.get()
            role = self.new_role.get()
            password = self.auth_store.create_user(
                username,
                role
            )
            self.new_username.delete(0, "end")
            self.new_role.set("Consultation")
            self.refresh_users()
            self.show_generated_password(username.strip(), password)
        except ValueError as e:
            messagebox.showerror("Impossible d'ajouter l'utilisateur", str(e), parent=self)

    def show_generated_password(self, username, password):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Mot de passe généré")
        dialog.geometry("480x220")
        dialog.transient(self)
        dialog.grab_set()
        ctk.CTkLabel(
            dialog,
            text=f"Compte « {username} » créé.\nCopiez et transmettez ce mot de passe de façon sûre : il ne sera plus affiché.",
            wraplength=430,
            justify="center"
        ).pack(padx=20, pady=(22, 12))
        password_entry = ctk.CTkEntry(dialog, width=420)
        password_entry.pack(padx=20, pady=5)
        password_entry.insert(0, password)
        password_entry.configure(state="readonly")

        actions = ctk.CTkFrame(dialog, fg_color="transparent")
        actions.pack(pady=12)

        def copy_password():
            dialog.clipboard_clear()
            dialog.clipboard_append(password)
            dialog.update()
            messagebox.showinfo("Mot de passe copié", "Conservez-le dans un endroit sûr.", parent=dialog)

        ctk.CTkButton(actions, text="Copier", command=copy_password).pack(side="left", padx=6)
        ctk.CTkButton(actions, text="Fermer", command=dialog.destroy).pack(side="left", padx=6)

    def delete_user(self):
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showwarning("Sélection requise", "Sélectionnez un utilisateur.", parent=self)
            return
        username = self.users_tree.item(selected[0], "values")[0]
        if not messagebox.askyesno(
            "Confirmation",
            f"Supprimer le compte « {username} » ?",
            parent=self
        ):
            return
        try:
            self.auth_store.delete_user(username, self.acting_user)
            self.refresh_users()
        except ValueError as e:
            messagebox.showerror("Suppression impossible", str(e), parent=self)


class ANRApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(" | Gestion des Fiches Individuelle")
        self.geometry("1200x800")
        from PIL import Image, ImageTk

        self.app_icon = ImageTk.PhotoImage(create_app_icon())
        self.iconphoto(True, self.app_icon)
        try:
            background_path = Path(__file__).with_name(
                "democratic-republic-of-congo-coat-of-arms-vector-24327882.webp"
            )
            self.background_source = Image.open(background_path).convert("RGBA")
            self.background_source.putalpha(82)
            header_image = self.background_source.copy()
            header_image.putalpha(220)
            header_image.thumbnail((62, 58), Image.Resampling.LANCZOS)
            self.header_logo = ImageTk.PhotoImage(header_image)
        except (OSError, ValueError) as e:
            self.background_source = None
            self.header_logo = None
            messagebox.showerror(
                "Arrière-plan indisponible",
                f"Impossible de charger l'emblème : {e}",
                parent=self
            )
        if AUTHENTICATION_ENABLED:
            self.withdraw()
        self.authenticated = False
        self.auth_store = AuthStore()
        if AUTHENTICATION_ENABLED:
            auth_dialog = AuthDialog(self, self.auth_store)
            self.wait_window(auth_dialog)
            if auth_dialog.result is None:
                self.destroy()
                return
            self.current_user = auth_dialog.result
        else:
            self.current_user = {"username": "Mode sans authentification", "role": "Admin"}
        self.authenticated = True
        self.remote_mode = False

        header_frame = ctk.CTkFrame(self, fg_color="#1b2a47", corner_radius=0, height=75)
        header_frame.pack(fill="x", side="top")
        if self.header_logo is not None:
            tk.Label(
                header_frame, image=self.header_logo, bg="#1b2a47", bd=0
            ).place(relx=0.98, rely=0.5, anchor="e")
        
        ctk.CTkLabel(header_frame, text="FICHE INDIVIDUELLE DE RENSEIGNEMENTS", font=("Arial", 11, "bold"), text_color="#d1d8e0").pack(pady=(8, 0))
        ctk.CTkLabel(header_frame, text="Personne criminelle, Subversive ou personne a prendre en charge", font=("Arial", 14, "bold"), text_color="#ffffff").pack(pady=(0, 8))

        self.tabview = ctk.CTkTabview(self, fg_color="transparent", segmented_button_selected_color="#1b2a47")
        self.tabview.pack(fill="both", expand=True, padx=15, pady=15)

        self.tab_form = None
        self.tab_list_name = "  Base de Données & Consultation  "
        self.tab_list = self.tabview.add(self.tab_list_name)

        if self.current_user["role"] == "Admin":
            self.tab_form = self.tabview.add("  Saisie & Édition de Fiche  ")
            self.create_form_tab()
        self.create_list_tab()
        self.deiconify()
        self.after(100, self.load_data)

    def add_background_canvas(self, parent):
        canvas = tk.Canvas(parent, bg="#f4f6f9", highlightthickness=0, bd=0)
        canvas.place(relwidth=1, relheight=1)
        canvas.bind(
            "<Configure>",
            lambda event, target=canvas: self.draw_background(target, event)
        )
        self.after_idle(
            lambda target=canvas: target.tk.call("lower", target._w)
        )
        self.after(0, lambda target=canvas: self.draw_background(target))
        return canvas

    def draw_background(self, canvas, _event=None):
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            return
        canvas.delete("all")
        if self.background_source is not None:
            from PIL import Image

            size = min(int(width * 0.55), int(height * 0.65), 420)
            source_width, source_height = self.background_source.size
            scale = min(size / source_width, size / source_height)
            image = self.background_source.resize(
                (int(source_width * scale), int(source_height * scale)),
                Image.Resampling.LANCZOS
            )
            from PIL import ImageTk

            canvas.background_photo = ImageTk.PhotoImage(image)
            canvas.create_image(
                width // 2, height // 2, image=canvas.background_photo, anchor="center"
            )

    def create_form_tab(self):
        self.add_background_canvas(self.tab_form)
        self.scroll_form = ctk.CTkScrollableFrame(self.tab_form, fg_color="transparent", corner_radius=10)
        self.scroll_form.pack(fill="both", expand=True, padx=5, pady=5)

        lbl_sec1 = ctk.CTkLabel(self.scroll_form, text="  I. IDENTITÉ DE LA PERSONNE & PHOTO", font=("Arial", 12, "bold"), fg_color="#2c3e50", text_color="white", corner_radius=5, anchor="w")
        lbl_sec1.pack(fill="x", pady=(10, 10), ipady=5)

        top_identite_frame = ctk.CTkFrame(self.scroll_form, fg_color="transparent")
        top_identite_frame.pack(fill="x", padx=5, pady=5)

        photo_frame = ctk.CTkFrame(top_identite_frame, fg_color="#ecf0f1", corner_radius=8, border_width=1, border_color="#bdc3c7")
        photo_frame.pack(side="right", padx=10, pady=5, anchor="n")

        self.photo_path_val = ""
        self.photo_label = ctk.CTkLabel(photo_frame, text="Aucune\nphoto", width=100, height=130, fg_color="#bdc3c7", text_color="#333333", corner_radius=5)
        self.photo_label.pack(padx=10, pady=5)

        ctk.CTkButton(photo_frame, text="Parcourir...", fg_color="#34495e", hover_color="#2c3e50", width=100, height=28, font=("Arial", 11), command=self.charger_photo).pack(padx=10, pady=(5, 10))

        f1 = ctk.CTkFrame(top_identite_frame, fg_color="transparent")
        f1.pack(side="left", fill="x", expand=True)

        self.entries = {}
        self.entry_labels = {}
        fields_part1 = [
            ("Nom, Post-nom & Prénom", "nom_complet"), ("Alias / Surnom", "alias_surnom"),
            ("Sexe", "sexe"), ("Date & Lieu de naissance", "date_lieu_naissance"),
            ("Nationalité", "nationalite"), ("Pièce d'identité", "piece_identite"),
            ("Domicile habituel", "domicile_habituel"), ("Résidence actuelle", "residence_actuelle"),
            ("Profession / Activité", "profession_activite"), ("Situation familiale", "situation_familiale"),
            ("Personne à prévenir", "personne_a_prevenir"), ("Téléphone", "telephone")
        ]

        for i, (label_text, key) in enumerate(fields_part1):
            row = i // 2
            col = (i % 2) * 2
            ctk.CTkLabel(f1, text=label_text + ":", font=("Arial", 11, "bold"), text_color="#333333").grid(row=row, column=col, sticky="w", padx=5, pady=6)
            if key == "sexe":
                ent = ctk.CTkComboBox(f1, values=["Masculin", "Féminin"], width=230, fg_color="white", text_color="black")
                ent.set("")
            else:
                ent = ctk.CTkEntry(f1, width=230, fg_color="white", text_color="black", border_color="#bdc3c7")
            ent.grid(row=row, column=col+1, sticky="w", padx=5, pady=6)
            self.entries[key] = ent
            self.entry_labels[key] = label_text

        lbl_sec2 = ctk.CTkLabel(self.scroll_form, text="  II. SIGNALEMENT", font=("Arial", 12, "bold"), fg_color="#2c3e50", text_color="white", corner_radius=5, anchor="w")
        lbl_sec2.pack(fill="x", pady=(15, 10), ipady=5)

        f2 = ctk.CTkFrame(self.scroll_form, fg_color="transparent")
        f2.pack(fill="x", padx=5, pady=5)

        fields_part2 = [
            ("Taille / Corpulence", "taille_corpulence"), ("Signes particuliers", "signes_particuliers"),
            ("Langues parlées", "langues_accents"), ("N° de photographie au dossier", "num_photo_dossier")
        ]

        for i, (label_text, key) in enumerate(fields_part2):
            ctk.CTkLabel(f2, text=label_text + ":", font=("Arial", 11, "bold"), text_color="#333333").grid(row=i, column=0, sticky="w", padx=5, pady=6)
            ent = ctk.CTkEntry(f2, width=590, fg_color="white", text_color="black", border_color="#bdc3c7")
            ent.grid(row=i, column=1, sticky="w", padx=5, pady=6)
            self.entries[key] = ent
            self.entry_labels[key] = label_text

        lbl_sec3 = ctk.CTkLabel(self.scroll_form, text="  III. FAITS REPROCHÉS & PROCÉDURE", font=("Arial", 12, "bold"), fg_color="#2c3e50", text_color="white", corner_radius=5, anchor="w")
        lbl_sec3.pack(fill="x", pady=(15, 10), ipady=5)

        f3 = ctk.CTkFrame(self.scroll_form, fg_color="transparent")
        f3.pack(fill="x", padx=5, pady=5)

        fields_part3 = [
            ("Qualification pénale", "qualification_penale"), ("Catégorie", "categorie"),
            ("Sous-catégorie", "sous_categorie"), ("Date, Heure et Lieu des faits", "date_heure_lieu_faits"),
            ("Mode opératoire", "mode_operatoire"), ("Groupe / Co-auteurs", "groupe_organisation"),
            ("Armes / Objets saisis", "armes_objets"), ("Niveau de dangerosité", "niveau_dangerosite"),
            ("Statut procédural", "statut_procedural"), ("Interpellation (Date/Lieu)", "date_lieu_interpellation"),
            ("Lieu de détention", "lieu_detention")
        ]

        for i, (label_text, key) in enumerate(fields_part3):
            row = i // 2
            col = (i % 2) * 2
            ctk.CTkLabel(f3, text=label_text + ":", font=("Arial", 11, "bold"), text_color="#333333").grid(row=row, column=col, sticky="w", padx=5, pady=6)
            if key == "categorie":
                ent = ctk.CTkComboBox(f3, values=["Criminelle", "Subversive", "Autres"], width=230, fg_color="white", text_color="black")
                ent.set("")
            elif key == "niveau_dangerosite":
                ent = ctk.CTkComboBox(f3, values=["FAIBLE", "MOYEN", "ELEVÉ"], width=230, fg_color="white", text_color="black")
                ent.set("")
            elif key == "statut_procedural":
                ent = ctk.CTkComboBox(f3, values=["Recherche", "Interpellé", "Détenu", "Condamné", "Acquitté", "En fuite", "Classé"], width=230, fg_color="white", text_color="black")
                ent.set("")
            else:
                ent = ctk.CTkEntry(f3, width=230, fg_color="white", text_color="black", border_color="#bdc3c7")
            ent.grid(row=row, column=col+1, sticky="w", padx=5, pady=6)
            self.entries[key] = ent
            self.entry_labels[key] = label_text

        lbl_sec4 = ctk.CTkLabel(self.scroll_form, text="  IV. OBSERVATIONS", font=("Arial", 12, "bold"), fg_color="#2c3e50", text_color="white", corner_radius=5, anchor="w")
        lbl_sec4.pack(fill="x", pady=(15, 10), ipady=5)

        f4 = ctk.CTkFrame(self.scroll_form, fg_color="transparent")
        f4.pack(fill="x", padx=5, pady=5)
        self.text_obs = ctk.CTkTextbox(f4, width=850, height=100, fg_color="white", text_color="black", border_color="#bdc3c7", border_width=1)
        self.text_obs.pack(padx=5, pady=5)

        self.current_id = None

        action_bar = ctk.CTkFrame(self.tab_form, fg_color="transparent", corner_radius=8)
        action_bar.pack(fill="x", padx=5, pady=(0, 5))

        ctk.CTkButton(
            action_bar, text="VALIDER", fg_color="#27ae60", hover_color="#219653",
            font=("Arial", 12, "bold"), width=130, height=38,
            command=self.valider_fiche
        ).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(
            action_bar, text="MODIFIER", fg_color="#f39c12", hover_color="#d68910",
            font=("Arial", 12, "bold"), width=130, height=38,
            command=self.modifier_fiche_action
        ).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(
            action_bar, text="ANNULER", fg_color="#e74c3c", hover_color="#c0392b",
            font=("Arial", 12, "bold"), width=130, height=38,
            command=self.annuler_formulaire
        ).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(
            action_bar, text="IMPRIMER", fg_color="#2980b9", hover_color="#2471a3",
            font=("Arial", 12, "bold"), width=130, height=38,
            command=self.imprimer_fiche
        ).pack(side="left", padx=8, pady=8)

    def create_list_tab(self):
        self.add_background_canvas(self.tab_list)
        network_frame = ctk.CTkFrame(self.tab_list, fg_color="#ffffff", corner_radius=10)
        network_frame.pack(fill="x", padx=10, pady=(10, 0))
        ctk.CTkLabel(
            network_frame,
            text="Connexion au serveur MySQL (Tailscale) :",
            font=("Arial", 11, "bold"),
            text_color="#333333"
        ).pack(side="left", padx=(12, 6), pady=10)
        self.server_entry = ctk.CTkEntry(
            network_frame,
            width=150,
            placeholder_text="Adresse IP du serveur"
        )
        self.server_entry.pack(side="left", padx=5, pady=10)
        self.server_user_entry = ctk.CTkEntry(
            network_frame,
            width=130,
            placeholder_text="Utilisateur MySQL"
        )
        self.server_user_entry.pack(side="left", padx=5, pady=10)
        self.server_password_entry = ctk.CTkEntry(
            network_frame,
            width=130,
            placeholder_text="Mot de passe",
            show="*"
        )
        self.server_password_entry.pack(side="left", padx=5, pady=10)
        ctk.CTkButton(
            network_frame,
            text="CONNECTER",
            width=110,
            command=self.connecter_serveur
        ).pack(side="left", padx=5, pady=10)
        self.network_status = ctk.CTkLabel(
            network_frame,
            text="Mode local",
            text_color="#555555"
        )
        self.network_status.pack(side="left", padx=8, pady=10)

        search_frame = ctk.CTkFrame(self.tab_list, fg_color="#ffffff", corner_radius=10)
        search_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(search_frame, text="Recherche rapide :", font=("Arial", 12, "bold"), text_color="#333333").pack(side="left", padx=15, pady=15)
        self.search_entry = ctk.CTkEntry(search_frame, width=350, height=35, fg_color="white", text_color="black", border_color="#bdc3c7")
        self.search_entry.pack(side="left", padx=10, pady=15)

        ctk.CTkButton(search_frame, text="RECHERCHER", fg_color="#8e44ad", hover_color="#7d3c98", font=("Arial", 11, "bold"), width=120, height=35, command=self.rechercher_data).pack(side="left", padx=10, pady=15)
        ctk.CTkButton(search_frame, text="Actualiser", fg_color="#7f8c8d", hover_color="#707b7c", font=("Arial", 11, "bold"), width=100, height=35, command=self.load_data).pack(side="left", padx=5, pady=15)

        results_frame = ctk.CTkFrame(self.tab_list, fg_color="transparent")
        results_frame.pack(fill="both", expand=True, padx=10, pady=10)

        table_frame = ctk.CTkFrame(results_frame, fg_color="#ffffff", corner_radius=10)
        table_frame.pack(side="left", fill="both", expand=True)

        columns = ("ID", "Nom Complet", "Alias", "Sexe", "Nationalité", "Catégorie", "Statut", "Dangerosité")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.bind("<<TreeviewSelect>>", self.afficher_details_selection)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview.Heading", background="#1b2a47", foreground="white", font=("Arial", 10, "bold"))
        style.configure("Treeview", rowheight=25, font=("Arial", 10))

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=130, anchor="center")
        self.tree.column("ID", width=50, anchor="center")

        self.tree.pack(side="left", fill="both", expand=True, padx=10, pady=10)

        self.tab_details_name = "  Détails de la fiche  "
        self.tab_details = self.tabview.add(self.tab_details_name)
        self.add_background_canvas(self.tab_details)
        self.details_frame = ctk.CTkFrame(self.tab_details, fg_color="transparent", corner_radius=10)
        self.details_frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.details_title = ctk.CTkLabel(
            self.details_frame,
            text="Détails de la fiche",
            font=("Arial", 14, "bold"),
            text_color="#1b2a47"
        )
        self.details_title.pack(fill="x", padx=15, pady=(15, 8))
        self.details_alert_label = ctk.CTkLabel(
            self.details_frame,
            text="",
            height=0,
            corner_radius=6,
            font=("Arial", 13, "bold"),
            justify="left",
            anchor="w"
        )
        self.details_alert_label.pack(fill="x", padx=15)
        details_content = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        details_content.pack(fill="both", expand=True, padx=10, pady=5)
        photo_frame = ctk.CTkFrame(details_content, fg_color="#ecf0f1", corner_radius=8)
        photo_frame.pack(side="left", fill="y", padx=(0, 12), pady=5)
        self.details_photo_label = ctk.CTkLabel(
            photo_frame,
            text="Aucune photo",
            width=300,
            height=360,
            fg_color="#ecf0f1",
            text_color="#333333",
            corner_radius=5
        )
        self.details_photo_label.pack(padx=10, pady=10)
        self.details_scroll = ctk.CTkScrollableFrame(details_content, fg_color="transparent")
        self.details_scroll.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        self.details_photo_img = None
        self.current_detail_row = None
        self.afficher_details_vides()
        details_actions = ctk.CTkFrame(self.details_frame, fg_color="transparent")
        details_actions.pack(fill="x", padx=15, pady=(5, 12))
        ctk.CTkButton(
            details_actions,
            text="Imprimer cette fiche",
            command=self.imprimer_detail
        ).pack(side="left")
        ctk.CTkButton(
            details_actions,
            text="Liste des alertes",
            command=self.ouvrir_liste_alertes
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            details_actions,
            text="Résultats de recherche",
            command=self.ouvrir_resultats_recherche
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            details_actions,
            text="Retour à la liste",
            command=lambda: self.tabview.set(self.tab_list_name)
        ).pack(side="right")

        actions_frame = ctk.CTkFrame(self.tab_list, fg_color="transparent")
        actions_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkButton(
            actions_frame,
            text="Consulter les alertes",
            fg_color="#c0392b",
            hover_color="#922b21",
            command=self.ouvrir_liste_alertes
        ).pack(side="left", padx=5)

        if self.current_user["role"] == "Admin":
            ctk.CTkButton(
                actions_frame,
                text="Gérer les utilisateurs",
                fg_color="#34495e",
                hover_color="#2c3e50",
                font=("Arial", 11, "bold"),
                width=180,
                height=35,
                command=self.gerer_utilisateurs
            ).pack(side="right", padx=5)
            ctk.CTkButton(actions_frame, text="Charger pour Modification", fg_color="#f39c12", hover_color="#d68910", font=("Arial", 11, "bold"), width=180, height=35, command=self.edit_selected).pack(side="left", padx=5)
            ctk.CTkButton(actions_frame, text="Supprimer la fiche", fg_color="#c0392b", hover_color="#922b21", font=("Arial", 11, "bold"), width=150, height=35, command=self.delete_selected).pack(side="left", padx=5)
        ctk.CTkLabel(
            actions_frame,
            text=f"Connecté : {self.current_user['username']} ({self.current_user['role']})",
            text_color="#555555"
        ).pack(side="right", padx=8)

    def gerer_utilisateurs(self):
        if self.current_user["role"] != "Admin":
            messagebox.showerror("Accès refusé", "Seul un Admin peut gérer les utilisateurs.")
            return
        UserManagementDialog(self, self.auth_store, self.current_user["username"])

    def connecter_serveur(self):
        host = self.server_entry.get().strip()
        username = self.server_user_entry.get().strip()
        password = self.server_password_entry.get()
        if not host or not username:
            messagebox.showwarning(
                "Connexion réseau",
                "Saisissez l'adresse Tailscale du serveur et le compte MySQL partagé."
            )
            return

        previous_config = DB_CONFIG.copy()
        DB_CONFIG.update(host=host, user=username, password=password)
        conn = None
        try:
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM fiches LIMIT 0")
            self.remote_mode = True
            self.network_status.configure(
                text=f"Connecté à {host} (ajout/modification, sans suppression)",
                text_color="#218838"
            )
            self.load_data()
        except Exception as e:
            DB_CONFIG.clear()
            DB_CONFIG.update(previous_config)
            self.remote_mode = previous_config["host"] != "localhost"
            messagebox.showerror("Connexion réseau impossible", f"Vérifiez l'adresse, les identifiants et les droits MySQL.\n\nDétail : {e}")
        finally:
            if conn is not None:
                conn.close()
            self.server_password_entry.delete(0, "end")

    def charger_photo(self):
        file_path = filedialog.askopenfilename(title="Sélectionner une photo", filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp")])
        if file_path:
            self.photo_path_val = file_path
            self.afficher_image(file_path)

    def afficher_image(self, path):
        try:
            from PIL import Image, ImageTk

            img = Image.open(path).resize((95, 120), Image.Resampling.LANCZOS)
            self.photo_img = ImageTk.PhotoImage(img)
            self.photo_label.configure(image=self.photo_img, text="")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger l'image : {e}")

    def load_data(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.afficher_details_vides()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, nom_complet, alias_surnom, sexe, nationalite, categorie, statut_procedural, niveau_dangerosite FROM fiches")
            for row in cursor.fetchall():
                self.tree.insert("", "end", values=(row['id'], row['nom_complet'], row['alias_surnom'], row['sexe'], row['nationalite'], row['categorie'], row['statut_procedural'], row['niveau_dangerosite']))
            conn.close()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de charger les fiches : {e}")

    def rechercher_data(self):
        query = self.search_entry.get()
        self.last_search_query = query
        for row in self.tree.get_children():
            self.tree.delete(row)
        self.afficher_details_vides()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            sql = "SELECT id, nom_complet, alias_surnom, sexe, nationalite, categorie, statut_procedural, niveau_dangerosite FROM fiches WHERE nom_complet LIKE %s OR alias_surnom LIKE %s"
            cursor.execute(sql, ('%' + query + '%', '%' + query + '%'))
            rows = cursor.fetchall()
            self.last_search_rows = rows
            for row in rows:
                self.tree.insert("", "end", values=(row['id'], row['nom_complet'], row['alias_surnom'], row['sexe'], row['nationalite'], row['categorie'], row['statut_procedural'], row['niveau_dangerosite']))
            conn.close()
            results = self.tree.get_children()
            if results:
                self.tree.selection_set(results[0])
                self.tree.focus(results[0])
            else:
                self.afficher_details_vides("Aucune fiche correspondante.")

            alerts = []
            for row in rows:
                alert_reasons = get_alert_reasons(row)
                if alert_reasons:
                    name = row.get("nom_complet") or "Nom non renseigné"
                    alerts.append(f"• {name} — {', '.join(alert_reasons)}")

            if alerts:
                messagebox.showwarning(
                    "Alertes sur les résultats",
                    "Attention : les fiches suivantes correspondent aux critères d'alerte :\n\n"
                    + "\n".join(alerts)
                )
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la recherche : {e}")

    def ouvrir_resultats_recherche(self):
        rows = getattr(self, "last_search_rows", None)
        if rows is None:
            messagebox.showinfo(
                "Résultats de recherche",
                "Effectuez d'abord une recherche.",
                parent=self
            )
            return
        if not rows:
            messagebox.showinfo(
                "Résultats de recherche",
                "Aucun résultat à afficher pour cette recherche.",
                parent=self
            )
            return

        window = ctk.CTkToplevel(self)
        window.title("Résultats de la recherche")
        window.geometry("1050x600")
        window.transient(self)

        query = getattr(self, "last_search_query", "").strip()
        ctk.CTkLabel(
            window,
            text=f"Résultats de recherche : {query or 'Toutes les fiches'}",
            font=("Arial", 17, "bold")
        ).pack(anchor="w", padx=18, pady=(16, 8))

        columns = (
            "id", "nom", "alias", "sexe", "nationalite",
            "categorie", "statut", "danger"
        )
        headings = {
            "id": "N°",
            "nom": "Nom complet",
            "alias": "Alias",
            "sexe": "Sexe",
            "nationalite": "Nationalité",
            "categorie": "Catégorie",
            "statut": "Statut",
            "danger": "Dangerosité",
        }
        widths = {
            "id": 55, "nom": 200, "alias": 130, "sexe": 80,
            "nationalite": 120, "categorie": 120, "statut": 130, "danger": 120
        }
        results_tree = ttk.Treeview(
            window, columns=columns, show="headings", selectmode="browse"
        )
        for column in columns:
            results_tree.heading(column, text=headings[column])
            results_tree.column(column, width=widths[column], anchor="center")

        result_items = {}
        for row in rows:
            item = results_tree.insert(
                "",
                "end",
                values=(
                    row.get("id", ""),
                    row.get("nom_complet") or "Nom non renseigné",
                    row.get("alias_surnom") or "",
                    row.get("sexe") or "",
                    row.get("nationalite") or "",
                    row.get("categorie") or "",
                    row.get("statut_procedural") or "",
                    row.get("niveau_dangerosite") or "",
                )
            )
            result_items[item] = row.get("id")
        results_tree.pack(fill="both", expand=True, padx=18, pady=8)

        ctk.CTkLabel(window, text=f"{len(rows)} résultat(s)").pack(
            anchor="w", padx=18, pady=4
        )

        def afficher_resultat_selectionne(_event=None):
            selected = results_tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Sélection requise",
                    "Sélectionnez un résultat.",
                    parent=window
                )
                return
            fiche_id = result_items[selected[0]]
            matching_item = next(
                (
                    item
                    for item in self.tree.get_children()
                    if str(self.tree.item(item, "values")[0]) == str(fiche_id)
                ),
                None
            )
            if matching_item is None:
                messagebox.showerror(
                    "Fiche introuvable",
                    "Cette fiche n'est plus présente dans les résultats.",
                    parent=window
                )
                return
            self.tree.selection_set(matching_item)
            self.tree.focus(matching_item)
            window.destroy()

        def imprimer_resultats():
            table_rows = []
            for row in rows:
                values = (
                    str(row.get("id", "")),
                    row.get("nom_complet") or "Nom non renseigné",
                    row.get("alias_surnom") or "",
                    row.get("sexe") or "",
                    row.get("nationalite") or "",
                    row.get("categorie") or "",
                    row.get("statut_procedural") or "",
                    row.get("niveau_dangerosite") or "",
                )
                table_rows.append(
                    "<tr>"
                    + "".join(
                        f"<td>{html.escape(str(value))}</td>" for value in values
                    )
                    + "</tr>"
                )
            report_html = (
                "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
                "<title>Résultats de recherche</title><style>"
                "body{font-family:Arial,sans-serif;margin:20px}"
                "table{border-collapse:collapse;width:100%;font-size:10pt}"
                "th,td{text-align:left;padding:6px;border:1px solid #bbb}"
                "th{background:#eee}"
                "</style></head><body><h1>Résultats de recherche</h1><p>"
                + html.escape(query or "Toutes les fiches")
                + "</p><table><thead><tr>"
                + "".join(f"<th>{html.escape(headings[key])}</th>" for key in columns)
                + "</tr></thead><tbody>"
                + "".join(table_rows)
                + "</tbody></table></body></html>"
            )
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".html", mode="w", encoding="utf-8"
                ) as temp_file:
                    temp_file.write(report_html)
                os.startfile(temp_file.name)
                messagebox.showinfo(
                    "Aperçu d'impression",
                    "Les résultats sont ouverts dans votre navigateur. "
                    "Utilisez Ctrl+P pour lancer l'impression.",
                    parent=window
                )
            except OSError as e:
                messagebox.showerror(
                    "Aperçu impossible",
                    f"Impossible d'ouvrir les résultats : {e}",
                    parent=window
                )

        results_tree.bind("<Double-1>", afficher_resultat_selectionne)
        actions = ctk.CTkFrame(window, fg_color="transparent")
        actions.pack(fill="x", padx=18, pady=(4, 14))
        ctk.CTkButton(
            actions,
            text="Imprimer les résultats",
            command=imprimer_resultats
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="Afficher la fiche sélectionnée",
            command=afficher_resultat_selectionne
        ).pack(side="right")

    def afficher_details_vides(self, message="Sélectionnez un résultat pour afficher la photo et toutes les informations."):
        if not hasattr(self, "details_scroll"):
            return
        for widget in self.details_scroll.winfo_children():
            widget.destroy()
        self.details_title.configure(text="Détails de la fiche")
        if hasattr(self, "details_alert_label"):
            self.details_alert_label.configure(
                text="",
                height=0,
                fg_color="transparent",
                text_color="#333333"
            )
        self.details_photo_img = None
        self.current_detail_row = None
        self.details_photo_label.configure(image="", text="Aucune photo")
        ctk.CTkLabel(
            self.details_scroll,
            text=message,
            wraplength=700,
            justify="left",
            text_color="#555555"
        ).pack(anchor="w", padx=8, pady=8)

    def afficher_details_selection(self, *_):
        selected_item = self.tree.selection()
        if not selected_item:
            self.afficher_details_vides()
            return

        fiche_id = self.tree.item(selected_item[0])["values"][0]
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fiches WHERE id = %s", (fiche_id,))
            row = cursor.fetchone()
            if not row:
                self.afficher_details_vides()
                return

            self.details_title.configure(text=row.get("nom_complet") or "Détails de la fiche")
            self.current_detail_row = row
            alert_reasons = get_alert_reasons(row)
            if alert_reasons:
                self.details_alert_label.configure(
                    text=f"⚠ ALERTE : {', '.join(alert_reasons)}",
                    height=42,
                    fg_color="#fdecea",
                    text_color="#c0392b"
                )
                self.bell()
            else:
                self.details_alert_label.configure(
                    text="",
                    height=0,
                    fg_color="transparent",
                    text_color="#333333"
                )
            for widget in self.details_scroll.winfo_children():
                widget.destroy()

            photo_path = row.get("photo_path")
            self.details_photo_img = None
            if photo_path and os.path.isfile(photo_path):
                try:
                    from PIL import Image, ImageTk

                    image = Image.open(photo_path)
                    image.thumbnail((300, 360), Image.Resampling.LANCZOS)
                    self.details_photo_img = ImageTk.PhotoImage(image)
                    self.details_photo_label.configure(image=self.details_photo_img, text="")
                except (OSError, ValueError) as e:
                    self.details_photo_label.configure(image="", text="Photo illisible")
                    messagebox.showwarning("Photo indisponible", f"Impossible d'afficher la photo : {e}")
            else:
                self.details_photo_label.configure(image="", text="Photo non disponible")

            for key, value in row.items():
                if key == "photo_path":
                    continue
                label = getattr(self, "entry_labels", {}).get(
                    key, key.replace("_", " ").capitalize()
                )
                if key == "id":
                    label = "N° de fiche"
                elif key == "observations":
                    label = "Observations"
                display_value = str(value).strip() if value is not None else ""
                if not display_value:
                    display_value = "Non renseigné"
                ctk.CTkLabel(
                    self.details_scroll,
                    text=f"{label} : {display_value}",
                    wraplength=700,
                    justify="left",
                    anchor="w",
                    text_color="#333333"
                ).pack(fill="x", anchor="w", padx=8, pady=5)
            self.tabview.set(self.tab_details_name)
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible d'afficher les détails de la fiche : {e}")
        finally:
            if conn is not None:
                conn.close()

    def imprimer_detail(self):
        if self.current_detail_row is None:
            messagebox.showwarning(
                "Impression",
                "Sélectionnez d'abord une fiche à imprimer.",
                parent=self
            )
            return

        row = self.current_detail_row
        image_html = ""
        photo_path = row.get("photo_path")
        if photo_path and os.path.isfile(photo_path):
            image_uri = Path(photo_path).resolve().as_uri()
            image_html = (
                f'<img class="photo" src="{html.escape(image_uri, quote=True)}" '
                'alt="Photo de la personne">'
            )

        details = []
        for key, value in row.items():
            if key == "photo_path":
                continue
            label = getattr(self, "entry_labels", {}).get(
                key, key.replace("_", " ").capitalize()
            )
            if key == "id":
                label = "N° de fiche"
            elif key == "observations":
                label = "Observations"
            display_value = str(value).strip() if value is not None else ""
            details.append(
                "<tr><th>"
                + html.escape(label)
                + "</th><td>"
                + html.escape(display_value or "Non renseigné")
                + "</td></tr>"
            )

        try:
            watermark_path = Path(__file__).with_name(
                "democratic-republic-of-congo-coat-of-arms-vector-24327882.webp"
            )
            watermark_data = watermark_path.read_bytes()
        except OSError as e:
            messagebox.showerror(
                "Fond de page indisponible",
                f"Impossible de charger l'emblème pour l'impression : {e}",
                parent=self
            )
            return
        watermark_html = (
            '<img class="watermark" src="data:'
            + html.escape(mimetypes.guess_type(watermark_path.name)[0] or "image/webp")
            + ";base64,"
            + base64.b64encode(watermark_data).decode("ascii")
            + '" alt="">'
        )
        content = (
            "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
            "<title>Fiche de renseignement</title><style>"
            "body{font-family:Arial,sans-serif;margin:24px;color:#222;position:relative}"
            ".watermark{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);"
            "width:150mm;height:150mm;object-fit:contain;opacity:.16;z-index:-1}"
            "h1{font-size:20px;color:#1b2a47}"
            ".photo{float:right;max-width:220px;max-height:270px;object-fit:contain;"
            "margin:0 0 16px 20px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{text-align:left;vertical-align:top;padding:7px;border-bottom:1px solid #ccc}"
            "th{width:32%;color:#1b2a47}@media print{body{margin:12mm}}"
            "</style></head><body>"
            + watermark_html
            + "<h1>FICHE INDIVIDUELLE DE RENSEIGNEMENT</h1>"
            + image_html
            + "<table>"
            + "".join(details)
            + "</table></body></html>"
        )
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".html", mode="w", encoding="utf-8"
            ) as temp_file:
                temp_file.write(content)
            os.startfile(temp_file.name)
            messagebox.showinfo(
                "Aperçu d'impression",
                "La fiche est ouverte dans votre navigateur. "
                "Utilisez Ctrl+P pour lancer l'impression.",
                parent=self
            )
        except OSError as e:
            messagebox.showerror(
                "Aperçu impossible",
                f"Impossible d'ouvrir la fiche : {e}",
                parent=self
            )

    def ouvrir_liste_alertes(self):
        conn = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, nom_complet, statut_procedural, niveau_dangerosite "
                "FROM fiches ORDER BY nom_complet"
            )
            records = [
                (row, get_alert_reasons(row))
                for row in cursor.fetchall()
            ]
        except Exception as e:
            messagebox.showerror(
                "Liste des alertes",
                f"Impossible de charger les fiches : {e}",
                parent=self
            )
            return
        finally:
            if conn is not None:
                conn.close()

        if not any(reasons for _, reasons in records):
            messagebox.showinfo(
                "Liste des alertes",
                "Aucune fiche ne correspond actuellement aux critères d'alerte.",
                parent=self
            )
            return

        window = ctk.CTkToplevel(self)
        window.title("Personnes enregistrées avec alerte")
        window.geometry("950x560")
        window.transient(self)

        ctk.CTkLabel(
            window,
            text="Fiches correspondant aux critères d'alerte",
            font=("Arial", 17, "bold")
        ).pack(anchor="w", padx=18, pady=(16, 8))

        filters = ["Toutes les alertes"] + sorted(
            {reason for _, reasons in records for reason in reasons}
        )
        filter_combo = ctk.CTkComboBox(window, values=filters, width=260)
        filter_combo.set(filters[0])
        filter_combo.pack(anchor="w", padx=18, pady=(0, 10))

        columns = ("id", "nom", "statut", "danger", "criteres")
        alert_tree = ttk.Treeview(
            window, columns=columns, show="headings", selectmode="browse"
        )
        headings = {
            "id": "N°",
            "nom": "Nom complet",
            "statut": "Statut procédural",
            "danger": "Dangerosité",
            "criteres": "Critères d'alerte",
        }
        widths = {"id": 55, "nom": 220, "statut": 150, "danger": 130, "criteres": 300}
        for column in columns:
            alert_tree.heading(column, text=headings[column])
            alert_tree.column(column, width=widths[column], anchor="w")
        alert_tree.pack(fill="both", expand=True, padx=18, pady=5)

        count_label = ctk.CTkLabel(window, text="")
        count_label.pack(anchor="w", padx=18, pady=5)

        visible_records = []

        def refresh_alert_rows(_event=None):
            nonlocal visible_records
            selected_filter = filter_combo.get()
            for item in alert_tree.get_children():
                alert_tree.delete(item)
            visible_records = [
                (row, reasons)
                for row, reasons in records
                if reasons
                and (
                    selected_filter == "Toutes les alertes"
                    or selected_filter in reasons
                )
            ]
            for row, reasons in visible_records:
                alert_tree.insert(
                    "",
                    "end",
                    values=(
                        row["id"],
                        row.get("nom_complet") or "Nom non renseigné",
                        row.get("statut_procedural") or "Non renseigné",
                        row.get("niveau_dangerosite") or "Non renseigné",
                        ", ".join(reasons),
                    )
                )
            count_label.configure(text=f"{len(visible_records)} fiche(s)")

        def imprimer_liste_alertes():
            if not visible_records:
                messagebox.showinfo(
                    "Impression",
                    "Aucune fiche à imprimer pour ce critère.",
                    parent=window
                )
                return
            table_rows = []
            for row, reasons in visible_records:
                values = (
                    row.get("nom_complet") or "Nom non renseigné",
                    row.get("statut_procedural") or "Non renseigné",
                    row.get("niveau_dangerosite") or "Non renseigné",
                    ", ".join(reasons),
                )
                table_rows.append(
                    "<tr>"
                    + "".join(f"<td>{html.escape(value)}</td>" for value in values)
                    + "</tr>"
                )
            report_html = (
                "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
                "<title>Liste des fiches en alerte</title><style>"
                "body{font-family:Arial,sans-serif;margin:20px}"
                "table{border-collapse:collapse;width:100%}"
                "th,td{text-align:left;padding:7px;border:1px solid #bbb}"
                "th{background:#eee}"
                "</style></head><body><h1>Fiches correspondant aux critères d'alerte</h1>"
                "<table><thead><tr><th>Nom complet</th><th>Statut</th>"
                "<th>Dangerosité</th><th>Critères d'alerte</th></tr></thead><tbody>"
                + "".join(table_rows)
                + "</tbody></table></body></html>"
            )
            try:
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".html", mode="w", encoding="utf-8"
                ) as temp_file:
                    temp_file.write(report_html)
                os.startfile(temp_file.name)
                messagebox.showinfo(
                    "Aperçu d'impression",
                    "La liste est ouverte dans votre navigateur. "
                    "Utilisez Ctrl+P pour lancer l'impression.",
                    parent=window
                )
            except OSError as e:
                messagebox.showerror(
                    "Aperçu impossible",
                    f"Impossible d'ouvrir la liste : {e}",
                    parent=window
                )

        def afficher_fiche_selectionnee(_event=None):
            selected = alert_tree.selection()
            if not selected:
                messagebox.showwarning(
                    "Sélection requise",
                    "Sélectionnez une fiche dans la liste.",
                    parent=window
                )
                return
            fiche_id = alert_tree.item(selected[0], "values")[0]
            matching_item = next(
                (
                    item
                    for item in self.tree.get_children()
                    if str(self.tree.item(item, "values")[0]) == str(fiche_id)
                ),
                None
            )
            if matching_item is None:
                self.load_data()
                matching_item = next(
                    (
                        item
                        for item in self.tree.get_children()
                        if str(self.tree.item(item, "values")[0]) == str(fiche_id)
                    ),
                    None
                )
            if matching_item is None:
                messagebox.showerror(
                    "Fiche introuvable",
                    "Cette fiche n'est plus disponible dans la liste.",
                    parent=window
                )
                return
            self.tree.selection_set(matching_item)
            self.tree.focus(matching_item)
            window.destroy()

        filter_combo.bind("<<ComboboxSelected>>", refresh_alert_rows)
        alert_tree.bind("<Double-1>", afficher_fiche_selectionnee)
        refresh_alert_rows()
        alert_actions = ctk.CTkFrame(window, fg_color="transparent")
        alert_actions.pack(fill="x", padx=18, pady=(5, 15))
        ctk.CTkButton(
            alert_actions,
            text="Imprimer cette liste",
            command=imprimer_liste_alertes
        ).pack(side="left")
        ctk.CTkButton(
            alert_actions,
            text="Afficher la fiche sélectionnée",
            command=afficher_fiche_selectionnee
        ).pack(side="right")

    def valider_fiche(self):
        if self.current_user["role"] != "Admin":
            messagebox.showwarning(
                "Accès refusé",
                "L'ajout et la modification des fiches sont réservés à l'Admin."
            )
            return
        try:
            data = {key: ent.get() for key, ent in self.entries.items()}
            data["photo_path"] = self.photo_path_val
            data["observations"] = self.text_obs.get("1.0", "end-1c").strip()

            if not data["nom_complet"] or data["nom_complet"].strip() == "":
                messagebox.showerror("Erreur", "Le champ 'Nom, Post-nom & Prénom' est obligatoire.")
                return

            conn = get_db_connection()
            cursor = conn.cursor()

            if self.current_id is None:
                keys = list(data.keys())
                values = list(data.values())
                placeholders = ", ".join(["%s"] * len(keys))
                sql = f"INSERT INTO fiches ({', '.join(keys)}) VALUES ({placeholders})"
                cursor.execute(sql, values)
                fiche_id = cursor.lastrowid
            else:
                fiche_id = self.current_id
                set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
                values = list(data.values()) + [self.current_id]
                sql = f"UPDATE fiches SET {set_clause} WHERE id = %s"
                cursor.execute(sql, values)

            conn.commit()
            pdf_path = None
            pdf_error = None
            try:
                pdf_path = exporter_fiche_pdf(data, self.entry_labels, fiche_id)
            except Exception as e:
                pdf_error = e

            excel_path = None
            excel_error = None
            try:
                excel_path = exporter_fiches_excel(conn)
            except Exception as e:
                excel_error = e
            
            conn.close()
            self.current_id = None
            self.annuler_formulaire()
            self.load_data()
            self.tabview.set("  Base de Données & Consultation  ")
            if pdf_error is not None or excel_error is not None:
                details = ["La fiche est bien enregistrée dans MySQL."]
                if pdf_error is None:
                    details.append(f"PDF créé : {pdf_path}")
                else:
                    details.append(f"PDF non créé : {pdf_error}")
                if excel_error is None:
                    details.append(f"Export Excel créé : {excel_path}")
                else:
                    details.append(f"Export Excel non créé : {excel_error}")
                messagebox.showwarning(
                    "Validation effectuée avec avertissement",
                    "\n".join(details),
                    parent=self
                )
            else:
                messagebox.showinfo(
                    "Succès",
                    "Fiche enregistrée dans MySQL.\n"
                    f"PDF : {pdf_path}\n"
                    f"Export Excel : {excel_path}",
                    parent=self
                )
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la validation : {e}")

    def modifier_fiche_action(self):
        if self.current_user["role"] != "Admin":
            messagebox.showwarning("Accès refusé", "La modification est réservée à l'Admin.")
            return
        if self.current_id is None:
            messagebox.showwarning("Attention", "Sélectionnez d'abord une fiche à modifier.")
            return
        self.valider_fiche()

    def annuler_formulaire(self):
        for key, ent in self.entries.items():
            if isinstance(ent, ctk.CTkComboBox): ent.set("")
            else: ent.delete(0, "end")
        self.text_obs.delete("1.0", "end")
        self.photo_path_val = ""
        self.photo_label.configure(image="", text="Aucune\nphoto")
        self.current_id = None

    def imprimer_fiche(self):
        data = {key: ent.get() for key, ent in self.entries.items()}
        data["observations"] = self.text_obs.get("1.0", "end-1c").strip()
        if not data["nom_complet"]:
            messagebox.showwarning("Attention", "Renseignez au moins le nom.")
            return

        photo_html = '<p class="no-photo">Aucune photo enregistrée</p>'
        if self.photo_path_val and os.path.isfile(self.photo_path_val):
            mime_type = mimetypes.guess_type(self.photo_path_val)[0] or "image/jpeg"
            try:
                with open(self.photo_path_val, "rb") as photo_file:
                    photo_data = base64.b64encode(photo_file.read()).decode("ascii")
            except OSError as e:
                messagebox.showerror(
                    "Photo indisponible",
                    f"Impossible de lire la photo sélectionnée : {e}",
                    parent=self
                )
                return
            photo_html = (
                f'<img class="photo" src="data:{html.escape(mime_type)};base64,'
                f'{photo_data}" '
                'alt="Photo de la personne">'
            )
        elif self.photo_path_val:
            photo_html = '<p class="no-photo">Photo introuvable</p>'

        field_sections = [
            ("Identité de la personne", [
                "nom_complet", "alias_surnom", "sexe", "date_lieu_naissance",
                "nationalite", "piece_identite", "domicile_habituel",
                "residence_actuelle", "profession_activite", "situation_familiale",
                "personne_a_prevenir", "telephone",
            ]),
            ("Signalement", [
                "taille_corpulence", "signes_particuliers", "langues_accents",
                "num_photo_dossier",
            ]),
            ("Faits et procédure", [
                "qualification_penale", "categorie", "sous_categorie",
                "date_heure_lieu_faits", "mode_operatoire", "groupe_organisation",
                "armes_objets", "niveau_dangerosite", "statut_procedural",
                "date_lieu_interpellation", "lieu_detention",
            ]),
        ]
        def make_table(keys):
            rows_html = []
            for key in keys:
                label = self.entry_labels.get(key, key.replace("_", " ").capitalize())
                value = data.get(key, "").strip() or "Non renseigné"
                rows_html.append(
                    "<tr><th>"
                    + html.escape(label)
                    + "</th><td>"
                    + html.escape(value)
                    + "</td></tr>"
                )
            return "<table>" + "".join(rows_html) + "</table>"

        identity_html = make_table(field_sections[0][1])
        signalement_html = (
            "<h2>Signalement</h2>"
            + make_table(field_sections[1][1])
        )
        facts_html = make_table(field_sections[2][1])
        observations = data["observations"] or "Non renseigné"
        observations_html = (
            "<section class=\"observations-section\"><h2>Observations</h2>"
            "<p class=\"observations\">"
            + html.escape(observations)
            + "</p></section>"
        )
        alert_reasons = get_alert_reasons(data)
        alert_html = ""
        if alert_reasons:
            alert_html = (
                '<div class="alert-banner"><strong>⚠ ALERTE</strong> — '
                + html.escape(", ".join(alert_reasons))
                + "</div>"
            )
        try:
            watermark_path = Path(__file__).with_name(
                "democratic-republic-of-congo-coat-of-arms-vector-24327882.webp"
            )
            watermark_data = watermark_path.read_bytes()
        except OSError as e:
            messagebox.showerror(
                "Fond de page indisponible",
                f"Impossible de charger l'image d'arrière-plan : {e}",
                parent=self
            )
            return
        watermark_html = (
            '<img class="watermark" src="data:'
            + html.escape(mimetypes.guess_type(watermark_path.name)[0] or "image/webp")
            + ";base64,"
            + base64.b64encode(watermark_data).decode("ascii")
            + '" alt="">'
        )
        content = (
            "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
            "<title>Fiche individuelle de renseignement</title><style>"
            "*{box-sizing:border-box}"
            "body{font-family:Arial,sans-serif;color:#263445;margin:0;line-height:1.3;"
            "background:#eef1f5}"
            ".page{position:relative;isolation:isolate;width:190mm;height:277mm;"
            "margin:0 auto;background:#fff;padding:6mm;border:1px solid #d5dce5;"
            "display:flex;flex-direction:column}"
            ".watermark{position:absolute;width:150mm;height:150mm;object-fit:contain;"
            "top:50%;left:50%;transform:translate(-50%,-50%);opacity:.16;"
            "z-index:0;pointer-events:none}"
            ".page>*:not(.watermark){position:relative;z-index:1}"
            ".heading{display:flex;flex-direction:row;align-items:center;text-align:center;"
            "border-bottom:2px solid #1b2a47;padding-bottom:4mm;margin-bottom:5mm}"
            ".heading>div{flex:1;text-align:center}"
            "h1{color:#1b2a47;font-size:17px;font-weight:700;letter-spacing:1px;margin:2mm 0 0}"
            ".subtitle{font-size:9px;color:#66758a;margin-top:2px}"
            ".alert-banner{font-size:10px;font-weight:bold;text-align:center;"
            "color:#9e2b24;background:#fff0ed;border:1px solid #e8b4ad;"
            "border-radius:3px;padding:2.5mm;margin:0 0 3mm}"
            ".photo{width:34mm;height:40mm;object-fit:contain;border:1px solid #c6ced8;"
            "border-radius:3px;padding:2px;margin:0 6mm 0 0}"
            ".no-photo{width:34mm;height:25mm;border:1px solid #c6ced8;padding:5px;"
            "text-align:center;color:#66758a;font-size:8px;margin:0 6mm 0 0}"
            ".columns{display:grid;grid-template-columns:1fr 1fr;gap:6mm;flex:1;"
            "align-content:space-between}"
            ".column{display:flex;flex-direction:column;justify-content:flex-start;"
            "gap:3mm;min-width:0}"
            ".column>div{width:100%}.full-width{grid-column:1 / -1}"
            "h2{font-size:10px;font-weight:700;color:#fff;text-align:center;letter-spacing:.3px;"
            "background:#1b2a47;margin:5mm 0 2mm;padding:2.5mm 3mm;border-radius:3px}"
            "table{border-collapse:collapse;width:100%;margin-bottom:3mm;table-layout:fixed;"
            "border:1px solid #d9e0e8}"
            "th,td{text-align:center;vertical-align:middle;padding:2mm 1.5mm;"
            "border-bottom:1px solid #d9e0e8;font-size:8.5px;overflow-wrap:anywhere}"
            "th{width:40%;color:#34445a;background:#f1f4f8;font-weight:600}"
            "tr:nth-child(even) td{background:#fbfcfd}"
            ".observations{white-space:pre-wrap;text-align:center;border:1px solid #d9e0e8;"
            "border-radius:3px;padding:4mm;font-size:8.5px;font-weight:700;margin:0;"
            "overflow-wrap:anywhere;background:#fbfcfd}"
            ".observations-section{margin-top:3mm}"
            "@page{size:A4 portrait;margin:8mm}"
            "@media print{body{margin:0;font-size:9pt;background:#fff}.page{width:190mm;"
            "height:277mm;margin:0 auto;padding:5mm;border:1px solid #cbd3dd;"
            "overflow:visible}.heading{padding-bottom:3mm;margin-bottom:3mm}"
            "h1{font-size:14pt;font-weight:700}.subtitle{font-size:8pt}"
            ".alert-banner{font-size:8pt;padding:2mm;margin-bottom:2mm}"
            ".photo{width:30mm;height:36mm;margin-right:5mm}"
            ".no-photo{width:30mm;height:22mm;margin-right:5mm}"
            ".columns{gap:5mm;grid-template-columns:1fr 1fr;grid-template-rows:1fr}"
            "h2{font-size:8pt;font-weight:700;margin:3mm 0 1.5mm;padding:1.8mm 2mm}"
            "table{margin-bottom:2mm}th,td{font-size:7.5pt;padding:1.2mm 1mm;"
            "line-height:1.15}tr{break-inside:avoid}"
            ".observations{font-size:7.5pt;padding:3mm;min-height:28mm;flex:none}}"
            "</style><script>"
            "window.addEventListener('load',function(){"
            "var page=document.querySelector('.page');"
            "var fitAndPrint=function(){"
            "var width=page.scrollWidth;var height=page.scrollHeight;"
            "var availableWidth=190*96/25.4;var availableHeight=277*96/25.4;"
            "page.style.zoom=Math.min(1,availableWidth/width,availableHeight/height);"
            "window.setTimeout(function(){window.print();},400);};"
            "if(document.fonts&&document.fonts.ready){"
            "document.fonts.ready.then(fitAndPrint);}else{fitAndPrint();}"
            "});"
            "</script></head><body><main class=\"page\">"
            + watermark_html
            +
            "<header class=\"heading\">"
            + photo_html
            + "<div><h1>FICHE INDIVIDUELLE DE RENSEIGNEMENT</h1>"
            "<div class=\"subtitle\">ANR — Fiche de renseignement</div></div>"
            + "</header>"
            + alert_html
            + "<div class=\"columns\"><section class=\"column\">"
            + "<div><h2>Identité de la personne</h2>"
            + identity_html
            + "</div><div>"
            + signalement_html
            + "</div>"
            + observations_html
            + "</section><section class=\"column\">"
            + '<div><h2>Faits et procédure</h2>'
            + facts_html
            + "</div></section></div></main></body></html>"
        )
        try:
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=".html", mode="w", encoding="utf-8"
            ) as temp_file:
                temp_file.write(content)
            os.startfile(temp_file.name)
        except OSError as e:
            messagebox.showerror(
                "Impression impossible",
                f"Impossible d'ouvrir la fiche pour impression : {e}",
                parent=self
            )

    def edit_selected(self):
        if self.current_user["role"] != "Admin":
            messagebox.showwarning("Accès refusé", "La modification est réservée à l'Admin.")
            return
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Attention", "Sélectionnez une fiche.")
            return
        self.current_id = self.tree.item(selected_item)['values'][0]
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM fiches WHERE id = %s", (self.current_id,))
            row = cursor.fetchone()
            conn.close()
            if row:
                self.photo_path_val = row['photo_path'] if row['photo_path'] else ""
                if self.photo_path_val and os.path.exists(self.photo_path_val):
                    self.afficher_image(self.photo_path_val)
                for key in self.entries.keys():
                    if key in row:
                        val = row[key]
                        ent = self.entries[key]
                        if isinstance(ent, ctk.CTkComboBox): ent.set(val if val else "")
                        else:
                            ent.delete(0, "end")
                            ent.insert(0, val if val else "")
                self.text_obs.delete("1.0", "end")
                self.text_obs.insert("1.0", row['observations'] if row['observations'] else "")
                self.tabview.set("  Saisie & Édition de Fiche  ")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur : {e}")

    def delete_selected(self):
        if self.current_user["role"] != "Admin" or self.remote_mode:
            messagebox.showwarning(
                "Suppression indisponible",
                "La suppression des fiches est réservée à l'Admin en mode local."
            )
            return
        selected_item = self.tree.selection()
        if not selected_item:
            messagebox.showwarning("Attention", "Sélectionnez une fiche à supprimer.")
            return
        item_id = self.tree.item(selected_item)['values'][0]
        if messagebox.askyesno("Confirmation", "Supprimer cette fiche ?"):
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM fiches WHERE id = %s", (item_id,))
                conn.commit()
                conn.close()
                self.load_data()
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur : {e}")

if __name__ == "__main__":
    app = ANRApp()
    if app.authenticated:
        app.mainloop()