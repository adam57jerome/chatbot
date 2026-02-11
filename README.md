# Application web de gestion des stagiaires (FastAPI)

Projet complet **100% local** pour gérer des stagiaires et leur affectation à des sections de formation.

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
uvicorn app.main:app --reload
```

Puis ouvrir : http://127.0.0.1:8000

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
