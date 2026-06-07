"""Persistance SQLite des recettes."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = (ROOT_DIR / "data" / "recipes.db").resolve()


class Base(DeclarativeBase):
    pass


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    ingredients_json: Mapped[str] = mapped_column(Text, default="[]")
    instructions_json: Mapped[str] = mapped_column(Text, default="[]")
    prep_time: Mapped[str] = mapped_column(String(80), default="")
    cook_time: Mapped[str] = mapped_column(String(80), default="")
    servings: Mapped[str] = mapped_column(String(80), default="")
    image_path: Mapped[str] = mapped_column(Text, default="")
    source_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    @property
    def ingredients(self) -> list[str]:
        return json.loads(self.ingredients_json)

    @property
    def instructions(self) -> list[str]:
        return json.loads(self.instructions_json)


class RecipeRepository:
    """Accès aux recettes avec un chemin SQLite absolu et stable."""

    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        Base.metadata.create_all(self.engine)

    def list_recipes(self, search: str = "") -> list[Recipe]:
        with Session(self.engine) as session:
            statement = select(Recipe).order_by(Recipe.updated_at.desc())
            if search.strip():
                statement = statement.where(Recipe.title.ilike(f"%{search.strip()}%"))
            return list(session.scalars(statement))

    def get_recipe(self, recipe_id: int) -> Recipe | None:
        with Session(self.engine) as session:
            return session.get(Recipe, recipe_id)

    def create_recipe(self, values: dict[str, Any]) -> Recipe:
        now = datetime.now(timezone.utc)
        recipe = Recipe(**self._to_columns(values), created_at=now, updated_at=now)
        with Session(self.engine) as session:
            session.add(recipe)
            session.commit()
            session.refresh(recipe)
            session.expunge(recipe)
        return recipe

    def update_recipe(self, recipe_id: int, values: dict[str, Any]) -> Recipe | None:
        with Session(self.engine) as session:
            recipe = session.get(Recipe, recipe_id)
            if recipe is None:
                return None
            for key, value in self._to_columns(values).items():
                setattr(recipe, key, value)
            recipe.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(recipe)
            session.expunge(recipe)
            return recipe

    def delete_recipe(self, recipe_id: int) -> Recipe | None:
        with Session(self.engine) as session:
            recipe = session.get(Recipe, recipe_id)
            if recipe is None:
                return None
            session.expunge(recipe)
            attached = session.merge(recipe)
            session.delete(attached)
            session.commit()
            return recipe

    @staticmethod
    def _to_columns(values: dict[str, Any]) -> dict[str, Any]:
        columns = {
            "title": str(values.get("title", "")).strip(),
            "description": str(values.get("description", "")).strip(),
            "prep_time": str(values.get("prep_time", "")).strip(),
            "cook_time": str(values.get("cook_time", "")).strip(),
            "servings": str(values.get("servings", "")).strip(),
            "image_path": str(values.get("image_path", "")).strip(),
            "source_text": str(values.get("source_text", "")).strip(),
            "ingredients_json": json.dumps(values.get("ingredients", []), ensure_ascii=False),
            "instructions_json": json.dumps(values.get("instructions", []), ensure_ascii=False),
        }
        if not columns["title"]:
            raise ValueError("Le titre de la recette est obligatoire.")
        return columns
