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
        candidate = f"{base_name} ({i})"
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


def _get_trainee(db: Session, session_id: int, full_name: str) -> Trainee | None:
    nom, prenom = _split_name(full_name)
    return db.scalar(
        select(Trainee).where(
            Trainee.session_id == session_id,
            Trainee.nom == nom,
            Trainee.prenom == prenom,
        ).limit(1)
    )


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
    questionnaire_strategy: str,
    selected_sections: set[str],
    selected_trainees_for_answers: set[str],
    import_new_trainees: bool,
    selected_new_trainees: set[str],
) -> tuple[Questionnaire, CohortSession, list[str], list[str]]:
    warnings = list(preview.warnings)
    diagnostics: list[str] = []

    existing_by_name = db.scalar(select(Questionnaire).where(Questionnaire.name == questionnaire_name).limit(1))
    if existing_by_name and questionnaire_strategy == "cancel":
        raise ValueError(f"Le questionnaire '{questionnaire_name}' existe déjà. Import annulé.")

    target_name = questionnaire_name
    if existing_by_name and questionnaire_strategy == "copy":
        target_name = _unique_questionnaire_name(db, questionnaire_name)
        diagnostics.append(f"Questionnaire existant détecté: copie créée '{target_name}'.")

    try:
        with db.begin():
            questionnaire = Questionnaire(
                name=target_name,
                description=f"Import Excel: {Path(preview.source_path).name}",
                active=True,
            )
            db.add(questionnaire)
            db.flush()

            question_by_numero: dict[int, Question] = {}

            for idx, section_data in enumerate(preview.sections_data, start=1):
                if section_data.name not in selected_sections:
                    diagnostics.append(f"Section ignorée: {section_data.name}")
                    continue

                section = Section(questionnaire_id=questionnaire.id, name=section_data.name, ordre=idx)
                db.add(section)
                db.flush()
                diagnostics.append(f"Section importée: {section_data.name} ({len(section_data.questions)} questions)")

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

            session = _get_or_create_session(db, session_code)
            diagnostics.append(f"Session cible: {session.code}")

            if import_answers:
                for trainee_name in preview.trainees:
                    if trainee_name not in selected_trainees_for_answers:
                        diagnostics.append(f"Stagiaire ignoré (réponses): {trainee_name}")
                        continue

                    trainee = _get_trainee(db, session.id, trainee_name)
                    if trainee is None:
                        if import_new_trainees and trainee_name in selected_new_trainees:
                            nom, prenom = _split_name(trainee_name)
                            trainee = Trainee(session_id=session.id, nom=nom, prenom=prenom, actif=True)
                            db.add(trainee)
                            db.flush()
                            diagnostics.append(f"Nouveau stagiaire créé: {trainee_name}")
                        else:
                            diagnostics.append(f"Stagiaire non créé (nouveau non importé): {trainee_name}")
                            continue
                    else:
                        diagnostics.append(f"Stagiaire existant réutilisé: {trainee_name}")

                    attempt = _get_or_create_attempt(db, session.id, questionnaire.id, trainee.id)

                    for section_data in preview.sections_data:
                        if section_data.name not in selected_sections:
                            continue
                        for q in section_data.questions:
                            question = question_by_numero.get(q.numero)
                            if question is None:
                                continue
                            response = section_data.responses_by_trainee.get(trainee_name, {}).get(q.numero, "")
                            score = _score_from_values(response, question.bonne_reponse)

                            answer = db.scalar(
                                select(Answer)
                                .where(Answer.attempt_id == attempt.id, Answer.question_id == question.id)
                                .limit(1)
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
            else:
                diagnostics.append("Import des réponses désactivé par l'utilisateur.")

        db.refresh(questionnaire)
        db.refresh(session)
        return questionnaire, session, warnings, diagnostics
    except Exception:
        db.rollback()
        raise
