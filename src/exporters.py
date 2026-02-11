from __future__ import annotations

from io import BytesIO

import openpyxl
import pandas as pd

from .utils import SubjectSheet


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

        for learner in subject.learners:
            score_col = f"{learner.name}__score"
            if score_col not in subject.questions_df.columns:
                continue
            for _, row in subject.questions_df.iterrows():
                excel_row = int(row["excel_row"])
                ws.cell(row=excel_row, column=learner.score_col, value=int(row[score_col]))

            ws.cell(row=subject.total_row, column=learner.score_col, value=subject.totals.get(learner.name, 0))
            ws.cell(row=subject.note_row, column=learner.score_col, value=subject.notes.get(learner.name, 0.0))

    if "Feuil5" in wb.sheetnames:
        del wb["Feuil5"]
    if "Synthèse" in wb.sheetnames:
        del wb["Synthèse"]

    ws_syn = wb.create_sheet("Feuil5")
    for col_idx, col_name in enumerate(synthesis_df.columns, start=1):
        ws_syn.cell(row=1, column=col_idx, value=col_name)
    for row_idx, row in enumerate(synthesis_df.itertuples(index=False), start=2):
        for col_idx, value in enumerate(row, start=1):
            ws_syn.cell(row=row_idx, column=col_idx, value=value)

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out.getvalue()


def export_synthesis_csv(synthesis_df: pd.DataFrame) -> bytes:
    return synthesis_df.to_csv(index=False).encode("utf-8")
