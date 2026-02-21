from __future__ import annotations

from app.utils.paper_export import (
    build_attempt_review_html,
    build_attempt_review_pdf_bytes,
    build_questionnaire_paper_html,
    build_questionnaire_scan_html,
)


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


def test_build_attempt_review_html_contains_expected_and_trainee_answers():
    html = build_attempt_review_html(
        attempt_id=42,
        trainee_name="Jean Dupont",
        questionnaire_title="QCM Révision",
        note_sur_20=12.0,
        score_brut=3,
        total_possible_points=5,
        rows=[
            {
                "numero": 1,
                "chapitre": "Maths",
                "enonce": "2+2=?",
                "attendu": "4",
                "reponse_stagiaire": "5",
                "correct": False,
                "points_obtenus": 0,
                "points_max": 2,
            }
        ],
    )

    assert "tentative #42" in html
    assert "Jean Dupont" in html
    assert "Attendu" in html
    assert "Réponse stagiaire" in html
    assert "5" in html
    assert "Score: 3/5 points" in html


def test_build_attempt_review_pdf_bytes_starts_with_pdf_signature():
    pdf_bytes = build_attempt_review_pdf_bytes(
        attempt_id=7,
        trainee_name="Alice",
        questionnaire_title="QCM",
        note_sur_20=16.0,
        score_brut=8,
        total_possible_points=10,
        rows=[
            {
                "numero": 1,
                "chapitre": "Maths",
                "enonce": "2+2",
                "attendu": "4",
                "reponse_stagiaire": "4",
                "correct": True,
                "points_obtenus": 2,
                "points_max": 2,
            }
        ],
    )
    assert pdf_bytes.startswith(b"%PDF")
