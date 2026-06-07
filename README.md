# 🍲 Mon carnet de recettes

Application web Streamlit permettant de créer, rechercher, modifier et supprimer des recettes de cuisine. Chaque recette peut contenir une image, des temps de préparation/cuisson, des ingrédients et des étapes. Une recette générée par ChatGPT peut être importée par simple copier-coller, sans clé API.

## Installation locale

Prérequis : Python 3.13.

```bash
python -m venv .venv
# Windows PowerShell : .venv\Scripts\Activate.ps1
# Linux/macOS : source .venv/bin/activate
pip install -r requirements-dev.txt
streamlit run streamlit_app.py --server.port 8001
```

L’application est disponible sur <http://localhost:8001>. La base SQLite est créée automatiquement dans `data/recipes.db` avec un chemin absolu calculé depuis le projet. Les images sont enregistrées dans `data/uploads/`.

## Importer une recette depuis ChatGPT

Demandez par exemple à ChatGPT :

> Donne-moi une recette au format Markdown avec un titre, une description, les temps de préparation et cuisson, le nombre de portions, puis des sections « Ingrédients » et « Préparation » sous forme de listes.

Copiez toute sa réponse, ouvrez l’onglet **Import ChatGPT**, collez le texte, ajoutez éventuellement une image puis cliquez sur **Importer la recette**. Les formats Markdown et JSON sont acceptés.

## Rendre le site accessible sur Internet

### Option simple : Streamlit Community Cloud

1. Placez ce projet dans un dépôt GitHub privé ou public.
2. Connectez-vous à [Streamlit Community Cloud](https://share.streamlit.io/).
3. Créez une application en sélectionnant le dépôt et le fichier `streamlit_app.py`.
4. Déployez, puis partagez l’URL fournie.

> Attention : sur certains hébergements gratuits, le disque local peut être réinitialisé lors d’un redéploiement. Pour un usage durable, configurez des sauvegardes du dossier `data/` ou utilisez un volume persistant chez un hébergeur compatible Streamlit.

### Serveur personnel/VPS

```bash
streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port 8001
```

Placez ensuite un proxy HTTPS (Caddy ou Nginx) devant le port `8001`. N’exposez pas directement la base SQLite ni le dossier `data/`.

## Tests

```bash
pytest -q
python -m compileall streamlit_app.py recipe_app tests
```

## Structure

- `streamlit_app.py` : interface utilisateur Streamlit.
- `recipe_app/database.py` : modèle SQLAlchemy et opérations CRUD SQLite.
- `recipe_app/importer.py` : analyse du texte Markdown/JSON copié depuis ChatGPT.
- `recipe_app/images.py` : stockage sécurisé des images téléversées.
- `docs/SPEC.md` : cahier des charges fonctionnel.
- `docs/CHANGELOG.md` : historique des évolutions.
