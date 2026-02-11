from __future__ import annotations

from typing import Dict, List

import pandas as pd

from .utils import LearnerColumn, SubjectSheet


def build_subjects_from_manual_tables(
    subject_tables: Dict[str, pd.DataFrame],
    learner_names: List[str],
) -> dict[str, SubjectSheet]:
    subjects: dict[str, SubjectSheet] = {}

    learners = [
        LearnerColumn(name=name, response_col=5 + idx * 3, score_col=6 + idx * 3)
        for idx, name in enumerate(learner_names)
    ]

    for subject_name, table in subject_tables.items():
        if table.empty:
            continue

        rows = []
        for i, row in table.reset_index(drop=True).iterrows():
            data = {
                "question": row.get("question", i + 1),
                "correct_answer": row.get("correct_answer", ""),
                "excel_row": 8 + i,
            }
            for learner in learners:
                data[f"{learner.name}__response"] = row.get(f"{learner.name}__response", "")
            rows.append(data)

        question_start = 8
        question_end = question_start + len(rows) - 1
        subjects[subject_name] = SubjectSheet(
            name=subject_name,
            learners=learners,
            questions_df=pd.DataFrame(rows),
            question_start_row=question_start,
            question_end_row=question_end,
            total_row=question_end + 2,
            note_row=question_end + 3,
        )

    return subjects
