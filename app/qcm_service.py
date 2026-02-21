from __future__ import annotations

from dataclasses import dataclass
import json
from datetime import date

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.models import QCMAnswer, QCMAttempt, QCMQuestion, Questionnaire


@dataclass
class AttemptResult:
    score_brut: int
    total_questions: int
    total_possible_points: int
    note_sur_20: float


def normalize_answer(value: str | None) -> str:
    if not value:
        return ""
    cleaned = value.strip().upper().replace(" ", "")
    if "," in cleaned:
        items = sorted([part for part in cleaned.split(",") if part])
        return ",".join(items)
    return cleaned


def parse_possible_answers(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        raw = json.loads(value)
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
    except Exception:
        pass
    return [part.strip() for part in value.split("|") if part.strip()]


def encode_possible_answers(values: list[str] | None) -> str | None:
    if not values:
        return None
    cleaned = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    return json.dumps(cleaned, ensure_ascii=False) if cleaned else None


def compute_note_sur_20(score_brut: int, total_questions: int) -> float:
    """Compute /20 note from score and maximum attainable score."""
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
    return db.scalars(query.order_by(Questionnaire.id)).all()


def add_question(
    db: Session,
    questionnaire_id: int,
    numero: int,
    resultat_attendu: str,
    enonce: str | None = None,
    points: int = 1,
    chapitre: str | None = None,
    sous_chapitre: str | None = None,
    possible_answers: list[str] | None = None,
) -> QCMQuestion:
    chapitre_clean = (chapitre or "").strip()
    if not chapitre_clean:
        raise ValueError("Le chapitre est obligatoire.")

    question = QCMQuestion(
        questionnaire_id=questionnaire_id,
        numero=numero,
        enonce=enonce or None,
        chapitre=chapitre_clean,
        sous_chapitre=(sous_chapitre.strip() if sous_chapitre else None),
        reponses_possibles=encode_possible_answers(possible_answers),
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
    sous_chapitre: str | None = None,
    possible_answers: list[str] | None = None,
) -> QCMQuestion | None:
    question = db.get(QCMQuestion, question_id)
    if not question:
        return None
    chapitre_clean = (chapitre or "").strip()
    if not chapitre_clean:
        raise ValueError("Le chapitre est obligatoire.")

    question.numero = numero
    question.resultat_attendu = resultat_attendu.strip()
    question.enonce = enonce or None
    question.chapitre = chapitre_clean
    question.sous_chapitre = sous_chapitre.strip() if sous_chapitre else None
    question.reponses_possibles = encode_possible_answers(possible_answers)
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
        select(QCMQuestion).where(QCMQuestion.questionnaire_id == questionnaire_id).order_by(QCMQuestion.id)
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
    total_possible_points = sum(max(int(q.points or 0), 0) for q in questions)
    note = compute_note_sur_20(score_brut, total_possible_points)
    attempt.score_brut = score_brut
    attempt.total_questions = total_questions
    attempt.note_sur_20 = note
    attempt.total_possible_points = total_possible_points
    db.commit()

    return AttemptResult(
        score_brut=score_brut,
        total_questions=total_questions,
        total_possible_points=total_possible_points,
        note_sur_20=note,
    )


def get_total_possible_points_for_questionnaire(db: Session, questionnaire_id: int) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(func.max(QCMQuestion.points, 0)), 0)).where(
            QCMQuestion.questionnaire_id == questionnaire_id
        )
    )
    return int(total or 0)


def get_attempt_total_possible_points(db: Session, attempt_id: int) -> int:
    attempt = db.get(QCMAttempt, attempt_id)
    if not attempt:
        return 0
    stored = int(attempt.total_possible_points or 0)
    if stored > 0:
        return stored
    return get_total_possible_points_for_questionnaire(db, attempt.questionnaire_id)


def get_attempt_review_rows(db: Session, attempt_id: int) -> list[dict[str, object]]:
    rows = db.execute(
        select(QCMQuestion, QCMAnswer)
        .join(QCMAnswer, QCMAnswer.question_id == QCMQuestion.id)
        .where(QCMAnswer.attempt_id == attempt_id)
        .order_by(QCMQuestion.numero, QCMQuestion.id)
    ).all()

    details: list[dict[str, object]] = []
    for question, answer in rows:
        expected = question.resultat_attendu or ""
        trainee_answer = answer.reponse_stagiaire or ""
        details.append(
            {
                "question_id": question.id,
                "numero": question.numero,
                "chapitre": question.chapitre or "Général",
                "sous_chapitre": question.sous_chapitre or "Sans sous-chapitre",
                "enonce": question.enonce or "",
                "attendu": expected,
                "reponse_stagiaire": trainee_answer,
                "correct": bool(answer.est_correct),
                "points_obtenus": int(answer.point_obtenu or 0),
                "points_max": int(question.points or 0),
            }
        )
    return details


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


def delete_attempt(db: Session, attempt_id: int) -> bool:
    attempt = db.get(QCMAttempt, attempt_id)
    if not attempt:
        return False
    db.delete(attempt)
    db.commit()
    return True


def get_attempt_answers_map(db: Session, attempt_id: int) -> dict[int, str | None]:
    rows = db.execute(
        select(QCMAnswer.question_id, QCMAnswer.reponse_stagiaire).where(QCMAnswer.attempt_id == attempt_id)
    ).all()
    return {int(qid): ans for qid, ans in rows}


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


def aggregate_scores_by_chapter(db: Session, trainee_id: int):
    rows = db.execute(
        select(
            QCMQuestion.chapitre.label("chapitre"),
            func.count(QCMAnswer.id).label("questions"),
            func.sum(QCMAnswer.est_correct.cast(Integer)).label("correct"),
            func.sum(QCMAnswer.point_obtenu).label("points"),
        )
        .select_from(QCMAnswer)
        .join(QCMQuestion, QCMQuestion.id == QCMAnswer.question_id)
        .join(QCMAttempt, QCMAttempt.id == QCMAnswer.attempt_id)
        .where(QCMAttempt.stagiaire_id == trainee_id)
        .group_by(QCMQuestion.chapitre)
        .order_by(QCMQuestion.chapitre)
    ).all()

    result = []
    for r in rows:
        questions = int(r.questions or 0)
        correct = int(r.correct or 0)
        incorrect = max(questions - correct, 0)
        rate = round((correct / questions) * 100, 1) if questions else 0.0
        result.append({
            "chapitre": r.chapitre or "Général",
            "questions": questions,
            "correct": correct,
            "incorrect": incorrect,
            "taux": rate,
        })
    return result


def aggregate_scores_by_subchapter(db: Session, trainee_id: int, chapitre: str | None = None):
    sous_expr = func.coalesce(func.nullif(QCMQuestion.sous_chapitre, ""), "Sans sous-chapitre")
    query = (
        select(
            QCMQuestion.chapitre.label("chapitre"),
            sous_expr.label("sous_chapitre"),
            func.count(QCMAnswer.id).label("questions"),
            func.sum(QCMAnswer.est_correct.cast(Integer)).label("correct"),
            func.sum(QCMAnswer.point_obtenu).label("points"),
        )
        .select_from(QCMAnswer)
        .join(QCMQuestion, QCMQuestion.id == QCMAnswer.question_id)
        .join(QCMAttempt, QCMAttempt.id == QCMAnswer.attempt_id)
        .where(QCMAttempt.stagiaire_id == trainee_id)
    )
    if chapitre:
        query = query.where(QCMQuestion.chapitre == chapitre)

    rows = db.execute(
        query.group_by(QCMQuestion.chapitre, sous_expr).order_by(QCMQuestion.chapitre, sous_expr)
    ).all()

    result = []
    for r in rows:
        questions = int(r.questions or 0)
        correct = int(r.correct or 0)
        incorrect = max(questions - correct, 0)
        rate = round((correct / questions) * 100, 1) if questions else 0.0
        result.append({
            "chapitre": r.chapitre or "Général",
            "sous_chapitre": r.sous_chapitre or "Sans sous-chapitre",
            "questions": questions,
            "correct": correct,
            "incorrect": incorrect,
            "taux": rate,
        })
    return result


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
            "by_chapter": [],
            "by_subchapter": [],
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

    by_chapter = aggregate_scores_by_chapter(db, trainee_id)
    by_subchapter = aggregate_scores_by_subchapter(db, trainee_id)

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
        "by_chapter": by_chapter,
        "by_subchapter": by_subchapter,
    }
