CREATE DATABASE IF NOT EXISTS anr_renseignement_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE anr_renseignement_db;

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT IGNORE INTO users (username, password_hash, role)
VALUES ('test', '$2y$10$92IXUNjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.', 'user');

CREATE TABLE IF NOT EXISTS fiches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    photo_path VARCHAR(255) NULL,
    nom_complet VARCHAR(255) NOT NULL,
    alias_surnom VARCHAR(100) NULL,
    sexe VARCHAR(20) NULL,
    date_lieu_naissance VARCHAR(150) NULL,
    nationalite VARCHAR(100) NULL,
    piece_identite VARCHAR(150) NULL,
    domicile_habituel VARCHAR(255) NULL,
    residence_actuelle VARCHAR(255) NULL,
    profession_activite VARCHAR(150) NULL,
    situation_familiale VARCHAR(100) NULL,
    personne_a_prevenir VARCHAR(255) NULL,
    telephone VARCHAR(50) NULL,
    taille_corpulence VARCHAR(100) NULL,
    signes_particuliers TEXT NULL,
    langues_accents VARCHAR(255) NULL,
    num_photo_dossier VARCHAR(100) NULL,
    qualification_penale VARCHAR(255) NULL,
    categorie VARCHAR(100) NULL,
    sous_categorie VARCHAR(150) NULL,
    date_heure_lieu_faits VARCHAR(255) NULL,
    mode_operatoire TEXT NULL,
    groupe_organisation VARCHAR(255) NULL,
    armes_objets TEXT NULL,
    niveau_dangerosite VARCHAR(50) NULL,
    statut_procedural VARCHAR(100) NULL,
    date_lieu_interpellation VARCHAR(255) NULL,
    lieu_detention VARCHAR(255) NULL,
    observations TEXT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

INSERT INTO fiches (photo_path, nom_complet, alias_surnom, sexe, date_lieu_naissance, nationalite, piece_identite, domicile_habituel, residence_actuelle, profession_activite, situation_familiale, personne_a_prevenir, telephone, taille_corpulence, signes_particuliers, langues_accents, num_photo_dossier, qualification_penale, categorie, sous_categorie, date_heure_lieu_faits, mode_operatoire, groupe_organisation, armes_objets, niveau_dangerosite, statut_procedural, date_lieu_interpellation, lieu_detention, observations) VALUES
('', 'KABEYA MWAMBA Jean', 'Kajor', 'Masculin', '12/05/1990 à Lubumbashi', 'Congolaise', 'Carte d''électeur N°12345', 'Av. de la Paix N°12', 'Lubumbashi', 'Commerçant', 'Marié', 'Marie Kabeya', '+243990000001', '1m75 / Moyenne', 'Cicatrice joue gauche', 'Swahili, Français', 'DOS-2026-001', 'Association de malfaiteurs', 'Criminelle', 'Vol à main armée', '01/10/2026 à 14h, Kampemba', 'Utilisation de fausses clés', 'Gang Katanga', 'Arme à feu (Pistolet PM)', 'ELEVÉ', 'Détenu', '02/10/2026 à Kasumbalesa', 'Prison Centrale de Kasapa', 'Sujet actif dans plusieurs dossiers de braquage.');