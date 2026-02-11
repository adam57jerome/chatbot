from __future__ import annotations

import csv
import io
from dataclasses import dataclass

import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import crud
from app.schemas import StagiaireCreate, StagiaireUpdate


@dataclass
class ImportOptions:
    create_missing_sections: bool = False
    create_missing_formations: bool = False
    duplicate_strategy: str = "skip"  # skip|update|strict
    title_case_names: bool = True


def detect_separator(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        return dialect.delimiter
    except csv.Error:
        return ","


def parse_csv(file_bytes: bytes, sep: str = "auto", encoding: str = "auto", has_header: bool = True) -> pd.DataFrame:
    encodings = ["utf-8", "latin-1"] if encoding == "auto" else [encoding]
    last_error = None
    for enc in encodings:
        try:
            text = file_bytes.decode(enc)
            delimiter = detect_separator(text[:2048]) if sep == "auto" else sep
            header = 0 if has_header else None
            df = pd.read_csv(io.StringIO(text), sep=delimiter, header=header, dtype=str, keep_default_na=False)
            if not has_header:
                df.columns = [f"col_{i+1}" for i in range(len(df.columns))]
            return df
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise ValueError(f"Impossible de lire le CSV: {last_error}")


def normalize_value(value: str | None) -> str | None:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def validate_rows(df: pd.DataFrame, mapping: dict[str, str], db: Session, options: ImportOptions):
    valid_rows: list[dict] = []
    errors: list[dict] = []
    duplicates: list[dict] = []

    for i, raw in df.iterrows():
        line_no = int(i) + 2

        def col(name: str) -> str | None:
            src = mapping.get(name)
            if not src or src == "-- Ignorer --":
                return None
            return normalize_value(raw.get(src))

        nom = col("nom")
        prenom = col("prenom")
        email = col("email")
        telephone = col("telephone")
        notes = col("notes")
        section_code = col("section_code")
        formation_code = col("formation_code")

        if options.title_case_names:
            nom = nom.title() if nom else nom
            prenom = prenom.title() if prenom else prenom

        if not nom or not prenom:
            errors.append({"line": line_no, "status": "error", "message": "nom/prenom obligatoires"})
            continue

        existing = crud.get_trainee_by_email(db, email) if email else None
        if existing:
            duplicates.append({"line": line_no, "email": email, "existing_id": existing.id})
            if options.duplicate_strategy == "strict":
                errors.append({"line": line_no, "status": "error", "message": f"doublon email: {email}"})
                continue

        valid_rows.append(
            {
                "line": line_no,
                "nom": nom,
                "prenom": prenom,
                "email": email,
                "telephone": telephone,
                "notes": notes,
                "section_code": section_code,
                "formation_code": formation_code,
                "existing": existing,
            }
        )

    return valid_rows, errors, duplicates


def _resolve_section_id(db: Session, code: str | None, options: ImportOptions) -> tuple[int | None, str | None]:
    if not code:
        return None, None
    section = crud.get_section_by_code(db, code)
    if section:
        return section.id, None
    if options.create_missing_sections:
        created = crud.create_section_from_code(db, code)
        return created.id, None
    return None, f"section inconnue: {code}"


def _resolve_formation_id(db: Session, code: str | None, options: ImportOptions) -> tuple[int | None, str | None]:
    if not code:
        return None, None
    formation = crud.get_formation_by_code(db, code)
    if formation:
        return formation.id, None
    if options.create_missing_formations:
        created = crud.create_formation_from_code(db, code)
        return created.id, None
    return None, f"formation inconnue: {code}"


def apply_import(db: Session, valid_rows: list[dict], options: ImportOptions):
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}
    report: list[dict] = []

    strict_mode = options.duplicate_strategy == "strict"
    try:
        for row in valid_rows:
            section_id, section_err = _resolve_section_id(db, row["section_code"], options)
            formation_id, formation_err = _resolve_formation_id(db, row["formation_code"], options)
            if section_err or formation_err:
                msg = section_err or formation_err
                stats["errors"] += 1
                report.append({"line": row["line"], "status": "error", "message": msg})
                if strict_mode:
                    raise ValueError(msg)
                continue

            existing = row.get("existing")
            if existing and options.duplicate_strategy == "skip":
                stats["skipped"] += 1
                report.append({"line": row["line"], "status": "skipped", "message": "doublon ignoré"})
                continue

            if existing and options.duplicate_strategy == "update":
                payload = StagiaireUpdate(
                    nom=row["nom"],
                    prenom=row["prenom"],
                    email=row["email"],
                    telephone=row["telephone"],
                    notes=row["notes"],
                    section_id=section_id,
                    formation_souhaitee_id=formation_id,
                )
                crud.update_stagiaire(db, existing, payload)
                stats["updated"] += 1
                report.append({"line": row["line"], "status": "updated", "message": "stagiaire mis à jour"})
                continue

            payload = StagiaireCreate(
                nom=row["nom"],
                prenom=row["prenom"],
                email=row["email"],
                telephone=row["telephone"],
                notes=row["notes"],
                section_id=section_id,
                formation_souhaitee_id=formation_id,
            )
            crud.create_stagiaire(db, payload)
            stats["created"] += 1
            report.append({"line": row["line"], "status": "created", "message": "stagiaire créé"})

        db.commit()
    except (IntegrityError, ValueError) as exc:
        db.rollback()
        if strict_mode:
            stats["errors"] += 1
            report.append({"line": "global", "status": "error", "message": f"rollback strict: {exc}"})
        else:
            raise

    return stats, report


def report_to_csv(report: list[dict]) -> bytes:
    df = pd.DataFrame(report if report else [{"line": "-", "status": "info", "message": "Aucun événement"}])
    return df.to_csv(index=False).encode("utf-8")
