import pandas as pd

from src.scoring import score_subject
from src.utils import LearnerColumn, SubjectSheet, normalize_answer


def test_normalize_answer():
    assert normalize_answer("  Bon   Jour ") == "bon jour"
    assert normalize_answer(None) == ""


def test_score_subject_handles_empty_and_note():
    subject = SubjectSheet(
        name="Lecture de plan",
        learners=[LearnerColumn("Alice", 5, 6)],
        questions_df=pd.DataFrame(
            [
                {"question": 1, "correct_answer": "A", "excel_row": 8, "Alice__response": "a"},
                {"question": 2, "correct_answer": "B", "excel_row": 9, "Alice__response": ""},
                {"question": 3, "correct_answer": "C", "excel_row": 10, "Alice__response": "d"},
            ]
        ),
        question_start_row=8,
        question_end_row=10,
        total_row=12,
        note_row=13,
    )

    scored = score_subject(subject)

    assert scored.questions_df["Alice__score"].tolist() == [1, 0, 0]
    assert scored.totals["Alice"] == 1
    assert scored.notes["Alice"] == round(20 / 3, 2)
    assert scored.empty_counts["Alice"] == 1
