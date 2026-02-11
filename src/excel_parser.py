from __future__ import annotations

from io import BytesIO
from typing import Dict, Iterable

import openpyxl
import pandas as pd

from .utils import LearnerColumn, ParsedWorkbook, SubjectSheet

SYNTHESIS_SHEETS = {"Feuil5", "Synthèse", "Synthese", "synthese", "synthèse"}


def _iter_subject_sheet_names(sheet_names: Iterable[str]) -> Iterable[str]:
    for sheet_name in sheet_names:
        if sheet_name not in SYNTHESIS_SHEETS:
            yield sheet_name


def detect_learners(ws) -> list[LearnerColumn]:
    learners: list[LearnerColumn] = []
    for col in range(4, ws.max_column + 1):
        header = ws.cell(row=4, column=col).value
        if header is None:
            continue
        name = str(header).strip()
        if not name:
            continue
        if col + 1 > ws.max_column + 1:
            continue
        learners.append(LearnerColumn(name=name, response_col=col, score_col=col + 1))
    return learners


def detect_question_bounds(ws, start_row: int = 8) -> tuple[int, int] | None:
    end_row = start_row - 1
    row = start_row
    while True:
        q_number = ws.cell(row=row, column=2).value
        if q_number in (None, ""):
            break
        end_row = row
        row += 1
    if end_row < start_row:
        return None
    return start_row, end_row


def parse_subject_sheet(ws, sheet_name: str) -> SubjectSheet:
    learners = detect_learners(ws)
    if not learners:
        raise ValueError("structure non reconnue: aucun apprenant détecté en ligne 4")

    bounds = detect_question_bounds(ws, start_row=8)
    if bounds is None:
        raise ValueError("structure non reconnue: aucune question détectée en colonne B")
    start_row, end_row = bounds

    rows = []
    for row in range(start_row, end_row + 1):
        data: Dict[str, object] = {
            "question": ws.cell(row=row, column=2).value,
            "correct_answer": ws.cell(row=row, column=3).value,
            "excel_row": row,
        }
        for learner in learners:
            data[f"{learner.name}__response"] = ws.cell(row=row, column=learner.response_col).value
        rows.append(data)

    df = pd.DataFrame(rows)
    total_row = end_row + 2
    note_row = end_row + 3
    return SubjectSheet(
        name=sheet_name,
        learners=learners,
        questions_df=df,
        question_start_row=start_row,
        question_end_row=end_row,
        total_row=total_row,
        note_row=note_row,
    )


def parse_workbook(file_bytes: bytes) -> ParsedWorkbook:
    wb = openpyxl.load_workbook(BytesIO(file_bytes), data_only=False)
    subjects: Dict[str, SubjectSheet] = {}
    ignored_sheets: Dict[str, str] = {}

    for sheet_name in _iter_subject_sheet_names(wb.sheetnames):
        ws = wb[sheet_name]
        try:
            subjects[sheet_name] = parse_subject_sheet(ws, sheet_name)
        except ValueError as exc:
            ignored_sheets[sheet_name] = str(exc)

    return ParsedWorkbook(subjects=subjects, ignored_sheets=ignored_sheets)
