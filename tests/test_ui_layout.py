from __future__ import annotations

from ui.layout import get_role_ui_preset


def test_admin_preset_is_confort_and_actions_enabled():
    preset = get_role_ui_preset("Admin")
    assert preset["ui_density"] == "Confort"
    assert preset["ui_show_section_actions"] is True


def test_formateur_preset_is_compact_and_management_actions_reduced():
    preset = get_role_ui_preset("Formateur")
    assert preset["ui_density"] == "Compact"
    assert preset["ui_compact_tables"] is True
    assert preset["ui_show_trainee_actions"] is False


def test_unknown_role_falls_back_to_admin_preset():
    preset = get_role_ui_preset("Autre")
    assert preset["ui_density"] == "Confort"
