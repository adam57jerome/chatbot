from __future__ import annotations

import pandas as pd

from .utils import SubjectSheet


def build_synthesis(subjects: dict[str, SubjectSheet]) -> pd.DataFrame:
    if not subjects:
        return pd.DataFrame()

    learner_names: list[str] = []
    for subject in subjects.values():
        for learner in subject.learners:
            if learner.name not in learner_names:
                learner_names.append(learner.name)

    rows = []
    for subject_name, subject in subjects.items():
        row = {"Matière": subject_name}
        for learner_name in learner_names:
            row[learner_name] = subject.notes.get(learner_name)
        row["Moyenne matière"] = round(
            pd.Series([row[name] for name in learner_names], dtype="float64").mean(skipna=True),
            2,
        )
        rows.append(row)

    df = pd.DataFrame(rows)
    learner_means = {
        learner_name: round(pd.to_numeric(df[learner_name], errors="coerce").mean(skipna=True), 2)
        for learner_name in learner_names
    }
    group_mean = round(pd.to_numeric(df["Moyenne matière"], errors="coerce").mean(skipna=True), 2)

    summary_row = {"Matière": "Moyenne générale apprenant"}
    summary_row.update(learner_means)
    summary_row["Moyenne matière"] = group_mean

    return pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)
