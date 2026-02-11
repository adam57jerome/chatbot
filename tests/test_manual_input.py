import pandas as pd

from src.manual_input import build_subjects_from_manual_tables


def test_build_subjects_from_manual_tables_creates_subjects_and_rows():
    table = pd.DataFrame(
        {
            "question": [1, 2],
            "correct_answer": ["a", "b"],
            "Alice__response": ["a", "c"],
            "Bob__response": ["a", "b"],
        }
    )

    subjects = build_subjects_from_manual_tables({"Math": table}, ["Alice", "Bob"])

    assert "Math" in subjects
    subject = subjects["Math"]
    assert len(subject.learners) == 2
    assert subject.questions_df.iloc[0]["Alice__response"] == "a"
    assert subject.questions_df.iloc[1]["excel_row"] == 9
