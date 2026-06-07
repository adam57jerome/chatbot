# Cahier des charges — Carnet de recettes

## 1. Objectif

Fournir une application web simple et professionnelle permettant de conserver et consulter des recettes de cuisine illustrées, ainsi que d’importer une recette générée par ChatGPT via copier-coller.

## 2. Utilisateurs et accès

- L’application est utilisable depuis un navigateur sur ordinateur ou mobile.
- La première version ne comporte pas d’authentification : toute personne ayant accès à l’URL peut gérer les recettes.
- Le déploiement Internet recommandé est Streamlit Community Cloud ou un serveur avec HTTPS.

## 3. Fonctionnalités

### 3.1 Catalogue

- Afficher toutes les recettes de la plus récemment modifiée à la plus ancienne.
- Rechercher une recette par son titre.
- Afficher l’image, la description, les durées, les portions, les ingrédients et les étapes.

### 3.2 Gestion des recettes

- Créer une recette avec un titre, une description, des ingrédients, des étapes et une image facultative.
- Modifier tous les champs d’une recette existante.
- Supprimer une recette uniquement après confirmation explicite.
- Afficher des messages clairs de succès ou d’erreur.

### 3.3 Import ChatGPT par copier-coller

- Accepter une réponse Markdown comportant des sections « Ingrédients » et « Préparation »/« Étapes ».
- Accepter un objet JSON avec des clés françaises ou anglaises usuelles.
- Détecter le titre, la description, les temps, les portions, les ingrédients et les étapes.
- Signaler un texte vide ou insuffisamment structuré sans enregistrer de recette incomplète.

## 4. Données et fichiers

- Persistance via SQLite et SQLAlchemy dans le chemin absolu stable `<projet>/data/recipes.db`.
- Création automatique du dossier `data/` et de la table `recipes` sans effacer les données existantes.
- Images JPG, PNG et WebP enregistrées avec des noms aléatoires dans `<projet>/data/uploads/`.
- Suppression des images uniquement à l’intérieur du dossier d’uploads autorisé.

## 5. Contraintes techniques

- Python 3.13.
- Streamlit en mise en page large.
- SQLAlchemy 2.x et SQLite.
- Port documenté : `8001`.
- Tests automatisés avec pytest pour le parseur d’import et le CRUD.

## 6. Évolutions envisagées

- Authentification et recettes privées/publiques.
- Catégories, favoris, filtres et planification des menus.
- Export PDF et liste de courses consolidée.
- Stockage persistant externe des images et sauvegardes automatiques.
- Import assisté directement via l’API OpenAI, en complément du copier-coller.
