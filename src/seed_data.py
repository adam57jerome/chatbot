from __future__ import annotations

from typing import Any


QUESTIONS_PAR_SECTION_RAW: dict[str, list[dict[str, Any]]] = {
    "Fondamentaux réseau": [
        {"numero": 1, "bonne_reponse": "a"},
        {"numero": 2, "bonne_reponse": "c"},
        {"numero": 3, "bonne_reponse": "d"},
        {"numero": 4, "bonne_reponse": "b"},
        {"numero": 5, "bonne_reponse": "a"},
    ],
    "Systèmes": [
        {"numero": 6, "bonne_reponse": "b"},
        {"numero": 7, "bonne_reponse": "d"},
        {"numero": 8, "bonne_reponse": "a"},
        {"numero": 9, "bonne_reponse": "c"},
        {"numero": 10, "bonne_reponse": "b"},
    ],
    "Cybersécurité": [
        {"numero": 11, "bonne_reponse": "d"},
        {"numero": 12, "bonne_reponse": "a"},
        {"numero": 13, "bonne_reponse": "c"},
        {"numero": 14, "bonne_reponse": "b"},
        {"numero": 15, "bonne_reponse": "d"},
    ],
    "Cloud": [
        {"numero": 16, "bonne_reponse": "a"},
        {"numero": 17, "bonne_reponse": "b"},
        {"numero": 18, "bonne_reponse": "c"},
        {"numero": 19, "bonne_reponse": "d"},
        {"numero": 20, "bonne_reponse": "a"},
    ],
    "Automatisation": [
        {"numero": 21, "bonne_reponse": "c"},
        {"numero": 22, "bonne_reponse": "d"},
        {"numero": 23, "bonne_reponse": "a"},
        {"numero": 24, "bonne_reponse": "b"},
        {"numero": 25, "bonne_reponse": "c"},
    ],
    "Méthodologie": [
        {"numero": 26, "bonne_reponse": "b"},
        {"numero": 27, "bonne_reponse": "a"},
        {"numero": 28, "bonne_reponse": "d"},
        {"numero": 29, "bonne_reponse": "c"},
        {"numero": 30, "bonne_reponse": "b"},
    ],
}


def convert_questions_par_section_raw(
    raw: dict[str, list[dict[str, Any]]],
) -> dict[str, dict[int, str]]:
    converted: dict[str, dict[int, str]] = {}

    for section_name, items in raw.items():
        section_map: dict[int, str] = {}
        for item in items:
            if "numero" not in item or "bonne_reponse" not in item:
                raise ValueError(
                    f"Seed invalide pour section '{section_name}': chaque item doit contenir 'numero' et 'bonne_reponse'."
                )

            numero = int(item["numero"])
            bonne_reponse = str(item["bonne_reponse"]).strip().lower()

            if numero in section_map:
                raise ValueError(
                    f"Seed invalide pour section '{section_name}': doublon du numero {numero}."
                )

            section_map[numero] = bonne_reponse

        converted[section_name] = section_map

    return converted


questions_par_section = convert_questions_par_section_raw(QUESTIONS_PAR_SECTION_RAW)
