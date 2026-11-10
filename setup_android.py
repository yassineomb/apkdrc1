import getpass
import hashlib
import json
import re
import secrets
import sqlite3
import sys
from pathlib import Path

import pymysql

from mobile_portal import (
    ACCOUNT_HOST,
    ACCOUNT_NAME,
    DATABASE_NAME,
    PASSWORD_ITERATIONS,
    get_config_dir,
)


def create_reader_database(config_dir, username, password):
    salt = secrets.token_bytes(16)
    password_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    with sqlite3.connect(config_dir / "readers.sqlite3") as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS readers (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                password_salt BLOB NOT NULL,
                password_hash BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )"""
        )
        connection.execute(
            "INSERT INTO readers (username, password_salt, password_hash) "
            "VALUES (?, ?, ?)",
            (username, salt, password_hash),
        )


def setup():
    config_dir = get_config_dir()
    config_path = config_dir / "config.json"
    if config_path.exists():
        raise SystemExit(
            f"Le portail est déjà configuré dans {config_dir}. "
            "Ne relancez pas cette configuration."
        )

    username = input("Nom du compte de lecture (3 à 32 caractères) : ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", username):
        raise SystemExit("Nom invalide : utilisez lettres, chiffres, point, tiret ou _.")
    password = getpass.getpass("Choisissez un mot de passe (14 caractères minimum) : ")
    if len(password) < 14:
        raise SystemExit("Le mot de passe doit comporter au moins 14 caractères.")
    if password != getpass.getpass("Confirmez le mot de passe : "):
        raise SystemExit("Les mots de passe ne correspondent pas.")

    db_admin = input("Utilisateur administrateur MySQL [root] : ").strip() or "root"
    db_admin_password = getpass.getpass("Mot de passe administrateur MySQL : ")
    mobile_password = secrets.token_urlsafe(32)
    connection = None
    try:
        connection = pymysql.connect(
            host="127.0.0.1",
            user=db_admin,
            password=db_admin_password,
            database=DATABASE_NAME,
            connect_timeout=5,
            autocommit=True,
        )
        with connection.cursor() as cursor:
            cursor.execute(
                f"CREATE USER IF NOT EXISTS '{ACCOUNT_NAME}'@'{ACCOUNT_HOST}' "
                "IDENTIFIED BY %s",
                (mobile_password,),
            )
            cursor.execute(
                f"ALTER USER '{ACCOUNT_NAME}'@'{ACCOUNT_HOST}' IDENTIFIED BY %s",
                (mobile_password,),
            )
            cursor.execute(
                f"GRANT SELECT ON {DATABASE_NAME}.fiches "
                f"TO '{ACCOUNT_NAME}'@'{ACCOUNT_HOST}'"
            )
            cursor.execute("SHOW COLUMNS FROM fiches")
            actual_columns = {row[0] for row in cursor.fetchall()}
        from mobile_portal import FIELDS

        missing_columns = set(FIELDS) - actual_columns
        if missing_columns:
            raise RuntimeError(
                "Colonnes requises absentes de la table fiches : "
                + ", ".join(sorted(missing_columns))
            )
    except (OSError, pymysql.MySQLError, RuntimeError) as error:
        raise SystemExit(f"Échec de la configuration MySQL : {error}") from error
    finally:
        if connection is not None:
            connection.close()

    config_dir.mkdir(parents=True, exist_ok=True)
    try:
        create_reader_database(config_dir, username, password)
        config_path.write_text(
            json.dumps(
                {
                    "secret_key": secrets.token_hex(32),
                    "mysql_password": mobile_password,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        (config_dir / "readers.sqlite3").unlink(missing_ok=True)
        raise
    print("\nConfiguration terminée.")
    print(f"Compte de lecture créé : {username}")
    print(f"Fichiers de configuration conservés dans : {config_dir}")
    print("Lancez lancer_android.bat sur ce PC serveur.")


if __name__ == "__main__":
    try:
        setup()
    except KeyboardInterrupt:
        print("\nConfiguration annulée.")
        sys.exit(1)
