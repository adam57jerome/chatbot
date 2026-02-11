from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd


@dataclass
class LearnerColumn:
    name: str
    response_col: int
    score_col: int


@dataclass
class SubjectSheet:
    name: str
    learners: List[LearnerColumn]
    questions_df: pd.DataFrame
    question_start_row: int
    question_end_row: int
    total_row: int
    note_row: int
    empty_counts: Dict[str, int] = field(default_factory=dict)
    totals: Dict[str, int] = field(default_factory=dict)
    notes: Dict[str, float] = field(default_factory=dict)


@dataclass
class ParsedWorkbook:
    subjects: Dict[str, SubjectSheet]
    ignored_sheets: Dict[str, str]


def normalize_answer(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return " ".join(text.split())


def safe_set_value(ws, row: int, col: int, value: object) -> None:
    cell = ws.cell(row=row, column=col)
    is_merged_cell = cell.__class__.__name__ == "MergedCell"

    if is_merged_cell:
        for merged_range in ws.merged_cells.ranges:
            if row in range(merged_range.min_row, merged_range.max_row + 1) and col in range(
                merged_range.min_col, merged_range.max_col + 1
            ):
                ws.cell(row=merged_range.min_row, column=merged_range.min_col, value=value)
                return

        try:
            ws.cell(row=row, column=col, value=value)
            return
        except AttributeError as exc:
            raise ValueError(
                f"Impossible d'écrire la valeur en ({row}, {col}) : cellule fusionnée sans ancre détectée"
            ) from exc

    ws.cell(row=row, column=col, value=value)
