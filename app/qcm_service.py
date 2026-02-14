from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
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
    chapitre: str | None = None,
) -> QCMQuestion:
    question = QCMQuestion(
        questionnaire_id=questionnaire_id,
        numero=numero,
        enonce=enonce or None,
        chapitre=chapitre.strip() if chapitre else None,
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
    chapitre: str | None = None,
) -> QCMQuestion | None:
    question = db.get(QCMQuestion, question_id)
    if not question:
        return None
    question.numero = numero
    question.resultat_attendu = resultat_attendu.strip()
    question.enonce = enonce or None
    question.chapitre = chapitre.strip() if chapitre else None
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
        select(QCMQuestion).where(QCMQuestion.questionnaire_id == questionnaire_id).order_by(QCMQuestion.chapitre, QCMQuestion.numero)
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


# Synthesis aggregates

def list_attempts_by_trainee(db: Session, trainee_id: int):
    return db.scalars(
        select(QCMAttempt).where(QCMAttempt.stagiaire_id == trainee_id).order_by(QCMAttempt.date_passage.desc())
    ).all()


def aggregate_correct_incorrect(db: Session, trainee_id: int) -> dict[str, int]:
    correct = db.scalar(
        select(func.coalesce(func.sum(QCMAnswer.point_obtenu), 0))
        .select_from(QCMAnswer)
        .join(QCMAttempt, QCMAttempt.id == QCMAnswer.attempt_id)
        .where(QCMAttempt.stagiaire_id == trainee_id)
    )
    total = db.scalar(
        select(func.coalesce(func.sum(QCMAttempt.total_questions), 0)).where(QCMAttempt.stagiaire_id == trainee_id)
    )
    correct = int(correct or 0)
    total = int(total or 0)
    incorrect = max(total - correct, 0)
    return {"correct": correct, "incorrect": incorrect, "total": total}


def aggregate_scores_by_questionnaire(db: Session, trainee_id: int):
    rows = db.execute(
        select(
            Questionnaire.titre,
            func.avg(QCMAttempt.note_sur_20).label("avg_note"),
            func.max(QCMAttempt.note_sur_20).label("best_note"),
            func.count(QCMAttempt.id).label("attempts"),
        )
        .join(Questionnaire, Questionnaire.id == QCMAttempt.questionnaire_id)
        .where(QCMAttempt.stagiaire_id == trainee_id)
        .group_by(Questionnaire.titre)
        .order_by(func.avg(QCMAttempt.note_sur_20).desc())
    ).all()
    return [
        {
            "questionnaire": r.titre,
            "avg_note": round(float(r.avg_note or 0.0), 1),
            "best_note": round(float(r.best_note or 0.0), 1),
            "attempts": int(r.attempts or 0),
        }
        for r in rows
    ]


def get_trainee_qcm_summary(db: Session, trainee_id: int):
    attempts = list_attempts_by_trainee(db, trainee_id)
    total_attempts = len(attempts)

    if not attempts:
        return {
            "stats": {
                "total_attempts": 0,
                "distinct_questionnaires": 0,
                "average_note": 0.0,
                "best_note": 0.0,
                "worst_note": 0.0,
                "last_attempt_date": None,
                "global_correct_rate": 0.0,
            },
            "attempts": [],
            "correct_incorrect": {"correct": 0, "incorrect": 0, "total": 0},
            "scores_by_questionnaire": [],
            "top3": [],
            "bottom3": [],
        }

    agg = db.execute(
        select(
            func.count(QCMAttempt.id),
            func.count(func.distinct(QCMAttempt.questionnaire_id)),
            func.avg(QCMAttempt.note_sur_20),
            func.max(QCMAttempt.note_sur_20),
            func.min(QCMAttempt.note_sur_20),
            func.max(QCMAttempt.date_passage),
        ).where(QCMAttempt.stagiaire_id == trainee_id)
    ).one()

    correct_data = aggregate_correct_incorrect(db, trainee_id)
    rate = round((correct_data["correct"] / correct_data["total"] * 100), 1) if correct_data["total"] else 0.0

    scores_by_questionnaire = aggregate_scores_by_questionnaire(db, trainee_id)
    top3 = scores_by_questionnaire[:3]
    bottom3 = sorted(scores_by_questionnaire, key=lambda x: x["avg_note"])[:3]

    return {
        "stats": {
            "total_attempts": int(agg[0] or 0),
            "distinct_questionnaires": int(agg[1] or 0),
            "average_note": round(float(agg[2] or 0.0), 1),
            "best_note": round(float(agg[3] or 0.0), 1),
            "worst_note": round(float(agg[4] or 0.0), 1),
            "last_attempt_date": agg[5],
            "global_correct_rate": rate,
        },
        "attempts": attempts,
        "correct_incorrect": correct_data,
        "scores_by_questionnaire": scores_by_questionnaire,
        "top3": top3,
        "bottom3": bottom3,
    }
