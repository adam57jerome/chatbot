from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Section, Stagiaire


def seed() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(Section.id).limit(1)):
            print("Des données existent déjà, seed ignoré.")
            return

        sec1 = Section(code="AC1025", nom="Développeur Web", description="Formation fullstack", date_debut=date(2025, 10, 1), date_fin=date(2026, 3, 31))
        sec2 = Section(code="DS2025", nom="Data Analyst", description="Analyse de données", date_debut=date(2025, 11, 15), date_fin=date(2026, 4, 15))
        db.add_all([sec1, sec2])
        db.flush()

        trainees = [
            Stagiaire(nom="Dupont", prenom="Alice", email="alice.dupont@example.test", section_id=sec1.id),
            Stagiaire(nom="Martin", prenom="Yanis", email="yanis.martin@example.test", section_id=sec2.id),
            Stagiaire(nom="Nguyen", prenom="Linh", email="linh.nguyen@example.test", section_id=None),
            Stagiaire(nom="Diallo", prenom="Moussa", email=None, section_id=None),
        ]
        db.add_all(trainees)
        db.commit()
        print("Seed terminé.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
