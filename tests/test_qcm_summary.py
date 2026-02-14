from __future__ import annotations

from app.db import Base, SessionLocal, engine
from app.models import Stagiaire
from app.qcm_service import (
    add_question,
    create_questionnaire,
    get_trainee_qcm_summary,
    start_attempt,
    submit_attempt,
)


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_summary_aggregates_average_and_correct_incorrect():
    with SessionLocal() as db:
        trainee = Stagiaire(nom="Test", prenom="User", email="test.summary@example.com")
        db.add(trainee)
        db.commit()
        db.refresh(trainee)

        q = create_questionnaire(db, "QCM Test", "desc")
        q1 = add_question(db, q.id, 1, "A", chapitre="Français", sous_chapitre="Grammaire")
        q2 = add_question(db, q.id, 2, "B", chapitre="Mathématiques")

        a1 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a1.id, {q1.id: "A", q2.id: "B"})  # 20

        a2 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a2.id, {q1.id: "A", q2.id: "C"})  # 10

        summary = get_trainee_qcm_summary(db, trainee.id)
        assert summary["stats"]["total_attempts"] == 2
        assert summary["stats"]["average_note"] == 15.0
        assert summary["correct_incorrect"]["correct"] == 3
        assert summary["correct_incorrect"]["incorrect"] == 1


def test_summary_by_chapter_and_subchapter_aggregations():
    with SessionLocal() as db:
        trainee = Stagiaire(nom="Chap", prenom="Test", email="chap.summary@example.com")
        db.add(trainee)
        db.commit()
        db.refresh(trainee)

        q = create_questionnaire(db, "QCM Chapitres", "desc")
        q1 = add_question(db, q.id, 1, "A", chapitre="Français", sous_chapitre="Grammaire")
        q2 = add_question(db, q.id, 2, "B", chapitre="Français", sous_chapitre="Vocabulaire")
        q3 = add_question(db, q.id, 3, "C", chapitre="Mathématiques")

        a1 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a1.id, {q1.id: "A", q2.id: "X", q3.id: "C"})

        summary = get_trainee_qcm_summary(db, trainee.id)
        chapters = {r["chapitre"]: r for r in summary["by_chapter"]}
        assert chapters["Français"]["questions"] == 2
        assert chapters["Français"]["correct"] == 1
        assert chapters["Mathématiques"]["questions"] == 1
        assert chapters["Mathématiques"]["correct"] == 1


def test_summary_groups_empty_subchapter_under_default_label():
    with SessionLocal() as db:
        trainee = Stagiaire(nom="Sub", prenom="Test", email="sub.summary@example.com")
        db.add(trainee)
        db.commit()
        db.refresh(trainee)

        q = create_questionnaire(db, "QCM Sous", "desc")
        q1 = add_question(db, q.id, 1, "A", chapitre="Mathématiques", sous_chapitre="")
        a1 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a1.id, {q1.id: "A"})

        summary = get_trainee_qcm_summary(db, trainee.id)
        rows = [r for r in summary["by_subchapter"] if r["chapitre"] == "Mathématiques"]
        assert rows[0]["sous_chapitre"] == "Sans sous-chapitre"
