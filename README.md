# Application web de gestion des stagiaires (FastAPI)

Projet complet **100% local** pour gérer des stagiaires et leur affectation à des sections de formation.

> ✅ Cette application fonctionne entièrement en local et **ne nécessite aucune clé API** (OpenAI, cloud, ou autre service externe).

## Stack
- Backend: FastAPI
- ORM: SQLAlchemy 2.x
- Migrations: Alembic
- Templates: Jinja2
- Interactions dynamiques: HTMX (affectation/désaffectation des stagiaires)
- Base de données: SQLite (par défaut)

## Fonctionnalités principales
- CRUD stagiaires
- CRUD sections
- Affectation d'un stagiaire à 0 ou 1 section
- Règle métier: suppression d'une section => `section_id` des stagiaires passe à `NULL`
- Recherche + filtres
- Pagination simple (50 éléments/page)
- Messages flash succès/erreur

## Arborescence

```text
app/
  main.py
  db.py
  models.py
  schemas.py
  crud.py
  routes/
    trainees.py
    sections.py
  templates/
    base.html
    trainees_list.html
    trainee_form.html
    trainee_detail.html
    sections_list.html
    section_form.html
    section_detail.html
    section_edit_assign.html
    partials/section_assign_lists.html
  static/styles.css
alembic/
  env.py
  script.py.mako
  versions/0001_initial.py
scripts/seed.py
tests/test_app.py
requirements.txt
alembic.ini
```

## Lancer le projet (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python scripts/seed.py   # optionnel
uvicorn app.main:app --reload --port 8001
```

Alternative (port 8001 par défaut):
```powershell
python -m app.main
```

Puis ouvrir : http://127.0.0.1:8001

## Filtres disponibles
- `/stagiaires`: recherche nom/prénom/email + filtre section (toutes/sans section/section donnée)
- `/sections`: recherche code/nom

## Endpoints HTMX (affectation)
- `POST /sections/{id}/assign` (`trainee_id`)
- `POST /sections/{id}/unassign` (`trainee_id`)

## Exécuter les tests

```bash
pytest
```

## Notes techniques
- Validation serveur: Pydantic + contraintes SQL.
- Gestion des erreurs SQL de type `UNIQUE` avec message utilisateur lisible.
- Aucun service externe requis.


## Interface alternative Streamlit (optionnelle)

Vous pouvez aussi utiliser une interface Streamlit locale (sans clé API), connectée à la même base SQLite:

```powershell
streamlit run streamlit_app.py --server.port 8501
```

> Cette interface est indépendante de FastAPI et utilise typiquement le port `8501`.
