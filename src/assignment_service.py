from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Assignment, Question, Section


def wizard_prerequisites_logic(
    questionnaire_selected: bool,
    section_count: int,
    question_count: int,
    trainee_count: int,
) -> dict[str, bool]:
    step1_ok = questionnaire_selected and section_count >= 1 and question_count >= 1
    step2_ok = trainee_count >= 1
    return {"step1_ok": step1_ok, "step2_ok": step2_ok, "all_ok": step1_ok and step2_ok}


def assign_questionnaire_to_session(
    db: Session,
    session_id: int,
    questionnaire_id: int,
    overwrite: bool = True,
) -> Assignment:
    existing = db.scalar(select(Assignment).where(Assignment.session_id == session_id).limit(1))
    if existing:
        if not overwrite:
            return existing
        existing.questionnaire_id = questionnaire_id
        existing.assigned_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    assignment = Assignment(session_id=session_id, questionnaire_id=questionnaire_id)
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


def get_assignment_for_session(db: Session, session_id: int) -> Assignment | None:
    return db.scalar(select(Assignment).where(Assignment.session_id == session_id).limit(1))


def get_assigned_questionnaire_id(db: Session, session_id: int) -> int | None:
    row = get_assignment_for_session(db, session_id)
    return row.questionnaire_id if row else None


def can_start_saisie(db: Session, session_id: int) -> bool:
    return get_assignment_for_session(db, session_id) is not None


def questionnaire_counts(db: Session, questionnaire_id: int) -> tuple[int, int]:
    section_count = len(db.scalars(select(Section).where(Section.questionnaire_id == questionnaire_id)).all())
    question_count = len(db.scalars(select(Question).where(Question.questionnaire_id == questionnaire_id)).all())
    return section_count, question_count
