from __future__ import annotations

from app.utils.paper_export import build_questionnaire_paper_html, build_questionnaire_scan_html


def test_build_questionnaire_paper_html_renders_checkboxes_and_metadata():
    html = build_questionnaire_paper_html(
        "QCM Test",
        [
            {
                "numero": 1,
                "chapitre": "Mathématiques",
                "sous_chapitre": "Fractions",
                "enonce": "2/4 = ?",
                "possible_answers": ["1/2", "2", "4"],
            }
        ],
    )

    assert "QCM Test" in html
    assert "Q1 — Mathématiques / Fractions" in html
    assert "2/4 = ?" in html
    assert html.count('type="checkbox"') == 3


def test_build_questionnaire_paper_html_handles_no_answers_with_free_field():
    html = build_questionnaire_paper_html(
        "QCM Libre",
        [
            {
                "numero": 2,
                "chapitre": "Français",
                "sous_chapitre": "",
                "enonce": "Expliquez.",
                "possible_answers": [],
            }
        ],
    )

    assert "Sans sous-chapitre" in html
    assert "☐ Réponse libre" in html


def test_build_questionnaire_scan_html_contains_markers_and_choice_codes():
    html = build_questionnaire_scan_html(
        "QCM Scan",
        [
            {
                "numero": 3,
                "chapitre": "Maths",
                "sous_chapitre": "Proportionnalité",
                "enonce": "Sélectionner la bonne réponse",
                "possible_answers": ["10", "20"],
            }
        ],
    )

    assert "Version scan optimisée" in html
    assert "class=\"marker tl\"" in html
    assert "Q3 | Maths | Proportionnalité" in html
    assert ">A<" in html
    assert ">B<" in html
    assert "300 dpi" in html
