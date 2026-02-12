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
        q1 = add_question(db, q.id, 1, "A")
        q2 = add_question(db, q.id, 2, "B")

        a1 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a1.id, {q1.id: "A", q2.id: "B"})  # 20

        a2 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a2.id, {q1.id: "A", q2.id: "C"})  # 10

        summary = get_trainee_qcm_summary(db, trainee.id)
        assert summary["stats"]["total_attempts"] == 2
        assert summary["stats"]["average_note"] == 15.0
        assert summary["correct_incorrect"]["correct"] == 3
        assert summary["correct_incorrect"]["incorrect"] == 1
