import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

import pymysql
from flask import Flask, abort, g, jsonify, make_response, render_template_string, request, session
from PIL import Image, ImageDraw
from waitress import serve


DATABASE_NAME = "anr_renseignement_db"
ACCOUNT_NAME = "anr_mobile"
ACCOUNT_HOST = "127.0.0.1"
PASSWORD_ITERATIONS = 310_000
FIELDS = (
    "nom_complet",
    "alias_surnom",
    "sexe",
    "date_lieu_naissance",
    "nationalite",
    "piece_identite",
    "domicile_habituel",
    "residence_actuelle",
    "profession_activite",
    "situation_familiale",
    "personne_a_prevenir",
    "telephone",
    "taille_corpulence",
    "signes_particuliers",
    "langues_accents",
    "num_photo_dossier",
    "qualification_penale",
    "categorie",
    "sous_categorie",
    "date_heure_lieu_faits",
    "mode_operatoire",
    "groupe_organisation",
    "armes_objets",
    "niveau_dangerosite",
    "statut_procedural",
    "date_lieu_interpellation",
    "lieu_detention",
    "observations",
)
SEARCH_FIELDS = (
    "nom_complet",
    "alias_surnom",
    "piece_identite",
    "categorie",
    "sous_categorie",
    "statut_procedural",
)
FIELD_LABELS = {
    "alias_surnom": "Alias / surnom",
    "sexe": "Sexe",
    "date_lieu_naissance": "Date et lieu de naissance",
    "nationalite": "Nationalité",
    "piece_identite": "Pièce d’identité",
    "domicile_habituel": "Domicile habituel",
    "residence_actuelle": "Résidence actuelle",
    "profession_activite": "Profession / activité",
    "situation_familiale": "Situation familiale",
    "personne_a_prevenir": "Personne à prévenir",
    "telephone": "Téléphone",
    "taille_corpulence": "Taille / corpulence",
    "signes_particuliers": "Signes particuliers",
    "langues_accents": "Langues / accents",
    "num_photo_dossier": "Numéro photo / dossier",
    "qualification_penale": "Qualification pénale",
    "categorie": "Catégorie",
    "sous_categorie": "Sous-catégorie",
    "date_heure_lieu_faits": "Date, heure et lieu des faits",
    "mode_operatoire": "Mode opératoire",
    "groupe_organisation": "Groupe / organisation",
    "armes_objets": "Armes / objets",
    "niveau_dangerosite": "Niveau de dangerosité",
    "statut_procedural": "Statut procédural",
    "date_lieu_interpellation": "Date et lieu d’interpellation",
    "lieu_detention": "Lieu de détention",
    "observations": "Observations",
}

PAGE = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#1b2a47">
  <meta name="description" content="Consultation sécurisée des fiches ANR">
  <link rel="manifest" href="/manifest.webmanifest">
  <link rel="icon" href="/icon.svg" type="image/svg+xml">
  <title>Consultation ANR</title>
  <style>
    :root { color-scheme: light; font-family: system-ui, sans-serif; color: #17243b; background: #f3f5f8; }
    * { box-sizing: border-box; }
    body { margin: 0; }
    header { background: #1b2a47; color: white; padding: 16px max(16px, calc((100% - 760px) / 2)); }
    header strong { font-size: 1.15rem; }
    main { max-width: 760px; margin: 22px auto; padding: 0 14px 36px; }
    section, article { background: white; border: 1px solid #dfe4eb; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
    h1 { margin: 0 0 14px; font-size: 1.25rem; }
    h2 { font-size: 1.05rem; overflow-wrap: anywhere; }
    label { display: block; font-size: .9rem; margin: 10px 0 5px; }
    input, button { font: inherit; }
    input { width: 100%; padding: 12px; border: 1px solid #aeb8c6; border-radius: 8px; }
    button { min-height: 42px; border: 0; border-radius: 8px; padding: 9px 14px; background: #1b2a47; color: white; font-weight: 650; }
    button.secondary { background: #e7ebf1; color: #17243b; }
    .row { display: flex; gap: 8px; align-items: center; }
    .row input { flex: 1; min-width: 0; }
    .muted { color: #5d6878; font-size: .9rem; }
    .error { color: #a32121; }
    .hidden { display: none !important; }
    .result { width: 100%; text-align: left; background: white; color: #17243b; border: 1px solid #dfe4eb; margin: 0 0 8px; }
    .result small { display: block; color: #5d6878; font-weight: 400; margin-top: 4px; }
    dl { display: grid; grid-template-columns: minmax(115px, 35%) 1fr; gap: 10px 12px; margin: 0; }
    dt { color: #5d6878; font-size: .9rem; }
    dd { margin: 0; overflow-wrap: anywhere; white-space: pre-wrap; }
    @media (max-width: 480px) { main { margin-top: 12px; } .row { align-items: stretch; } dl { grid-template-columns: 1fr; gap: 4px; } dd { margin-bottom: 9px; } }
  </style>
</head>
<body>
  <header><strong>ANR · Consultation sécurisée</strong></header>
  <main>
    <section id="login">
      <h1>Connexion</h1>
      <p class="muted">Accès en lecture seule. Les dossiers ne sont pas enregistrés sur le téléphone.</p>
      <form id="login-form">
        <label for="username">Utilisateur</label>
        <input id="username" autocomplete="username" required maxlength="32">
        <label for="password">Mot de passe</label>
        <input id="password" type="password" autocomplete="current-password" required>
        <p id="login-error" class="error" role="alert"></p>
        <button type="submit">Se connecter</button>
      </form>
    </section>
    <section id="search-panel" class="hidden">
      <div class="row"><h1 style="flex:1">Rechercher une fiche</h1><button id="logout" class="secondary" type="button">Quitter</button></div>
      <form id="search-form" class="row">
        <input id="query" placeholder="Nom, alias, catégorie…" aria-label="Recherche" maxlength="100">
        <button type="submit">Rechercher</button>
      </form>
      <p id="status" class="muted" role="status"></p>
      <div id="results"></div>
    </section>
    <section id="detail-panel" class="hidden">
      <div class="row"><h1 id="detail-title" style="flex:1"></h1><button id="back" class="secondary" type="button">Retour</button></div>
      <dl id="details"></dl>
    </section>
  </main>
  <script nonce="{{ csp_nonce }}">
    const loginPanel = document.querySelector("#login");
    const searchPanel = document.querySelector("#search-panel");
    const detailPanel = document.querySelector("#detail-panel");
    const statusText = document.querySelector("#status");
    const labels = {{ labels|tojson }};

    async function api(url, options = {}) {
      const response = await fetch(url, {
        cache: "no-store",
        headers: options.body ? {"Content-Type": "application/json"} : {},
        ...options,
      });
      if (response.status === 401) {
        showLogin();
        throw new Error("Session expirée. Reconnectez-vous.");
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Une erreur est survenue.");
      return data;
    }

    function showLogin() {
      loginPanel.classList.remove("hidden");
      searchPanel.classList.add("hidden");
      detailPanel.classList.add("hidden");
      document.querySelector("#password").value = "";
    }

    async function showSearch() {
      loginPanel.classList.add("hidden");
      detailPanel.classList.add("hidden");
      searchPanel.classList.remove("hidden");
      await search("");
    }

    async function search(query) {
      statusText.textContent = "Recherche…";
      const results = document.querySelector("#results");
      results.replaceChildren();
      try {
        const data = await api(`/api/fiches?q=${encodeURIComponent(query)}`);
        statusText.textContent = data.items.length
          ? `${data.items.length} résultat(s)${data.has_more ? " — affinez la recherche" : ""}`
          : "Aucune fiche trouvée.";
        for (const item of data.items) {
          const button = document.createElement("button");
          button.type = "button";
          button.className = "result";
          button.textContent = item.nom_complet || "Sans nom";
          const extra = document.createElement("small");
          extra.textContent = [item.alias_surnom, item.categorie, item.statut_procedural].filter(Boolean).join(" · ");
          button.append(extra);
          button.addEventListener("click", () => showDetail(item.id));
          results.append(button);
        }
      } catch (error) {
        statusText.textContent = error.message;
      }
    }

    async function showDetail(id) {
      try {
        const item = await api(`/api/fiches/${id}`);
        document.querySelector("#detail-title").textContent = item.nom_complet || "Fiche";
        const details = document.querySelector("#details");
        details.replaceChildren();
        for (const [key, label] of Object.entries(labels)) {
          const value = item[key];
          if (value === null || value === undefined || value === "") continue;
          const term = document.createElement("dt");
          term.textContent = label;
          const description = document.createElement("dd");
          description.textContent = value;
          details.append(term, description);
        }
        searchPanel.classList.add("hidden");
        detailPanel.classList.remove("hidden");
      } catch (error) {
        statusText.textContent = error.message;
      }
    }

    document.querySelector("#login-form").addEventListener("submit", async event => {
      event.preventDefault();
      const errorText = document.querySelector("#login-error");
      errorText.textContent = "";
      try {
        await api("/api/login", {
          method: "POST",
          body: JSON.stringify({
            username: document.querySelector("#username").value,
            password: document.querySelector("#password").value,
          }),
        });
        await showSearch();
      } catch (error) {
        errorText.textContent = error.message;
      }
    });

    document.querySelector("#search-form").addEventListener("submit", event => {
      event.preventDefault();
      search(document.querySelector("#query").value.trim());
    });
    document.querySelector("#logout").addEventListener("click", async () => {
      await api("/api/logout", {method: "POST", body: "{}"});
      showLogin();
    });
    document.querySelector("#back").addEventListener("click", () => {
      detailPanel.classList.add("hidden");
      searchPanel.classList.remove("hidden");
    });
    api("/api/session").then(showSearch).catch(showLogin);
  </script>
</body>
</html>"""


def get_config_dir():
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "Application_ANR_MySQL" / "mobile_portal"


def load_config(config_dir=None):
    path = (config_dir or get_config_dir()) / "config.json"
    with path.open(encoding="utf-8") as config_file:
        config = json.load(config_file)
    required = {"secret_key", "mysql_password"}
    if not required.issubset(config):
        raise ValueError(f"Configuration incomplète : {path}")
    return config


@contextmanager
def open_auth_db(config_dir):
    connection = sqlite3.connect(config_dir / "readers.sqlite3")
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


def create_app(config_dir=None, database_config=None, testing=False):
    config_dir = Path(config_dir or get_config_dir())
    config = load_config(config_dir)
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=config["secret_key"],
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=not testing,
        SESSION_COOKIE_SAMESITE="Strict",
        PERMANENT_SESSION_LIFETIME=1800,
        MAX_CONTENT_LENGTH=4096,
        TESTING=testing,
    )
    db_config = dict(database_config) if database_config is not None else {
        "host": "127.0.0.1",
        "user": ACCOUNT_NAME,
        "password": config["mysql_password"],
        "database": DATABASE_NAME,
        "connect_timeout": 5,
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": True,
    }
    failed_logins = {}
    login_lock = threading.Lock()
    dummy_salt = secrets.token_bytes(16)
    dummy_hash = hashlib.pbkdf2_hmac(
        "sha256", secrets.token_bytes(32), dummy_salt, PASSWORD_ITERATIONS
    )

    @app.before_request
    def create_nonce():
        g.csp_nonce = secrets.token_urlsafe(18)

    def authenticated(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("reader"):
                return jsonify(error="Connexion requise."), 401
            return view(*args, **kwargs)

        return wrapped

    @app.after_request
    def add_security_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            f"script-src 'self' 'nonce-{g.csp_nonce}'; img-src 'self' data:; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        return response

    @app.get("/")
    def index():
        return render_template_string(
            PAGE, labels=FIELD_LABELS, csp_nonce=g.csp_nonce
        )

    @app.get("/manifest.webmanifest")
    def manifest():
        return jsonify(
            name="Consultation ANR",
            short_name="ANR",
            start_url="/",
            display="standalone",
            background_color="#f3f5f8",
            theme_color="#1b2a47",
            icons=[
                {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png"},
            ],
        )

    @app.get("/icon.svg")
    def icon():
        response = make_response(
            """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
            <rect width="64" height="64" rx="12" fill="#1b2a47"/>
            <path d="m32 8 6 14 15 2-11 10 3 15-13-8-13 8 3-15-11-10 15-2z" fill="#f7d618"/>
            <text x="32" y="58" fill="white" font-family="Arial" font-size="12" font-weight="bold" text-anchor="middle">ANR</text>
            </svg>"""
        )
        response.headers["Content-Type"] = "image/svg+xml"
        return response

    @app.get("/icon-<int:size>.png")
    def png_icon(size):
        if size not in (192, 512):
            abort(404)
        image = Image.new("RGBA", (size, size), "#1b2a47")
        draw = ImageDraw.Draw(image)
        margin = size // 16
        draw.rounded_rectangle(
            (margin, margin, size - margin, size - margin),
            radius=size // 5,
            fill="#1b2a47",
            outline="#f7d618",
            width=max(2, size // 64),
        )
        center = size // 2
        draw.polygon(
            [
                (center, size // 7),
                (center + size // 14, size // 3),
                (center + size // 4, size // 3),
                (center + size // 10, center),
                (center + size // 7, center + size // 5),
                (center, center + size // 10),
                (center - size // 7, center + size // 5),
                (center - size // 10, center),
                (center - size // 4, size // 3),
                (center - size // 14, size // 3),
            ],
            fill="#f7d618",
        )
        draw.text(
            (center, size * 3 // 4),
            "ANR",
            fill="white",
            anchor="mm",
            font_size=size // 5,
            stroke_width=0,
        )
        from io import BytesIO

        buffer = BytesIO()
        image.save(buffer, format="PNG")
        response = make_response(buffer.getvalue())
        response.headers["Content-Type"] = "image/png"
        return response

    @app.post("/api/login")
    def login():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Requête invalide."), 400
        username = str(payload.get("username", "")).strip()
        password = payload.get("password", "")
        if not isinstance(password, str) or len(username) > 32 or len(password) > 256:
            return jsonify(error="Identifiant ou mot de passe invalide."), 400
        key = username.casefold()
        now = time.monotonic()
        with login_lock:
            attempts, blocked_until = failed_logins.get(key, (0, 0.0))
            if blocked_until > now:
                return jsonify(error="Trop de tentatives. Réessayez dans une minute."), 429
        with open_auth_db(config_dir) as connection:
            reader = connection.execute(
                "SELECT username, password_salt, password_hash "
                "FROM readers WHERE username = ? COLLATE NOCASE",
                (username,),
            ).fetchone()
        salt = reader["password_salt"] if reader is not None else dummy_salt
        expected_hash = reader["password_hash"] if reader is not None else dummy_hash
        candidate = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
        )
        valid = reader is not None and hmac.compare_digest(candidate, expected_hash)
        if not valid:
            with login_lock:
                attempts += 1
                failed_logins[key] = (attempts, now + 60.0 if attempts >= 5 else 0.0)
            return jsonify(error="Utilisateur ou mot de passe incorrect."), 401
        with login_lock:
            failed_logins.pop(key, None)
        session.clear()
        session["reader"] = reader["username"]
        session.permanent = True
        return jsonify(username=reader["username"])

    @app.post("/api/logout")
    @authenticated
    def logout():
        session.clear()
        return jsonify(ok=True)

    @app.get("/api/session")
    @authenticated
    def current_session():
        return jsonify(username=session["reader"])

    @app.get("/api/fiches")
    @authenticated
    def list_fiches():
        query = request.args.get("q", "").strip()
        if len(query) > 100:
            return jsonify(error="La recherche est limitée à 100 caractères."), 400
        limit = 101
        selected_fields = (
            "id", "nom_complet", "alias_surnom", "categorie", "sous_categorie",
            "statut_procedural",
        )
        sql = "SELECT " + ", ".join(selected_fields) + " FROM fiches"
        params = []
        if query:
            sql += " WHERE " + " OR ".join(
                f"{field} LIKE %s" for field in SEARCH_FIELDS
            )
            params.extend([f"%{query}%"] * len(SEARCH_FIELDS))
        sql += " ORDER BY id DESC LIMIT %s"
        params.append(limit)
        try:
            connection = pymysql.connect(**db_config)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall()
            finally:
                connection.close()
        except pymysql.MySQLError:
            app.logger.exception("Échec de lecture de la base MySQL")
            return jsonify(error="Base de données indisponible."), 503
        return jsonify(items=rows[:100], has_more=len(rows) > 100)

    @app.get("/api/fiches/<int:fiche_id>")
    @authenticated
    def get_fiche(fiche_id):
        if fiche_id < 1:
            abort(404)
        fields = ("id",) + FIELDS
        sql = "SELECT " + ", ".join(fields) + " FROM fiches WHERE id = %s"
        try:
            connection = pymysql.connect(**db_config)
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql, (fiche_id,))
                    row = cursor.fetchone()
            finally:
                connection.close()
        except pymysql.MySQLError:
            app.logger.exception("Échec de lecture d'une fiche MySQL")
            return jsonify(error="Base de données indisponible."), 503
        if row is None:
            return jsonify(error="Fiche introuvable."), 404
        return jsonify(row)

    return app


def main():
    config_dir = get_config_dir()
    if not (config_dir / "config.json").exists():
        raise SystemExit(
            "Le portail Android n'est pas configuré. Lancez setup_android.bat."
        )
    logging.basicConfig(level=logging.INFO)
    app = create_app(config_dir)
    print("Portail ANR en écoute locale sur 127.0.0.1:8765.")
    print("Publiez-le uniquement avec Tailscale Serve en HTTPS.")
    serve(app, host="127.0.0.1", port=8765, threads=4)


if __name__ == "__main__":
    main()
