from __future__ import annotations

HELP_TEXTS = {
    "email": "Email unique du stagiaire. Utilisé pour détecter les doublons à l'import CSV.",
    "section": "Section actuelle du stagiaire. Laisser vide si non affecté.",
    "formation": "Formation souhaitée par le stagiaire (orientation).",
    "dates": "La date de fin doit être supérieure ou égale à la date de début.",
    "delete": "Action destructive. Une confirmation est demandée avant suppression.",
    "import_separator": "Auto tente de détecter le séparateur. Vous pouvez forcer virgule, point-virgule ou tabulation.",
    "import_encoding": "Auto teste utf-8 puis latin-1. Forcer un encodage si les accents sont incorrects.",
    "import_strategy": "skip=ignore, update=met à jour les emails existants, strict=annule l'import en cas de doublon.",
}

AIDE_SECTIONS = {
    "overview": "Application locale pour gérer stagiaires, sections et formations, avec import CSV et validations.",
    "stagiaires": "Créer, modifier, supprimer, rechercher, et affecter un stagiaire à une section + formation souhaitée.",
    "sections": "Créer/modifier les sections, puis ajouter/retirer des stagiaires depuis l'écran section.",
    "formations": "Créer/modifier les formations et les associer comme souhaitées pour les stagiaires.",
    "import_csv": "Importer en masse des stagiaires avec prévisualisation, mapping des colonnes, validation et rapport.",
    "database": "Base SQLite locale (data/app.db). Les migrations Alembic appliquent les changements de schéma.",
}

CSV_EXAMPLE = """nom,prenom,email,telephone,section_code,formation_code,notes
Dupont,Jean,jean.dupont@example.com,0600000001,AC1025,MAB,Profil reconversion
Martin,Lea,lea.martin@example.com,0600000002,AC1025,TMB,Disponible le matin
"""
