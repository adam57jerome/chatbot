from pathlib import Path

from openpyxl import Workbook
from sqlalchemy import select

from src.excel_importer import parse_excel_preview
from src.import_service import import_excel_to_db
from src.models import Answer, Attempt, Question, Section, Trainee
from src.services import section_stats_for_attempt


def _build_fixture(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Lecture de plan"
    wb.create_sheet("Feuil5")

    ws["E4"] = "Dupont Alice"
    ws["H4"] = "Durand Bob"

    # Questions démarrent ligne 8
    data = [
        (1, "a", " A ", "b"),
        (2, "b", " B ", "b"),
        (3, "c", "d", " c "),
        (4, "d", "", "d"),
        (5, "a", "a", "x"),
    ]
    row = 8
    for numero, bonne, rep1, rep2 in data:
        ws.cell(row=row, column=2, value=numero)
        ws.cell(row=row, column=3, value=bonne)
        ws.cell(row=row, column=5, value=rep1)
        ws.cell(row=row, column=8, value=rep2)
        row += 1

    wb.save(path)


def test_excel_import_with_answers_and_scores(db_session, tmp_path: Path):
    xlsx = tmp_path / "fixture_import.xlsx"
    _build_fixture(xlsx)

    preview = parse_excel_preview(str(xlsx))
    questionnaire, session, _warnings = import_excel_to_db(
        db_session,
        preview,
        questionnaire_name="Import Test",
        session_code="S-IMP",
        import_answers=True,
    )

    assert questionnaire.name.startswith("Import Test")
    assert session.code == "S-IMP"
    assert len(db_session.scalars(select(Section).where(Section.questionnaire_id == questionnaire.id)).all()) == 1
    assert len(db_session.scalars(select(Question).where(Question.questionnaire_id == questionnaire.id)).all()) == 5
    assert len(db_session.scalars(select(Trainee).where(Trainee.session_id == session.id)).all()) == 2

    answers = db_session.scalars(select(Answer)).all()
    assert len(answers) == 10

    # Vérifie normalisation: bonne="b" et réponse=" B " => score=1
    q2 = db_session.scalar(select(Question).where(Question.questionnaire_id == questionnaire.id, Question.numero == 2))
    trainee = db_session.scalar(select(Trainee).where(Trainee.session_id == session.id, Trainee.nom == "Dupont"))
    attempt = db_session.scalar(
        select(Attempt).where(
            Attempt.session_id == session.id,
            Attempt.questionnaire_id == questionnaire.id,
            Attempt.trainee_id == trainee.id,
        )
    )
    a_q2 = db_session.scalar(select(Answer).where(Answer.attempt_id == attempt.id, Answer.question_id == q2.id))
    assert a_q2.score == 1

    section = db_session.scalar(select(Section).where(Section.questionnaire_id == questionnaire.id))
    stats = section_stats_for_attempt(db_session, attempt.id, section.id)
    assert stats.total_points == 3
    assert stats.note_sur_20 == 12.0
