from __future__ import annotations

from app.db import Base, SessionLocal, engine
from app.models import Stagiaire
from app.qcm_service import (
    add_question,
    create_questionnaire,
    delete_attempt,
    get_attempt_answers_map,
    get_attempt_review_rows,
    get_attempt_total_possible_points,
    get_total_possible_points_for_questionnaire,
    parse_possible_answers,
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


def test_delete_attempt_and_retrieve_answers_map():
    with SessionLocal() as db:
        trainee = Stagiaire(nom="Edit", prenom="Attempt", email="edit.attempt@example.com")
        db.add(trainee)
        db.commit()
        db.refresh(trainee)

        q = create_questionnaire(db, "QCM Delete", "desc")
        q1 = add_question(db, q.id, 1, "A", chapitre="Français")
        a1 = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, a1.id, {q1.id: "A"})

        answers = get_attempt_answers_map(db, a1.id)
        assert answers[q1.id] == "A"

        assert delete_attempt(db, a1.id) is True
        assert delete_attempt(db, a1.id) is False


def test_list_questions_keeps_insert_order_not_alphabetical():
    from app.qcm_service import list_questions

    with SessionLocal() as db:
        q = create_questionnaire(db, "QCM Ordre import", "desc")
        q1 = add_question(db, q.id, 10, "A", chapitre="Zeta")
        q2 = add_question(db, q.id, 1, "B", chapitre="Alpha")
        q3 = add_question(db, q.id, 5, "C", chapitre="Beta")

        questions = list_questions(db, q.id)
        assert [q.id for q in questions] == [q1.id, q2.id, q3.id]


def test_possible_answers_are_stored_and_parsed_variable_count():
    with SessionLocal() as db:
        q = create_questionnaire(db, "QCM Choix", "desc")
        question = add_question(
            db,
            q.id,
            1,
            "A,C",
            chapitre="Français",
            possible_answers=["A", "B", "C", "D"],
        )
        parsed = parse_possible_answers(question.reponses_possibles)
        assert parsed == ["A", "B", "C", "D"]


def test_possible_answers_empty_returns_empty_list():
    assert parse_possible_answers(None) == []
    assert parse_possible_answers("") == []


def test_attempt_review_rows_include_expected_and_trainee_answers():
    with SessionLocal() as db:
        trainee = Stagiaire(nom="Review", prenom="User", email="review.user@example.com")
        db.add(trainee)
        db.commit()
        db.refresh(trainee)

        q = create_questionnaire(db, "QCM Review", "desc")
        q1 = add_question(db, q.id, 1, "B", chapitre="Mathématiques", points=2)
        attempt = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, attempt.id, {q1.id: "A"})

        rows = get_attempt_review_rows(db, attempt.id)
        assert len(rows) == 1
        assert rows[0]["attendu"] == "B"
        assert rows[0]["reponse_stagiaire"] == "A"
        assert rows[0]["points_max"] == 2


def test_total_possible_points_for_questionnaire_uses_weighted_questions():
    with SessionLocal() as db:
        q = create_questionnaire(db, "QCM Pondéré", "desc")
        add_question(db, q.id, 1, "A", chapitre="Français", points=3)
        add_question(db, q.id, 2, "B", chapitre="Français", points=2)

        assert get_total_possible_points_for_questionnaire(db, q.id) == 5


def test_attempt_total_possible_points_is_stored_on_submit():
    with SessionLocal() as db:
        trainee = Stagiaire(nom="Store", prenom="Points", email="store.points@example.com")
        db.add(trainee)
        db.commit()
        db.refresh(trainee)

        q = create_questionnaire(db, "QCM Store", "desc")
        q1 = add_question(db, q.id, 1, "A", chapitre="Français", points=3)
        attempt = start_attempt(db, trainee.id, q.id)
        submit_attempt(db, attempt.id, {q1.id: "A"})

        assert get_attempt_total_possible_points(db, attempt.id) == 3
