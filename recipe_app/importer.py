"""Import de recettes copiées depuis ChatGPT (Markdown ou JSON)."""

from __future__ import annotations

import json
import re
import unicodedata
from typing import Any


HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)(.+?)\s*$")
META_PATTERNS = {
    "prep_time": re.compile(r"(?:temps de )?préparation\s*:\s*(.+)", re.IGNORECASE),
    "cook_time": re.compile(r"(?:temps de )?cuisson\s*:\s*(.+)", re.IGNORECASE),
    "servings": re.compile(r"(?:portions?|personnes?)\s*:\s*(.+)", re.IGNORECASE),
}


def _normalise(value: str) -> str:
    return "".join(
        char for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    )


def _clean_item(line: str) -> str:
    match = BULLET_RE.match(line)
    return (match.group(1) if match else line).strip()


def _from_json(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*", "", candidate, flags=re.IGNORECASE)
        candidate = re.sub(r"\s*```$", "", candidate)
    if not candidate.startswith("{"):
        return None
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "title": data.get("title") or data.get("titre") or "",
        "description": data.get("description", ""),
        "ingredients": data.get("ingredients", []),
        "instructions": data.get("instructions") or data.get("etapes") or data.get("étapes") or [],
        "prep_time": data.get("prep_time") or data.get("temps_preparation") or "",
        "cook_time": data.get("cook_time") or data.get("temps_cuisson") or "",
        "servings": data.get("servings") or data.get("portions") or "",
        "source_text": text,
    }


def parse_recipe(text: str) -> dict[str, Any]:
    """Transforme une recette Markdown/JSON en champs éditables."""
    if not text.strip():
        raise ValueError("Collez d’abord le texte d’une recette.")

    json_recipe = _from_json(text)
    if json_recipe is not None:
        if not str(json_recipe["title"]).strip():
            raise ValueError("La recette JSON doit contenir un titre.")
        return json_recipe

    result: dict[str, Any] = {
        "title": "",
        "description": "",
        "ingredients": [],
        "instructions": [],
        "prep_time": "",
        "cook_time": "",
        "servings": "",
        "source_text": text,
    }
    section = "description"
    description_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            label = heading.group(1).strip()
            normalised = _normalise(label)
            if not result["title"] and not any(word in normalised for word in ("ingredient", "preparation", "instruction", "etape")):
                result["title"] = label
                continue
            if "ingredient" in normalised:
                section = "ingredients"
            elif any(word in normalised for word in ("preparation", "instruction", "etape", "realisation")):
                section = "instructions"
            else:
                section = "description"
            continue

        meta_found = False
        for field, pattern in META_PATTERNS.items():
            if match := pattern.search(line):
                result[field] = match.group(1).strip("* ")
                meta_found = True
                break
        if meta_found:
            continue

        if not result["title"]:
            result["title"] = line.strip("*# ")
        elif section in ("ingredients", "instructions"):
            result[section].append(_clean_item(line))
        else:
            description_lines.append(line)

    result["description"] = "\n".join(description_lines)
    if not result["ingredients"] or not result["instructions"]:
        raise ValueError("Impossible de détecter les ingrédients et les étapes. Utilisez des titres Markdown « Ingrédients » et « Préparation ».")
    return result
