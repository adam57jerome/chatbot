from __future__ import annotations

from datetime import datetime
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Answer, Attempt, Question, Section, Trainee
from .services import score_answer


def list_attempts(db: Session, session_id: int, questionnaire_id: int) -> list[Attempt]:
    return db.scalars(
        select(Attempt)
        .where(Attempt.session_id == session_id, Attempt.questionnaire_id == questionnaire_id)
        .order_by(Attempt.created_at.desc())
    ).all()


def create_attempt(
    db: Session,
    session_id: int,
    questionnaire_id: int,
    label: str,
    created_at: datetime | None = None,
    duplicate_from_attempt_id: int | None = None,
) -> Attempt:
    attempt = Attempt(
        session_id=session_id,
        questionnaire_id=questionnaire_id,
        label=label,
        created_at=created_at or datetime.utcnow(),
        active=True,
    )
    db.add(attempt)
    db.flush()

    if duplicate_from_attempt_id:
        prev_answers = db.scalars(select(Answer).where(Answer.attempt_id == duplicate_from_attempt_id)).all()
        questions = {q.id: q for q in db.scalars(select(Question).where(Question.questionnaire_id == questionnaire_id)).all()}
        for a in prev_answers:
            q = questions.get(a.question_id)
            if not q:
                continue
            db.add(
                Answer(
                    attempt_id=attempt.id,
                    trainee_id=a.trainee_id,
                    question_id=a.question_id,
                    reponse_texte=a.reponse_texte,
                    score=score_answer(a.reponse_texte, q.bonne_reponse),
                )
            )

    db.commit()
    db.refresh(attempt)
    return attempt


def get_answer(db: Session, attempt_id: int, trainee_id: int, question_id: int) -> Answer | None:
    return db.scalar(
        select(Answer).where(
            Answer.attempt_id == attempt_id,
            Answer.trainee_id == trainee_id,
            Answer.question_id == question_id,
        ).limit(1)
    )


def save_answer_for_attempt(
    db: Session,
    attempt_id: int,
    trainee_id: int,
    question_id: int,
    response: str | None,
    expected: str | None,
) -> Answer:
    answer = get_answer(db, attempt_id, trainee_id, question_id)
    score = score_answer(response, expected)
    if answer is None:
        answer = Answer(
            attempt_id=attempt_id,
            trainee_id=trainee_id,
            question_id=question_id,
            reponse_texte=response or "",
            score=score,
        )
        db.add(answer)
    else:
        answer.reponse_texte = response or ""
        answer.score = score
    db.commit()
    db.refresh(answer)
    return answer


def copy_previous_attempt_answers(db: Session, source_attempt_id: int, target_attempt_id: int, questionnaire_id: int) -> int:
    prev_answers = db.scalars(select(Answer).where(Answer.attempt_id == source_attempt_id)).all()
    questions = {q.id: q for q in db.scalars(select(Question).where(Question.questionnaire_id == questionnaire_id)).all()}
    count = 0
    for a in prev_answers:
        q = questions.get(a.question_id)
        if not q:
            continue
        db.add(
            Answer(
                attempt_id=target_attempt_id,
                trainee_id=a.trainee_id,
                question_id=a.question_id,
                reponse_texte=a.reponse_texte,
                score=score_answer(a.reponse_texte, q.bonne_reponse),
            )
        )
        count += 1
    db.commit()
    return count


def compare_attempts_section_delta(db: Session, attempt_a_id: int, attempt_b_id: int, questionnaire_id: int) -> dict[str, float]:
    sections = db.scalars(select(Section).where(Section.questionnaire_id == questionnaire_id).order_by(Section.ordre)).all()
    deltas: dict[str, float] = {}
    for s in sections:
        qids = [q.id for q in db.scalars(select(Question).where(Question.section_id == s.id)).all()]
        if not qids:
            deltas[s.name] = 0.0
            continue

        ans_a = db.scalars(select(Answer).where(Answer.attempt_id == attempt_a_id, Answer.question_id.in_(qids))).all()
        ans_b = db.scalars(select(Answer).where(Answer.attempt_id == attempt_b_id, Answer.question_id.in_(qids))).all()

        by_t_a: dict[int, int] = {}
        by_t_b: dict[int, int] = {}
        for a in ans_a:
            by_t_a[a.trainee_id] = by_t_a.get(a.trainee_id, 0) + a.score
        for b in ans_b:
            by_t_b[b.trainee_id] = by_t_b.get(b.trainee_id, 0) + b.score

        tids = set(by_t_a) | set(by_t_b)
        notes_a = [(20 / len(qids)) * by_t_a.get(t, 0) for t in tids]
        notes_b = [(20 / len(qids)) * by_t_b.get(t, 0) for t in tids]
        deltas[s.name] = round((mean(notes_b) if notes_b else 0.0) - (mean(notes_a) if notes_a else 0.0), 2)
    return deltas
