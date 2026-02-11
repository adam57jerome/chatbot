from __future__ import annotations

import json
from typing import Any


QUESTIONS_PAR_SECTION_RAW: dict[str, list[dict[str, Any]]] = json.loads(
    """
{
  "Lecture de plan": [
    {"numero": 1, "bonne_reponse": "a"},
    {"numero": 2, "bonne_reponse": "d"},
    {"numero": 3, "bonne_reponse": "c"},
    {"numero": 4, "bonne_reponse": "b"},
    {"numero": 5, "bonne_reponse": "c"},
    {"numero": 6, "bonne_reponse": "c"},
    {"numero": 7, "bonne_reponse": "d"},
    {"numero": 8, "bonne_reponse": "c"},
    {"numero": 9, "bonne_reponse": "d"},
    {"numero": 10, "bonne_reponse": "b"},
    {"numero": 11, "bonne_reponse": "a"},
    {"numero": 12, "bonne_reponse": "b"},
    {"numero": 13, "bonne_reponse": "a"},
    {"numero": 14, "bonne_reponse": "d"},
    {"numero": 15, "bonne_reponse": "c"},
    {"numero": 16, "bonne_reponse": "d"},
    {"numero": 17, "bonne_reponse": "d"},
    {"numero": 18, "bonne_reponse": "c"},
    {"numero": 19, "bonne_reponse": "a"},
    {"numero": 20, "bonne_reponse": "d"},
    {"numero": 21, "bonne_reponse": "b"},
    {"numero": 22, "bonne_reponse": "c"},
    {"numero": 23, "bonne_reponse": "c"},
    {"numero": 24, "bonne_reponse": "a"},
    {"numero": 25, "bonne_reponse": "c"},
    {"numero": 26, "bonne_reponse": "d"},
    {"numero": 27, "bonne_reponse": "c"},
    {"numero": 28, "bonne_reponse": "c"},
    {"numero": 29, "bonne_reponse": "b"},
    {"numero": 30, "bonne_reponse": "c"}
  ],
  "Acteur de l'acte de construire": [
    {"numero": 31, "bonne_reponse": "c"},
    {"numero": 32, "bonne_reponse": "b"},
    {"numero": 33, "bonne_reponse": "c"},
    {"numero": 34, "bonne_reponse": "c"},
    {"numero": 35, "bonne_reponse": "b"},
    {"numero": 36, "bonne_reponse": "b"},
    {"numero": 37, "bonne_reponse": "a"},
    {"numero": 38, "bonne_reponse": "b"},
    {"numero": 39, "bonne_reponse": "c"},
    {"numero": 40, "bonne_reponse": "a"},
    {"numero": 41, "bonne_reponse": "c"},
    {"numero": 42, "bonne_reponse": "b"},
    {"numero": 43, "bonne_reponse": "c"},
    {"numero": 44, "bonne_reponse": "c"},
    {"numero": 45, "bonne_reponse": "a"},
    {"numero": 46, "bonne_reponse": "b"},
    {"numero": 47, "bonne_reponse": "a"},
    {"numero": 48, "bonne_reponse": "a"},
    {"numero": 49, "bonne_reponse": "d"},
    {"numero": 50, "bonne_reponse": "c"},
    {"numero": 51, "bonne_reponse": "b"},
    {"numero": 52, "bonne_reponse": "d"},
    {"numero": 53, "bonne_reponse": "c"},
    {"numero": 54, "bonne_reponse": "b"},
    {"numero": 55, "bonne_reponse": "a"},
    {"numero": 56, "bonne_reponse": "c"},
    {"numero": 57, "bonne_reponse": "a"},
    {"numero": 58, "bonne_reponse": "c"},
    {"numero": 59, "bonne_reponse": "b"},
    {"numero": 60, "bonne_reponse": "c"}
  ],
  "Corps d'état dans le batiment": [
    {"numero": 61, "bonne_reponse": "d"},
    {"numero": 62, "bonne_reponse": "c"},
    {"numero": 63, "bonne_reponse": "b"},
    {"numero": 64, "bonne_reponse": "b"},
    {"numero": 65, "bonne_reponse": "a"},
    {"numero": 66, "bonne_reponse": "c"},
    {"numero": 67, "bonne_reponse": "a"},
    {"numero": 68, "bonne_reponse": "a"},
    {"numero": 69, "bonne_reponse": "a"},
    {"numero": 70, "bonne_reponse": "d"},
    {"numero": 71, "bonne_reponse": "d"},
    {"numero": 72, "bonne_reponse": "c"},
    {"numero": 73, "bonne_reponse": "a"},
    {"numero": 74, "bonne_reponse": "d"},
    {"numero": 75, "bonne_reponse": "d"},
    {"numero": 76, "bonne_reponse": "b"},
    {"numero": 77, "bonne_reponse": "a"},
    {"numero": 78, "bonne_reponse": "c"},
    {"numero": 79, "bonne_reponse": "d"},
    {"numero": 80, "bonne_reponse": "c"},
    {"numero": 81, "bonne_reponse": "a"},
    {"numero": 82, "bonne_reponse": "c"},
    {"numero": 83, "bonne_reponse": "c"},
    {"numero": 84, "bonne_reponse": "b"},
    {"numero": 85, "bonne_reponse": "b"},
    {"numero": 86, "bonne_reponse": "a"},
    {"numero": 87, "bonne_reponse": "a"},
    {"numero": 88, "bonne_reponse": "a"},
    {"numero": 89, "bonne_reponse": "a"},
    {"numero": 90, "bonne_reponse": "b"}
  ],
  "Utilisation de l'informatique e": [
    {"numero": 91, "bonne_reponse": "a"},
    {"numero": 92, "bonne_reponse": "b"},
    {"numero": 93, "bonne_reponse": "c"},
    {"numero": 94, "bonne_reponse": "a"},
    {"numero": 95, "bonne_reponse": "c"},
    {"numero": 96, "bonne_reponse": "c"},
    {"numero": 97, "bonne_reponse": "b"},
    {"numero": 98, "bonne_reponse": "d"},
    {"numero": 99, "bonne_reponse": "b"},
    {"numero": 100, "bonne_reponse": "b"},
    {"numero": 101, "bonne_reponse": "b"},
    {"numero": 102, "bonne_reponse": "b"},
    {"numero": 103, "bonne_reponse": "b"},
    {"numero": 104, "bonne_reponse": "d"},
    {"numero": 105, "bonne_reponse": "b"},
    {"numero": 106, "bonne_reponse": "a"},
    {"numero": 107, "bonne_reponse": "a"},
    {"numero": 108, "bonne_reponse": "a"},
    {"numero": 109, "bonne_reponse": "c"},
    {"numero": 110, "bonne_reponse": "a"},
    {"numero": 111, "bonne_reponse": "b"},
    {"numero": 112, "bonne_reponse": "c"},
    {"numero": 113, "bonne_reponse": "c"},
    {"numero": 114, "bonne_reponse": "a"},
    {"numero": 115, "bonne_reponse": "b"},
    {"numero": 116, "bonne_reponse": "b"},
    {"numero": 117, "bonne_reponse": "b"},
    {"numero": 118, "bonne_reponse": "b"},
    {"numero": 119, "bonne_reponse": "c"},
    {"numero": 120, "bonne_reponse": "c"}
  ],
  "Utilisation du français": [
    {"numero": 121, "bonne_reponse": "b"},
    {"numero": 122, "bonne_reponse": "c"},
    {"numero": 123, "bonne_reponse": "a"},
    {"numero": 124, "bonne_reponse": "a"},
    {"numero": 125, "bonne_reponse": "b"},
    {"numero": 126, "bonne_reponse": "b"},
    {"numero": 127, "bonne_reponse": "b"},
    {"numero": 128, "bonne_reponse": "d"},
    {"numero": 129, "bonne_reponse": "c"},
    {"numero": 130, "bonne_reponse": "d"},
    {"numero": 131, "bonne_reponse": "c"},
    {"numero": 132, "bonne_reponse": "a"},
    {"numero": 133, "bonne_reponse": "b"},
    {"numero": 134, "bonne_reponse": "d"},
    {"numero": 135, "bonne_reponse": "b"},
    {"numero": 136, "bonne_reponse": "a"},
    {"numero": 137, "bonne_reponse": "a"},
    {"numero": 138, "bonne_reponse": "a"},
    {"numero": 139, "bonne_reponse": "a"},
    {"numero": 140, "bonne_reponse": "a"},
    {"numero": 141, "bonne_reponse": "a"},
    {"numero": 142, "bonne_reponse": "c"},
    {"numero": 143, "bonne_reponse": "b"},
    {"numero": 144, "bonne_reponse": "a"},
    {"numero": 145, "bonne_reponse": "b"},
    {"numero": 146, "bonne_reponse": "c"},
    {"numero": 147, "bonne_reponse": "a"},
    {"numero": 148, "bonne_reponse": "c"},
    {"numero": 149, "bonne_reponse": "a"},
    {"numero": 150, "bonne_reponse": "a"}
  ],
  "Utilisation de Mathématique": [
    {"numero": 151, "bonne_reponse": "b"},
    {"numero": 152, "bonne_reponse": "b"},
    {"numero": 153, "bonne_reponse": "d"},
    {"numero": 154, "bonne_reponse": "a"},
    {"numero": 155, "bonne_reponse": "b"},
    {"numero": 156, "bonne_reponse": "c"},
    {"numero": 157, "bonne_reponse": "c"},
    {"numero": 158, "bonne_reponse": "a"},
    {"numero": 159, "bonne_reponse": "b"},
    {"numero": 160, "bonne_reponse": "c"},
    {"numero": 161, "bonne_reponse": "a"},
    {"numero": 162, "bonne_reponse": "c"},
    {"numero": 163, "bonne_reponse": "b"},
    {"numero": 164, "bonne_reponse": "b"},
    {"numero": 165, "bonne_reponse": "a"},
    {"numero": 166, "bonne_reponse": "a"},
    {"numero": 167, "bonne_reponse": "d"}
  ]
}
"""
)


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
