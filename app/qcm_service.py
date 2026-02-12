from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import QCMAnswer, QCMAttempt, QCMQuestion, Questionnaire


@dataclass
class AttemptResult:
    score_brut: int
    total_questions: int
    note_sur_20: float


def normalize_answer(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip().upper().replace(" ", "")
    if "," in cleaned:
        items = sorted([part for part in cleaned.split(",") if part])
        return ",".join(items)
    return cleaned


def compute_note_sur_20(score_brut: int, total_questions: int) -> float:
    if total_questions <= 0:
        return 0.0
    return round((score_brut / total_questions) * 20, 1)


# Questionnaires

def create_questionnaire(db: Session, titre: str, description: str | None = None, bareme_sur: int = 20) -> Questionnaire:
    questionnaire = Questionnaire(titre=titre.strip(), description=description or None, bareme_sur=bareme_sur)
    db.add(questionnaire)
    db.commit()
    db.refresh(questionnaire)
    return questionnaire


def update_questionnaire(db: Session, questionnaire_id: int, titre: str, description: str | None = None) -> Questionnaire | None:
    questionnaire = db.get(Questionnaire, questionnaire_id)
    if not questionnaire:
        return None
    questionnaire.titre = titre.strip()
    questionnaire.description = description or None
    db.commit()
    db.refresh(questionnaire)
    return questionnaire


def delete_questionnaire(db: Session, questionnaire_id: int) -> bool:
    questionnaire = db.get(Questionnaire, questionnaire_id)
    if not questionnaire:
        return False
    db.delete(questionnaire)
    db.commit()
    return True


def list_questionnaires(db: Session, q: str | None = None):
    query = select(Questionnaire)
    if q:
        query = query.where(func.lower(Questionnaire.titre).contains(q.strip().lower()))
    return db.scalars(query.order_by(Questionnaire.created_at.desc())).all()


def add_question(
    db: Session,
    questionnaire_id: int,
    numero: int,
    resultat_attendu: str,
    enonce: str | None = None,
    points: int = 1,
) -> QCMQuestion:
    question = QCMQuestion(
        questionnaire_id=questionnaire_id,
        numero=numero,
        enonce=enonce or None,
        resultat_attendu=resultat_attendu.strip(),
        points=points,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


def update_question(
    db: Session,
    question_id: int,
    numero: int,
    resultat_attendu: str,
    enonce: str | None = None,
    points: int = 1,
) -> QCMQuestion | None:
    question = db.get(QCMQuestion, question_id)
    if not question:
        return None
    question.numero = numero
    question.resultat_attendu = resultat_attendu.strip()
    question.enonce = enonce or None
    question.points = points
    db.commit()
    db.refresh(question)
    return question


def delete_question(db: Session, question_id: int) -> bool:
    question = db.get(QCMQuestion, question_id)
    if not question:
        return False
    db.delete(question)
    db.commit()
    return True


def list_questions(db: Session, questionnaire_id: int):
    return db.scalars(
        select(QCMQuestion).where(QCMQuestion.questionnaire_id == questionnaire_id).order_by(QCMQuestion.numero)
    ).all()


# Attempts

def start_attempt(db: Session, stagiaire_id: int, questionnaire_id: int) -> QCMAttempt:
    attempt = QCMAttempt(stagiaire_id=stagiaire_id, questionnaire_id=questionnaire_id)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def submit_attempt(db: Session, attempt_id: int, answers_dict: dict[int, str | None]) -> AttemptResult | None:
    attempt = db.get(QCMAttempt, attempt_id)
    if not attempt:
        return None

    questions = list_questions(db, attempt.questionnaire_id)
    score_brut = 0

    db.query(QCMAnswer).filter(QCMAnswer.attempt_id == attempt_id).delete()

    for question in questions:
        raw_answer = answers_dict.get(question.id)
        normalized_answer = normalize_answer(raw_answer)
        expected = normalize_answer(question.resultat_attendu)
        is_correct = bool(normalized_answer) and normalized_answer == expected
        points = question.points if is_correct else 0
        score_brut += points

        db.add(
            QCMAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                reponse_stagiaire=raw_answer.strip() if isinstance(raw_answer, str) else None,
                est_correct=is_correct,
                point_obtenu=points,
            )
        )

    total_questions = len(questions)
    note = compute_note_sur_20(score_brut, total_questions)
    attempt.score_brut = score_brut
    attempt.total_questions = total_questions
    attempt.note_sur_20 = note
    db.commit()

    return AttemptResult(score_brut=score_brut, total_questions=total_questions, note_sur_20=note)


def list_attempts(db: Session, stagiaire_id: int | None = None, questionnaire_id: int | None = None, day: date | None = None):
    query = select(QCMAttempt)
    if stagiaire_id:
        query = query.where(QCMAttempt.stagiaire_id == stagiaire_id)
    if questionnaire_id:
        query = query.where(QCMAttempt.questionnaire_id == questionnaire_id)
    if day:
        query = query.where(func.date(QCMAttempt.date_passage) == day.isoformat())
    return db.scalars(query.order_by(QCMAttempt.date_passage.desc())).all()


def get_attempt_detail(db: Session, attempt_id: int) -> QCMAttempt | None:
    return db.get(QCMAttempt, attempt_id)
