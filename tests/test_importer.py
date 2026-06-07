import pytest

from recipe_app.importer import parse_recipe


def test_parse_markdown_recipe():
    result = parse_recipe("""# Tarte aux pommes
Une tarte familiale.
Préparation : 20 min
Cuisson : 35 min
Portions : 6

## Ingrédients
- 4 pommes
- 1 pâte feuilletée

## Préparation
1. Éplucher les pommes.
2. Cuire au four.
""")

    assert result["title"] == "Tarte aux pommes"
    assert result["ingredients"] == ["4 pommes", "1 pâte feuilletée"]
    assert result["instructions"] == ["Éplucher les pommes.", "Cuire au four."]
    assert result["prep_time"] == "20 min"
    assert result["cook_time"] == "35 min"
    assert result["servings"] == "6"


def test_parse_json_recipe_with_french_keys():
    result = parse_recipe('{"titre": "Soupe", "ingredients": ["eau"], "étapes": ["Chauffer"]}')
    assert result["title"] == "Soupe"
    assert result["instructions"] == ["Chauffer"]


def test_parse_rejects_incomplete_text():
    with pytest.raises(ValueError, match="Impossible de détecter"):
        parse_recipe("Une recette sans structure")
