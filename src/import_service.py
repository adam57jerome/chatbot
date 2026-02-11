from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .excel_importer import ExcelImportPreview, normalize_answer
from .models import Answer, Attempt, Question, Questionnaire, Section, Session as CohortSession, Trainee


def _score_from_values(response: object, expected: object) -> int:
    r = normalize_answer(response)
    br = normalize_answer(expected)
    if not r:
        return 0
    if br not in {"a", "b", "c", "d"}:
        return 0
    return int(r == br)


def _unique_questionnaire_name(db: Session, base_name: str) -> str:
    if not db.scalar(select(Questionnaire).where(Questionnaire.name == base_name).limit(1)):
        return base_name
    i = 2
    while True:
        candidate = f"{base_name} (import {i})"
        if not db.scalar(select(Questionnaire).where(Questionnaire.name == candidate).limit(1)):
            return candidate
        i += 1


def _split_name(fullname: str) -> tuple[str, str]:
    parts = fullname.split()
    if len(parts) <= 1:
        return fullname, ""
    return parts[0], " ".join(parts[1:])


def _get_or_create_session(db: Session, session_code: str) -> CohortSession:
    session = db.scalar(select(CohortSession).where(CohortSession.code == session_code).limit(1))
    if session:
        return session
    session = CohortSession(code=session_code, label=f"Session {session_code}", active=True)
    db.add(session)
    db.flush()
    return session


def _get_or_create_trainee(db: Session, session_id: int, full_name: str) -> Trainee:
    nom, prenom = _split_name(full_name)
    trainee = db.scalar(
        select(Trainee).where(
            Trainee.session_id == session_id,
            Trainee.nom == nom,
            Trainee.prenom == prenom,
        ).limit(1)
    )
    if trainee:
        return trainee
    trainee = Trainee(session_id=session_id, nom=nom, prenom=prenom, actif=True)
    db.add(trainee)
    db.flush()
    return trainee


def _get_or_create_attempt(db: Session, session_id: int, questionnaire_id: int, trainee_id: int) -> Attempt:
    attempt = db.scalar(
        select(Attempt).where(
            Attempt.session_id == session_id,
            Attempt.questionnaire_id == questionnaire_id,
            Attempt.trainee_id == trainee_id,
        ).limit(1)
    )
    if attempt:
        return attempt
    attempt = Attempt(session_id=session_id, questionnaire_id=questionnaire_id, trainee_id=trainee_id)
    db.add(attempt)
    db.flush()
    return attempt


def import_excel_to_db(
    db: Session,
    preview: ExcelImportPreview,
    questionnaire_name: str,
    session_code: str,
    import_answers: bool,
) -> tuple[Questionnaire, CohortSession, list[str]]:
    warnings = list(preview.warnings)

    questionnaire = Questionnaire(
        name=_unique_questionnaire_name(db, questionnaire_name),
        description=f"Import Excel: {Path(preview.source_path).name}",
        active=True,
    )
    db.add(questionnaire)
    db.flush()

    question_by_numero: dict[int, Question] = {}
    section_question_numbers: dict[str, set[int]] = {}

    for idx, section_data in enumerate(preview.sections_data, start=1):
        section = Section(questionnaire_id=questionnaire.id, name=section_data.name, ordre=idx)
        db.add(section)
        db.flush()

        section_question_numbers[section_data.name] = set()
        for q in section_data.questions:
            question = Question(
                questionnaire_id=questionnaire.id,
                section_id=section.id,
                numero=q.numero,
                bonne_reponse=q.bonne_reponse_normalized,
            )
            db.add(question)
            db.flush()
            question_by_numero[q.numero] = question
            section_question_numbers[section_data.name].add(q.numero)

    session = _get_or_create_session(db, session_code)

    if import_answers:
        for trainee_name in preview.trainees:
            trainee = _get_or_create_trainee(db, session.id, trainee_name)
            attempt = _get_or_create_attempt(db, session.id, questionnaire.id, trainee.id)

            for section_data in preview.sections_data:
                for numero in section_question_numbers[section_data.name]:
                    question = question_by_numero[numero]
                    response = section_data.responses_by_trainee.get(trainee_name, {}).get(numero, "")
                    score = _score_from_values(response, question.bonne_reponse)

                    answer = db.scalar(
                        select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == question.id).limit(1)
                    )
                    if answer:
                        answer.reponse_texte = response
                        answer.score = score
                    else:
                        db.add(
                            Answer(
                                attempt_id=attempt.id,
                                question_id=question.id,
                                reponse_texte=response,
                                score=score,
                            )
                        )

    db.commit()
    db.refresh(questionnaire)
    db.refresh(session)
    return questionnaire, session, warnings
