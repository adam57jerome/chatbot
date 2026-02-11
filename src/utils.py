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
