from __future__ import annotations

import os
from collections.abc import Generator
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


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
