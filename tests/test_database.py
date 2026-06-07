from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")

from recipe_app.database import RecipeRepository


def recipe_values(title: str = "Curry") -> dict:
    return {
        "title": title,
        "description": "Simple et bon",
        "ingredients": ["Pois chiches", "Curry"],
        "instructions": ["Mélanger", "Cuire"],
        "prep_time": "10 min",
        "cook_time": "20 min",
        "servings": "4",
        "image_path": "",
        "source_text": "",
    }


def test_recipe_crud_uses_absolute_sqlite_path(tmp_path: Path):
    repository = RecipeRepository(tmp_path / "recipes.db")
    assert repository.db_path.is_absolute()

    created = repository.create_recipe(recipe_values())
    assert created.id
    assert repository.get_recipe(created.id).ingredients == ["Pois chiches", "Curry"]

    updated = repository.update_recipe(created.id, recipe_values("Curry doux"))
    assert updated.title == "Curry doux"
    assert repository.list_recipes("doux")[0].id == created.id

    deleted = repository.delete_recipe(created.id)
    assert deleted.id == created.id
    assert repository.get_recipe(created.id) is None


def test_title_is_required(tmp_path: Path):
    repository = RecipeRepository(tmp_path / "recipes.db")
    values = recipe_values("")

    try:
        repository.create_recipe(values)
    except ValueError as error:
        assert "titre" in str(error)
    else:
        raise AssertionError("Une recette sans titre ne doit pas être créée")
