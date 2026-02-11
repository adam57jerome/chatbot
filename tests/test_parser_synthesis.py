from io import BytesIO

import pytest


openpyxl = pytest.importorskip("openpyxl")

from src.excel_parser import parse_workbook
from src.scoring import score_all_subjects
from src.synthesis import build_synthesis


def _build_workbook_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Lecture de plan"

    ws.cell(row=4, column=5, value="Alice")  # E4
    ws.cell(row=4, column=8, value="Bob")  # H4

    # Questions démarrent plus bas que la ligne 8, avec une ligne vide entre questions
    ws.cell(row=10, column=2, value=1)
    ws.cell(row=10, column=3, value="oui")
    ws.cell(row=10, column=5, value="oui")
    ws.cell(row=10, column=8, value="non")

    ws.cell(row=11, column=2, value=None)
    ws.cell(row=11, column=3, value="non")
    ws.cell(row=11, column=5, value="non")
    ws.cell(row=11, column=8, value="non")

    ws.cell(row=12, column=2, value="")  # ligne vide dans le bloc

    ws.cell(row=13, column=2, value=3)
    ws.cell(row=13, column=3, value="peut-être")
    ws.cell(row=13, column=5, value="peut-être")
    ws.cell(row=13, column=8, value="oui")

    ws2 = wb.create_sheet("Feuil5")
    ws2.cell(row=1, column=1, value="ancienne synthèse")

    out = BytesIO()
    wb.save(out)
    return out.getvalue()


def test_parse_score_and_synthesis_flow_with_flexible_question_detection():
    parsed = parse_workbook(_build_workbook_bytes())

    assert "Lecture de plan" in parsed.subjects
    assert not parsed.ignored_sheets

    subjects = score_all_subjects(parsed.subjects)
    synthesis = build_synthesis(subjects)

    # Alice: 3 bonnes réponses; Bob: 1 bonne réponse
    assert subjects["Lecture de plan"].totals == {"Alice": 3, "Bob": 1}
    assert "Moyenne matière" in synthesis.columns
    assert synthesis.iloc[-1]["Matière"] == "Moyenne générale apprenant"
