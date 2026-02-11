# Recalculateur de questionnaire d'entrée (Streamlit)

Application Streamlit qui recalcule les scores et notes d'un classeur Excel (sans dépendre des formules Excel) **ou** permet une **saisie manuelle complète** (section, stagiaires, thématiques, réponses).

## Stack

- Python 3.11
- Streamlit
- pandas + openpyxl
- plotly
- pytest

## Design des données

Le cœur métier s'appuie sur des `dataclasses` :

- `LearnerColumn` : nom stagiaire + index colonne réponse + index colonne score.
- `SubjectSheet` :
  - `questions_df` avec colonnes :
    - `question`
    - `correct_answer`
    - `excel_row`
    - `<Stagiaire>__response`
    - `<Stagiaire>__score` (ajouté après calcul)
  - métadonnées Excel : `question_start_row`, `question_end_row`, `total_row`, `note_row`
  - résultats : `totals`, `notes`, `empty_counts`
- `ParsedWorkbook` :
  - `subjects` (feuilles matières reconnues)
  - `ignored_sheets` (feuilles ignorées + raison "structure non reconnue")

## Structure du repo

- `app.py`
- `src/`
  - `excel_parser.py`
  - `manual_input.py`
  - `database.py`
  - `scoring.py`
  - `synthesis.py`
  - `exporters.py`
  - `utils.py`
- `tests/`
- `requirements.txt`
- `README.md`

## Fonctionnalités

### 1) Mode Import Excel
- Upload `.xlsx`
- Détection automatique des feuilles matières (hors Feuil5/Synthèse)
- Détection stagiaires via cellules non vides en ligne 4 (colonnes espacées supportées)
- Détection robuste des questions à partir de la ligne 8 (tolère décalages, numéros manquants et lignes vides intermédiaires)
- Recalcul des scores (normalisation : trim/lower/suppression espaces multiples)
- Réponses vides : score 0 + compteur par stagiaire
- Export Excel recalculé + CSV synthèse
- Gestion des cellules fusionnées : écriture sur la cellule ancre (haut-gauche) pour éviter les erreurs openpyxl

### 2) Mode Saisie manuelle
- Saisie de la **section**
- Saisie des **stagiaires** rattachés à la section
- Sélection des **thématiques**
- Saisie des bonnes réponses et réponses stagiaires via grilles éditables
- Calcul instantané scores/totaux/notes
- Export Excel généré depuis la saisie + CSV synthèse

### 3) Visualisations
- Vue matière (détail questions/réponses/scores)
- Vue synthèse (type Feuil5)
- Camembert par stagiaire (bonnes vs mauvaises réponses)
- Camembert par thématique (répartition moyenne groupe)
- Analyse graphique du groupe (barres moyennes générales par stagiaire)

### 4) Enregistrement & sauvegarde en base
- Base SQLite locale (`.data/results.db`) créée automatiquement
- Enregistrement des sections
- Enregistrement des stagiaires
- Liaison section ↔ stagiaires
- Historique des calculs (imports Excel et saisie manuelle)
- Sauvegarde des résultats par thématique et par stagiaire
- Vue latérale dans l'app : sections enregistrées + derniers runs

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

## Format attendu (mode Import Excel)

Pour chaque feuille matière :
- ligne 4 : noms stagiaires
- ligne 8+ :
  - colonne B : numéro question
  - colonne C : bonne réponse
  - colonne stagiaire : réponse
  - colonne suivante : score à recalculer

Feuille synthèse d'origine (`Feuil5`) facultative : elle est ignorée en entrée et recréée à l'export.
