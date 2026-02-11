# Questionnaire AC Web (Streamlit + SQLite)

Application web pour la gestion de questionnaires d’entrée:
- saisie manuelle des réponses,
- analyses par section et par stagiaire,
- comparatifs de groupe,
- aide intégrée (menu + F1),
- export CSV et copie JSON pour ChatGPT.

## Stack
- Python 3.11
- PySide6
- SQLAlchemy + SQLite
- matplotlib (Qt embedding)
- pytest
- pyinstaller

## Installation
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
```

## Lancer l’application web
```bash
streamlit run web_app.py
```
ou
```bash
python app.py
```

La base est créée dans `data/questionnaire.db`.
Au premier lancement, un seed est injecté automatiquement:
- questionnaire `Questionnaire AC1024 – issu Excel`
- 6 sections (`Lecture de plan`, `Acteur de l'acte de construire`, `Corps d'état dans le batiment`, `Utilisation de l'informatique e`, `Utilisation du français`, `Utilisation de Mathématique`)
- 167 questions avec numérotation globale et bonnes réponses.

## Fonctionnalités principales
- **Admin**:
  - création questionnaire
  - création session
  - import rapide de stagiaires (copier/coller)
  - ajout de questions en bloc (`1=a`, `2=c`, ...)
  - import Excel `.xlsx` (questionnaire + sections + questions + stagiaires + réponses + scores recalculés)
  - gestion des conflits import: questionnaire existant (annuler/copie), sections existantes (ignorer), stagiaires existants (réutiliser)
- **Section**:
  - workflow Session → Questionnaire → Section → Stagiaire
  - grille `Numero | Bonne réponse | Réponse saisie | Score`
  - enregistrement + recalcul
  - effacement + copie JSON ChatGPT
- **Stagiaire**:
  - notes par section + graphique barres
  - sections sous référence mises en évidence
- **Synthèse groupe**:
  - tableau des moyennes globales
  - export CSV
- **Comparatifs sections**:
  - classement sections par moyenne groupe
  - écart à la référence
  - export CSV section
- **Aide**:
  - onglet intégré
  - menu Aide
  - touche F1

## Tests
```bash
pytest
```

Tests inclus:
- `test_seed()`
- `test_add_question_block_parse()`
- `test_scoring()`
- `test_section_stats()`
- `test_group_synthesis()`
- `test_reference_threshold()`

## Aide
Le contenu de l’aide se trouve dans:
- `src/help/help.md`

## Dépannage seed
Si un seed échoue (ex: crash au démarrage), supprimez `data/questionnaire.db` puis relancez l’application pour reconstruire la base proprement.


## Lancer avec script (Windows)
```bat
run.bat
```
Le script crée/active `.venv`, installe les dépendances puis lance la version web (`streamlit run web_app.py`).

## Version Web (recommandée pour affichage graphique)
L’application propose maintenant une interface web orientée dashboard (CSS + graphiques):

```bash
streamlit run web_app.py
```

Fonctions disponibles en web:
- saisie manuelle par section/stagiaire,
- synthèse groupe (moyennes, bar charts),
- vue stagiaire (notes par section),
- import Excel avec écran de récapitulatif, gestion des conflits et diagnostics.


## Lancer la version Web sous Windows
```bat
run_web.bat
```
