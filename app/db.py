from __future__ import annotations

import os
import shutil
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Racine du projet: .../chatbot
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_SQLITE_PATH = DATA_DIR / "app.db"


def _resolve_database_url() -> str:
    """Construit une URL DB robuste.

    - Si DATABASE_URL est absent: sqlite local absolu dans ./data/app.db.
    - Si DATABASE_URL est un sqlite relatif: conversion en chemin absolu.
    - Sinon: renvoi tel quel (Postgres/MySQL/etc.).
    """
    env_url = os.getenv("DATABASE_URL")
    if not env_url:
        return f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"

    if env_url.startswith("sqlite:///"):
        raw_path = env_url.replace("sqlite:///", "", 1)
        path_obj = Path(raw_path)
        if not path_obj.is_absolute():
            path_obj = (PROJECT_ROOT / path_obj).resolve()
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path_obj.as_posix()}"

    return env_url


DATABASE_URL = _resolve_database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)

if DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


class Base(DeclarativeBase):
    pass


def get_sqlite_db_path() -> str | None:
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    return DATABASE_URL.replace("sqlite:///", "", 1)


def init_db() -> None:
    """Crée les tables si elles n'existent pas (sans supprimer de données)."""
    # Important: importer les modèles pour enregistrer les tables dans Base.metadata.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_qcm_questions_hierarchy_columns()


def _ensure_qcm_questions_hierarchy_columns() -> None:
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info('qcm_questions')").fetchall()
        if not rows:
            return
        cols = {r[1] for r in rows}

        if "chapitre" not in cols:
            conn.exec_driver_sql("ALTER TABLE qcm_questions ADD COLUMN chapitre VARCHAR(120)")

        if "sous_chapitre" not in cols:
            conn.exec_driver_sql("ALTER TABLE qcm_questions ADD COLUMN sous_chapitre VARCHAR(120)")

        if "reponses_possibles" not in cols:
            conn.exec_driver_sql("ALTER TABLE qcm_questions ADD COLUMN reponses_possibles TEXT")

        conn.exec_driver_sql("UPDATE qcm_questions SET chapitre='Général' WHERE chapitre IS NULL OR trim(chapitre) = ''")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_backups_dir() -> Path | None:
    sqlite_path = get_sqlite_db_path()
    if not sqlite_path:
        return None
    backup_dir = Path(sqlite_path).resolve().parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def list_sqlite_backups() -> list[Path]:
    backup_dir = get_backups_dir()
    if not backup_dir:
        return []
    return sorted(backup_dir.glob("*.db"), reverse=True)


def create_sqlite_backup() -> Path:
    sqlite_path = get_sqlite_db_path()
    if not sqlite_path:
        raise RuntimeError("La sauvegarde automatique est disponible uniquement avec SQLite.")

    db_file = Path(sqlite_path).resolve()
    if not db_file.exists():
        raise FileNotFoundError(f"Base introuvable: {db_file}")

    backup_dir = get_backups_dir()
    assert backup_dir is not None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"app_backup_{timestamp}.db"

    engine.dispose()
    shutil.copy2(db_file, backup_file)
    return backup_file


def restore_sqlite_backup(backup_path: str | Path) -> Path:
    sqlite_path = get_sqlite_db_path()
    if not sqlite_path:
        raise RuntimeError("La restauration automatique est disponible uniquement avec SQLite.")

    source = Path(backup_path).resolve()
    if not source.exists():
        raise FileNotFoundError(f"Sauvegarde introuvable: {source}")

    destination = Path(sqlite_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    engine.dispose()
    shutil.copy2(source, destination)
    return destination
