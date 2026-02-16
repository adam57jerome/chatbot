from __future__ import annotations

from app.help_texts import AIDE_SECTIONS


def test_aide_sections_contains_qcm_and_synthese():
    assert "qcm" in AIDE_SECTIONS
    assert "synthese" in AIDE_SECTIONS


def test_aide_sections_core_keys_present():
    required = {"overview", "stagiaires", "sections", "formations", "import_csv", "database"}
    assert required.issubset(set(AIDE_SECTIONS))
