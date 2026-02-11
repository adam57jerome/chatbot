from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Section, Stagiaire


client = TestClient(app)


def setup_module(module):
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def teardown_module(module):
    Path("test.db").unlink(missing_ok=True)


def test_create_section_and_list():
    response = client.post(
        "/sections/nouveau",
        data={"code": "QA2025", "nom": "Qualité logicielle", "date_debut": "", "date_fin": "", "description": ""},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "QA2025" in response.text


def test_create_trainee_with_section():
    db = SessionLocal()
    try:
        section = db.query(Section).filter_by(code="QA2025").first()
        assert section is not None
    finally:
        db.close()

    response = client.post(
        "/stagiaires/nouveau",
        data={"nom": "Test", "prenom": "User", "email": "test.user@example.test", "telephone": "", "notes": "", "section_id": str(section.id)},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Test" in response.text
    assert "QA2025" in response.text


def test_delete_section_unassigns_trainees():
    db = SessionLocal()
    try:
        section = db.query(Section).filter_by(code="QA2025").first()
        trainee = db.query(Stagiaire).filter_by(email="test.user@example.test").first()
        assert section and trainee
        trainee_id = trainee.id
        section_id = section.id
    finally:
        db.close()

    client.post(f"/sections/{section_id}/delete", follow_redirects=True)

    db = SessionLocal()
    try:
        trainee = db.get(Stagiaire, trainee_id)
        assert trainee is not None
        assert trainee.section_id is None
    finally:
        db.close()
