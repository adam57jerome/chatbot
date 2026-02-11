from pathlib import Path

import pandas as pd

from src.database import get_recent_runs, get_sections_with_counts, init_db, save_assessment_run
from src.scoring import score_subject
from src.utils import LearnerColumn, SubjectSheet


def _build_subject() -> SubjectSheet:
    subject = SubjectSheet(
        name="Lecture de plan",
        learners=[LearnerColumn(name="Alice", response_col=5, score_col=6)],
        questions_df=pd.DataFrame(
            [
                {"question": 1, "correct_answer": "a", "excel_row": 8, "Alice__response": "a"},
                {"question": 2, "correct_answer": "b", "excel_row": 9, "Alice__response": "c"},
            ]
        ),
        question_start_row=8,
        question_end_row=9,
        total_row=11,
        note_row=12,
    )
    return score_subject(subject)


def test_save_assessment_run_persists_sections_and_results(tmp_path: Path):
    db_path = str(tmp_path / "results.db")
    init_db(db_path)
    subjects = {"Lecture de plan": _build_subject()}

    run_id = save_assessment_run(
        section_name="Section Test",
        learner_names=["Alice"],
        subjects=subjects,
        source="manual",
        db_path=db_path,
    )

    assert run_id > 0
    sections_df = get_sections_with_counts(db_path)
    runs_df = get_recent_runs(db_path=db_path)

    assert "Section Test" in sections_df["section"].tolist()
    assert runs_df.iloc[0]["section"] == "Section Test"
    assert runs_df.iloc[0]["nb_lignes_resultats"] >= 1
