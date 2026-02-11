import pytest

openpyxl = pytest.importorskip("openpyxl")

from src.utils import safe_set_value


def test_safe_set_value_writes_to_merged_anchor_when_target_is_non_anchor():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.merge_cells("E4:F4")

    safe_set_value(ws, row=4, col=6, value="Score Alice")  # F4 (non-ancre)

    assert ws.cell(row=4, column=5).value == "Score Alice"  # E4 (ancre)
    assert ws.cell(row=4, column=6).value is None
