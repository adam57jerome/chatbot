from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Answer, Attempt, Question, Questionnaire, Section, Session as CohortSession, Trainee
from .seed_data import questions_par_section


def normalize_answer(value: str | None, ignore_accents: bool = True) -> str:
    if not value:
        return ""
    text = " ".join(value.strip().lower().split())
    if ignore_accents:
        text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return text


def score_answer(response: str | None, expected: str | None) -> int:
    r = normalize_answer(response)
    br = normalize_answer(expected)
    if not r:
        return 0
    if br not in {"a", "b", "c", "d"}:
        return 0
    return int(r == br)


def parse_question_block(text: str) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(\d+)\s*[=:]\s*([a-dA-D])$", line)
        if not m:
            raise ValueError(f"Ligne invalide: {line}")
        entries.append((int(m.group(1)), m.group(2).lower()))
    return entries


def color_for_score(score: float, reference: float) -> str:
    if score >= reference:
        return "#2e7d32"
    if score >= reference - 1.0:
        return "#f9a825"
    return "#c62828"


def ensure_seed_data(db: Session) -> None:
    seed_name = "Questionnaire AC1024 – issu Excel"
    existing = db.scalar(select(Questionnaire).where(Questionnaire.name == seed_name))
    if existing:
        has_questions = db.scalar(select(Question.id).where(Question.questionnaire_id == existing.id).limit(1))
        if has_questions:
            if not db.scalar(select(CohortSession).where(CohortSession.code == "AC1024").limit(1)):
                db.add(CohortSession(code="AC1024", label="Session AC1024", active=True))
                db.commit()
            return
        db.delete(existing)
        db.flush()

    questionnaire = Questionnaire(
        name=seed_name,
        description="Seed initial sans import Excel",
        active=True,
        reference_score_20=15.0,
    )
    db.add(questionnaire)
    db.flush()

    ordre = 1
    for section_name, qmap in questions_par_section.items():
        section = Section(questionnaire_id=questionnaire.id, name=section_name, ordre=ordre)
        db.add(section)
        db.flush()
        for numero, good in qmap.items():
            db.add(
                Question(
                    questionnaire_id=questionnaire.id,
                    section_id=section.id,
                    numero=numero,
                    bonne_reponse=(good.lower() if good else None),
                )
            )
        ordre += 1

    if not db.scalar(select(CohortSession).limit(1)):
        db.add(CohortSession(code="AC1024", label="Session AC1024", active=True))
    db.commit()


@dataclass
class SectionResult:
    section_name: str
    total_points: int
    nb_questions: int
    note_sur_20: float


def get_or_create_attempt(db: Session, session_id: int, questionnaire_id: int, trainee_id: int | None = None) -> Attempt:
    # trainee_id kept for backward compatibility (attempt is now per session+questionnaire)
    attempt = db.scalar(
        select(Attempt)
        .where(Attempt.session_id == session_id, Attempt.questionnaire_id == questionnaire_id, Attempt.active.is_(True))
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    if attempt:
        return attempt
    attempt = Attempt(session_id=session_id, questionnaire_id=questionnaire_id, label="Passation", active=True)
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def save_answer(
    db: Session,
    attempt_id: int,
    question_id: int,
    response: str | None,
    expected: str | None,
    trainee_id: int | None = None,
) -> Answer:
    if trainee_id is None:
        raise ValueError("trainee_id requis pour save_answer")
    answer = db.scalar(
        select(Answer).where(Answer.attempt_id == attempt_id, Answer.trainee_id == trainee_id, Answer.question_id == question_id)
    )
    scored = score_answer(response, expected)
    if answer is None:
        answer = Answer(attempt_id=attempt_id, trainee_id=trainee_id, question_id=question_id, reponse_texte=response or "", score=scored)
        db.add(answer)
    else:
        answer.reponse_texte = response or ""
        answer.score = scored
    db.commit()
    db.refresh(answer)
    return answer


def section_stats_for_attempt(db: Session, attempt_id: int, section_id: int, trainee_id: int | None = None) -> SectionResult:
    questions = db.scalars(select(Question).where(Question.section_id == section_id).order_by(Question.numero)).all()
    q_ids = [q.id for q in questions]
    if not questions:
        return SectionResult("", 0, 0, 0.0)

    stmt = select(Answer).where(Answer.attempt_id == attempt_id, Answer.question_id.in_(q_ids))
    if trainee_id is not None:
        stmt = stmt.where(Answer.trainee_id == trainee_id)
    answers = db.scalars(stmt).all()
    score_map = {a.question_id: a.score for a in answers}
    total = sum(score_map.get(q.id, 0) for q in questions)
    note = (20 / len(questions)) * total
    return SectionResult(questions[0].section.name, total, len(questions), round(note, 2))


def global_stats_for_attempt(db: Session, attempt_id: int, questionnaire_id: int) -> dict:
    sections = db.scalars(select(Section).where(Section.questionnaire_id == questionnaire_id).order_by(Section.ordre)).all()
    section_notes = [section_stats_for_attempt(db, attempt_id, s.id).note_sur_20 for s in sections]
    global_note = mean(section_notes) if section_notes else 0.0
    return {
        "note_globale_sur_20": round(global_note, 2),
        "sections": section_notes,
    }


def group_synthesis(db: Session, session_id: int, questionnaire_id: int) -> dict:
    trainees = db.scalars(select(Trainee).where(Trainee.session_id == session_id, Trainee.actif.is_(True))).all()
    sections = db.scalars(select(Section).where(Section.questionnaire_id == questionnaire_id).order_by(Section.ordre)).all()
    trainees_stats = []
    section_bucket: dict[str, list[float]] = {s.name: [] for s in sections}

    attempt = db.scalar(
        select(Attempt)
        .where(Attempt.session_id == session_id, Attempt.questionnaire_id == questionnaire_id, Attempt.active.is_(True))
        .order_by(Attempt.created_at.desc())
        .limit(1)
    )
    if attempt is None:
        attempt = get_or_create_attempt(db, session_id, questionnaire_id)

    for trainee in trainees:
        sec_notes = {}
        for sec in sections:
            note = section_stats_for_attempt(db, attempt.id, sec.id, trainee.id).note_sur_20
            sec_notes[sec.name] = note
            section_bucket[sec.name].append(note)
        global_note = round(mean(sec_notes.values()), 2) if sec_notes else 0.0
        trainees_stats.append(
            {
                "trainee": f"{trainee.nom} {trainee.prenom}",
                "sections": sec_notes,
                "global_note": global_note,
            }
        )

    section_stats = {
        name: {
            "mean": round(mean(vals), 2) if vals else 0.0,
            "median": round(median(vals), 2) if vals else 0.0,
            "min": round(min(vals), 2) if vals else 0.0,
            "max": round(max(vals), 2) if vals else 0.0,
        }
        for name, vals in section_bucket.items()
    }
    return {"section_stats": section_stats, "trainees_stats": trainees_stats}


def export_chatgpt_payload(db: Session, session_id: int, questionnaire_id: int) -> str:
    cohort = db.get(CohortSession, session_id)
    questionnaire = db.get(Questionnaire, questionnaire_id)
    synth = group_synthesis(db, session_id, questionnaire_id)
    payload = {
        "session": cohort.code if cohort else "",
        "questionnaire": questionnaire.name if questionnaire else "",
        "reference_score": questionnaire.reference_score_20 if questionnaire else 15.0,
        "section_stats": synth["section_stats"],
        "trainees_stats": synth["trainees_stats"],
    }
    return json.dumps(payload, ensure_ascii=False)
