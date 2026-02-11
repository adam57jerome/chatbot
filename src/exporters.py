from __future__ import annotations

from io import BytesIO

import openpyxl
import pandas as pd

from .utils import SubjectSheet, safe_set_value


def _write_subject_sheet(ws, subject: SubjectSheet) -> None:
    safe_set_value(ws, row=4, col=2, value="Question")
    safe_set_value(ws, row=4, col=3, value="Bonne réponse")
    for learner in subject.learners:
        safe_set_value(ws, row=4, col=learner.response_col, value=learner.name)
        safe_set_value(ws, row=4, col=learner.score_col, value=f"Score {learner.name}")

    for _, row in subject.questions_df.iterrows():
        excel_row = int(row["excel_row"])
        safe_set_value(ws, row=excel_row, col=2, value=row["question"])
        safe_set_value(ws, row=excel_row, col=3, value=row["correct_answer"])
        for learner in subject.learners:
            response_col = f"{learner.name}__response"
            score_col = f"{learner.name}__score"
            safe_set_value(ws, row=excel_row, col=learner.response_col, value=row.get(response_col))
            safe_set_value(ws, row=excel_row, col=learner.score_col, value=int(row.get(score_col, 0)))

        for learner in subject.learners:
            safe_set_value(ws, row=subject.total_row, col=learner.score_col, value=subject.totals.get(learner.name, 0))
            safe_set_value(
                ws,
                row=subject.note_row,
                col=learner.score_col,
                value=subject.notes.get(learner.name, 0.0),
            )

    safe_set_value(ws, row=subject.total_row, col=3, value="Total points")
    safe_set_value(ws, row=subject.note_row, col=3, value="Note /20")


def _write_synthesis_sheet(wb, synthesis_df: pd.DataFrame) -> None:
    if "Feuil5" in wb.sheetnames:
        del wb["Feuil5"]
    if "Synthèse" in wb.sheetnames:
        del wb["Synthèse"]

    ws_syn = wb.create_sheet("Feuil5")
    for col_idx, col_name in enumerate(synthesis_df.columns, start=1):
        safe_set_value(ws_syn, row=1, col=col_idx, value=col_name)
    for row_idx, row in enumerate(synthesis_df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            safe_set_value(ws_syn, row=row_idx, col=col_idx, value=value)


def export_recalculated_workbook(
    source_bytes: bytes,
    subjects: dict[str, SubjectSheet],
    synthesis_df: pd.DataFrame,
) -> bytes:
    wb = openpyxl.load_workbook(BytesIO(source_bytes), data_only=False)

    for subject_name, subject in subjects.items():
        if subject_name not in wb.sheetnames:
            continue
        ws = wb[subject_name]
        _write_subject_sheet(ws, subject)

    _write_synthesis_sheet(wb, synthesis_df)

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()


def export_manual_workbook(
    section_name: str,
    subjects: dict[str, SubjectSheet],
    synthesis_df: pd.DataFrame,
) -> bytes:
    wb = openpyxl.Workbook()
    default = wb.active
    wb.remove(default)

    for subject_name, subject in subjects.items():
        ws = wb.create_sheet(subject_name[:31])
        safe_set_value(ws, row=1, col=1, value="Section")
        safe_set_value(ws, row=1, col=2, value=section_name)
        _write_subject_sheet(ws, subject)

    _write_synthesis_sheet(wb, synthesis_df)

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()


def export_synthesis_csv(synthesis_df: pd.DataFrame) -> bytes:
    return synthesis_df.to_csv(index=False).encode("utf-8")
