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
- Modifier un stagiaire : bouton **Modifier** dans la liste des stagiaires.
- CRUD sections
- Modifier une section : bouton **Modifier** dans la liste des sections.
- Affectation d'un stagiaire à 0 ou 1 section
- Règle métier: suppression d'une section => `section_id` des stagiaires passe à `NULL`
- Recherche + filtres
- Pagination simple (50 éléments/page)
- Messages flash succès/erreur
- Le logo **Accès VII** est affiché dans l'interface (FastAPI + Streamlit).

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

### UI (thème + navigation)
- Thème Streamlit: défini dans `.streamlit/config.toml`.
- Styles UI légers: `static/app.css` (cards, toolbar, header, espacements).
- Navigation pro:
  - priorité à `st.navigation(..., position="top")` avec groupes **Gestion / Outils / Paramètres**,
  - fallback automatique sur menu latéral (`selectbox`) si la version Streamlit ne supporte pas `st.navigation`.
- Version Streamlit recommandée: `>= 1.41`.
- Pour ajuster les couleurs du thème: modifier directement les clés `[theme]` du fichier `.streamlit/config.toml`.


## Initialisation BDD

### Option 1 (auto via application)
- FastAPI: les tables sont créées au démarrage (`init_db()` appelé au startup).
- Streamlit: les tables sont créées au démarrage et un bouton **Initialiser la base** est disponible.

### Option 2 (migrations Alembic recommandées)
```powershell
alembic upgrade head
```

### Vérifier le fichier SQLite utilisé
- Chemin par défaut: `data/app.db` (chemin absolu résolu automatiquement).
- Vous pouvez surcharger avec `DATABASE_URL`.

## Mise à jour BDD (Formations)

La feature **formations** ajoute :
- une table `formations`
- la colonne `stagiaires.formation_souhaitee_id` (FK nullable, `ON DELETE SET NULL`)

Commandes Alembic:

```powershell
# générer une migration (si vous voulez la regénérer localement)
alembic revision --autogenerate -m "add formations and trainee desired formation"

# appliquer les migrations
alembic upgrade head
```

Dans ce dépôt, la migration est déjà fournie :
- `alembic/versions/0002_add_formations_and_trainee_wish.py`

## Import CSV

Une page **Import CSV** est disponible dans le menu Streamlit (**Outils > Import CSV**).

Fonctionnalités :
- Upload `.csv` avec options séparateur/encodage/présence d'en-tête
- Prévisualisation des données
- Mapping des colonnes vers les champs stagiaire
- Validation des lignes + détection doublons
- Stratégies doublons: `skip` / `update` / `strict`
- Rapport final téléchargeable (`rapport_import.csv`)

Exemple de CSV:

```csv
nom,prenom,email,telephone,section_code,formation_code,notes
Dupont,Jean,jean.dupont@example.com,0600000001,AC1025,MAB,Profil reconversion
Martin,Lea,lea.martin@example.com,0600000002,AC1025,TMB,Disponible le matin
```

## Aide en ligne

Une page **📘 Aide** est disponible dans la navigation Streamlit.
- Guide complet par rubrique (stagiaires, sections, formations, import CSV, base de données)
- Aide contextuelle sur les champs/actions importantes (`help=`)

### Commandes utiles (Import + Aide)

```powershell
pip install -r requirements.txt
pytest -q
streamlit run streamlit_app.py --server.port 8501
```

## Module QCM

Le module QCM ajoute :
- gestion des **questionnaires**
- gestion des **questions QCM** avec résultat attendu
- **passages stagiaires** avec correction automatique
- historique des passages avec détail par question (**attendu** vs **réponse stagiaire**)
- filtre **Voir uniquement erreurs** dans le détail d'une tentative
- export du détail d'un passage en **HTML imprimable** (génération PDF via navigateur)
- export natif **PDF** (bouton direct)
- envoi optionnel du PDF par email (SMTP)
- compatibilité Streamlit: pas d'expanders imbriqués dans l'historique QCM
- pagination des tentatives + mode résumé compact / détail complet + bouton Afficher/Masquer détail
- PDF avec réponses attendues en vert et réponses stagiaire en vert/rouge selon résultat
- score brut + conversion **note sur 20** (arrondie à 1 décimale)

### Calcul de note
- 1 point si réponse stagiaire normalisée == résultat attendu normalisé
- 0 sinon
- `note_sur_20 = (score_brut / total_points_possibles) * 20`
- si `total_questions == 0`, alors note = `0`

### Commandes

```powershell
alembic upgrade head
streamlit run streamlit_app.py --server.port 8501
```

## Synthèse stagiaire QCM

Nouvelle page Streamlit: **Synthèse > 📊 Synthèse stagiaire**.

Contenu affiché pour un stagiaire:
- indicateurs globaux (tentatives, moyenne, meilleure/pire note, taux de bonnes réponses)
- camembert correct/incorrect
- bar chart des notes par tentative
- historique détaillé des tentatives
- bloc ChatGPT prêt à copier-coller (prompt + données JSON)

Utilisation:
1. Ouvrir Streamlit.
2. Aller dans **Synthèse > 📊 Synthèse stagiaire**.
3. Choisir un stagiaire.
4. Copier le bloc “Prompt prêt à l'emploi” dans ChatGPT.


## Gouvernance documentation

Toute nouvelle fonctionnalité doit mettre à jour :
- `docs/SPEC.md` (cahier des charges)
- `docs/CHANGELOG.md` (entrée datée des changements)


## Authentification (FastAPI + Streamlit)

L'auth est **optionnelle**: si les variables d'environnement ne sont pas définies, l'application reste ouverte (mode local dev).

Variables supportées :
- `APP_SECRET_KEY` : secret de session FastAPI (obligatoire en production)
- `APP_ADMIN_USER` : nom d'utilisateur admin
- `APP_ADMIN_PASSWORD_HASH` : hash du mot de passe (prioritaire)
- `APP_ADMIN_PASSWORD` : fallback local dev uniquement (à éviter en production)

Exemple PowerShell :
```powershell
$env:APP_SECRET_KEY = "change-me-super-secret"
$env:APP_ADMIN_USER = "admin"
$env:APP_ADMIN_PASSWORD = "admin123"   # fallback dev

uvicorn app.main:app --reload --port 8001
streamlit run streamlit_app.py --server.port 8501
```

Comportement :
- FastAPI : page `/login` + session + `/logout`.
- Streamlit : formulaire de connexion au démarrage + bouton de déconnexion en sidebar.



### Envoi email optionnel du PDF QCM

Variables SMTP supportées :
- `SMTP_HOST` (obligatoire)
- `SMTP_PORT` (optionnel, défaut `587`)
- `SMTP_USER` / `SMTP_PASSWORD` (optionnel selon serveur)
- `SMTP_FROM` (obligatoire)
- `SMTP_USE_TLS` (`1` par défaut, mettre `0` pour désactiver STARTTLS)

Sans ces variables, le bouton d'envoi email reste informatif et n'envoie rien.
