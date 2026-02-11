from __future__ import annotations

from .utils import SubjectSheet, normalize_answer


def score_subject(subject: SubjectSheet) -> SubjectSheet:
    df = subject.questions_df.copy()
    n_questions = len(df)

    totals: dict[str, int] = {}
    notes: dict[str, float] = {}
    empty_counts: dict[str, int] = {}

    for learner in subject.learners:
        response_col = f"{learner.name}__response"
        score_col = f"{learner.name}__score"

        scores = []
        empty_count = 0
        for _, row in df.iterrows():
            correct = normalize_answer(row["correct_answer"])
            response = normalize_answer(row[response_col])
            if response == "":
                empty_count += 1
                scores.append(0)
            else:
                scores.append(1 if response == correct else 0)

        df[score_col] = scores
        total_points = int(sum(scores))
        note = round((20 / n_questions) * total_points, 2) if n_questions else 0.0

        totals[learner.name] = total_points
        notes[learner.name] = note
        empty_counts[learner.name] = empty_count

    subject.questions_df = df
    subject.totals = totals
    subject.notes = notes
    subject.empty_counts = empty_counts
    return subject


def score_all_subjects(subjects: dict[str, SubjectSheet]) -> dict[str, SubjectSheet]:
    return {name: score_subject(subject) for name, subject in subjects.items()}
