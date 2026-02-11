# Recalculateur de questionnaire d'entrée (Streamlit)

Application Streamlit qui recalcule les scores et notes d'un classeur Excel de questionnaire (sans dépendre des formules Excel).

## Stack

- Python 3.11
- Streamlit
- pandas + openpyxl
- plotly
- pytest

## Design des données

Le cœur métier s'appuie sur des `dataclasses` :

- `LearnerColumn` : nom apprenant + index colonne réponse + index colonne score
- `SubjectSheet` :
  - `questions_df` avec colonnes :
    - `question`
    - `correct_answer`
    - `excel_row`
    - `<Apprenant>__response`
    - `<Apprenant>__score` (ajouté après calcul)
  - métadonnées d'écriture Excel : `question_start_row`, `question_end_row`, `total_row`, `note_row`
  - résultats : `totals`, `notes`, `empty_counts`
- `ParsedWorkbook` :
  - `subjects` (feuilles matières reconnues)
  - `ignored_sheets` (feuilles ignorées + raison "structure non reconnue")

## Structure du repo

- `app.py`
- `src/`
  - `excel_parser.py`
  - `scoring.py`
  - `synthesis.py`
  - `exporters.py`
  - `utils.py`
- `tests/`
- `requirements.txt`
- `README.md`

## Fonctionnalités

- Upload `.xlsx`
- Détection automatique des feuilles matières (hors Feuil5/Synthèse)
- Détection apprenants via cellules non vides en ligne 4 (colonnes espacées supportées)
- Détection du nombre de questions (colonne B depuis ligne 8)
- Recalcul des scores (normalisation: trim/lower/suppression espaces multiples)
- Réponses vides : score 0 + compteur par apprenant
- Vue matière : tableau détaillé + totaux + notes /20
- Vue synthèse :
  - notes par matière/apprenant
  - moyenne matière
  - moyenne générale apprenant
  - moyenne générale groupe
- Graphiques Plotly :
  - moyenne générale par apprenant
  - moyenne par matière
- Exports :
  - Excel recalculé (scores, totaux, notes et Feuil5 régénérée)
  - CSV de synthèse
- Robustesse : les feuilles non conformes sont ignorées avec message explicite

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Lancement

```bash
streamlit run app.py
```

## Tests

```bash
pytest
```

## Format attendu (résumé)

Pour chaque feuille matière :
- ligne 4 : noms apprenants
- ligne 8+ :
  - colonne B : numéro question
  - colonne C : bonne réponse
  - colonne apprenant : réponse
  - colonne suivante : score à recalculer

Feuille synthèse d'origine (`Feuil5`) facultative : elle est ignorée en entrée et recréée à l'export.
