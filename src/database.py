from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = Path("data/questionnaire.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def initialize_database() -> None:
    """Create tables and tolerate duplicate-table race/driver quirks on SQLite."""
    try:
        Base.metadata.create_all(engine, checkfirst=True)
    except OperationalError as exc:
        if "already exists" not in str(exc).lower():
            raise
