from __future__ import annotations

from app import crud
from app.importer import ImportOptions, apply_import, parse_csv, validate_rows
from app.models import Base
from app.db import SessionLocal, engine
from app.schemas import StagiaireCreate


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_import_simple_two_rows_ok():
    csv_data = b"nom,prenom,email\nDoe,John,john@example.com\nSmith,Anna,anna@example.com\n"
    df = parse_csv(csv_data)
    mapping = {"nom": "nom", "prenom": "prenom", "email": "email", "telephone": "-- Ignorer --", "notes": "-- Ignorer --", "section_code": "-- Ignorer --", "formation_code": "-- Ignorer --"}

    with SessionLocal() as db:
        valid, errors, duplicates = validate_rows(df, mapping, db, ImportOptions())
        assert len(errors) == 0
        assert len(duplicates) == 0
        stats, _ = apply_import(db, valid, ImportOptions())
        assert stats["created"] == 2


def test_import_duplicate_email_update_strategy():
    with SessionLocal() as db:
        crud.create_stagiaire(
            db,
            payload=StagiaireCreate(nom="Old", prenom="Name", email="dup@example.com"),
        )

        csv_data = b"nom,prenom,email\nNew,Name,dup@example.com\n"
        df = parse_csv(csv_data)
        mapping = {"nom": "nom", "prenom": "prenom", "email": "email", "telephone": "-- Ignorer --", "notes": "-- Ignorer --", "section_code": "-- Ignorer --", "formation_code": "-- Ignorer --"}
        options = ImportOptions(duplicate_strategy="update")
        valid, errors, duplicates = validate_rows(df, mapping, db, options)
        assert len(errors) == 0
        assert len(duplicates) == 1
        stats, _ = apply_import(db, valid, options)
        assert stats["updated"] == 1


def test_unknown_section_with_auto_create_toggle():
    csv_data = b"nom,prenom,section_code\nDoe,John,NEWSEC\n"
    df = parse_csv(csv_data)
    mapping = {"nom": "nom", "prenom": "prenom", "email": "-- Ignorer --", "telephone": "-- Ignorer --", "notes": "-- Ignorer --", "section_code": "section_code", "formation_code": "-- Ignorer --"}

    with SessionLocal() as db:
        valid, _, _ = validate_rows(df, mapping, db, ImportOptions(create_missing_sections=False))
        stats, report = apply_import(db, valid, ImportOptions(create_missing_sections=False))
        assert stats["errors"] >= 1
        assert any("section inconnue" in r["message"] for r in report)

    with SessionLocal() as db:
        valid, _, _ = validate_rows(df, mapping, db, ImportOptions(create_missing_sections=True))
        stats, _ = apply_import(db, valid, ImportOptions(create_missing_sections=True))
        assert stats["created"] == 1
        assert crud.get_section_by_code(db, "NEWSEC") is not None
