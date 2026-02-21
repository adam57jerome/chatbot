# Historique des modifications

## 2026-02-20
### Module Web/API (correctif middleware)
- Correction de l'ordre des middlewares dans `app/main.py` pour garantir que `SessionMiddleware` est actif avant la lecture de la session flash.
- Remplacement du middleware fonctionnel flash par un middleware de classe (`FlashStateMiddleware`) avec accès sûr à `request.scope["session"]`.
- Corrige les scénarios de tests sections/stagiaires qui échouaient avec `SessionMiddleware must be installed to access request.session`.

## 2026-02-19
### Module UI/UX (correctifs)
- Correction de la sauvegarde d'édition de question QCM: validation du résultat attendu + gestion d'erreur explicite en cas d'échec de mise à jour.
- Correction de la page Aide: restauration d'un affichage exhaustif des rubriques (incluant QCM et Synthèse) avec ordre de rendu stable.

## 2026-02-18
### Module UI/UX (itération 3)
- Ajout d'un **profil UI par rôle** (Admin/Formateur) avec presets d'affichage automatiques depuis Préférences.
- Ajout d'une barre d'actions contextuelle sur les pages longues (actions principales en tête de page).
- Ajout d'un mode **onboarding** (découverte rapide) au premier passage sur plusieurs écrans métiers.
- Uniformisation de **Import CSV** et **Aide** avec assistant, accordéons et KPI légers.

## 2026-02-17
### Module UI/UX (itération 2)
- Ajout d'un mode global **Confort / Compact** dans Préférences (densité + tables compactes).
- Uniformisation de l'UI sur Sections, Formations et QCM-Questionnaires avec accordéons + options d'affichage (checkboxes).
- Ajout d'un **assistant de page** (3 étapes) sur les écrans métiers principaux.
- Ajout de **KPI rapides** sur les pages de gestion pour guider l'usage (volumes et état courant).

## 2026-02-16
### Module UI/UX
- Refonte visuelle légère (style plus moderne, lisible et cohérent) via `static/app.css`.
- Navigation clarifiée: séparation du menu **QCM** du bloc **Gestion** dans la navigation multipage.
- Page Stagiaires: ajout d’accordéons (filtres, formulaire, liste, actions rapides) + cases à cocher d’affichage.
- Page QCM - Passages: organisation en accordéons (préparer passage, modifier tentative, feuille de saisie, historique) + options d’affichage via checkboxes.
- Page Outils: regroupement en accordéons pour maintenance/sauvegarde/restauration.

## 2026-02-15
### Module QCM / Synthèse / Export
- QCM Questionnaire: correction de la navigation d’édition pour supporter **à la fois** la sélection via liste déroulante et les boutons **Précédent/Suivant** sans conflit d’état Streamlit.
- QCM Questionnaire: ajout d’un export **questionnaire papier (.html)** prêt à imprimer, avec cases à cocher pour passation manuelle.
- QCM Questionnaire: ajout d'une **feuille scan optimisée (.html)** (A4 + repères + cases contrastées) pour améliorer la fiabilité de conversion scan vers CSV.
- Synthèse stagiaire: ergonomie améliorée avec accordéons et visualisation centrée sur les radars (chapitres + sous-chapitres filtrables).

## 2026-02-14
### Module QCM / Synthèse / Documentation
- Ajout de la hiérarchie **Chapitre (obligatoire)** / **Sous-chapitre (optionnel)** sur les questions QCM.
- Migration Alembic: ajout colonnes, backfill `chapitre="Général"`, puis contrainte NOT NULL sur `chapitre`.
- UI QCM: champ Chapitre obligatoire, Sous-chapitre optionnel, filtres chapitre/sous-chapitre, édition/suppression de question enrichie.
- Import rapide QCM aligné sur `numero;resultat_attendu;chapitre;sous_chapitre;enonce`.
- Synthèse stagiaire: graphiques de réussite par chapitre et sous-chapitre + tableau récapitulatif.
- Aide: intégration du cahier des charges (`docs/SPEC.md`) et de cet historique (`docs/CHANGELOG.md`).
- README: ajout de la règle de maintenance documentaire (SPEC + CHANGELOG à chaque évolution).
- QCM Passages: ajout de la modification et suppression des tentatives depuis l'UI.
- Import QCM: ajout de l'import CSV de questionnaire(s) et conservation de l'ordre d'import des questions (pas de tri alphabétique).
- QCM: ajout de l'export des questions d'un questionnaire en fichier `.csv`.
- Synthèse: ajout du graphique radar (toile d'araignée) du profil de compétences avec export PNG (kaleido) ou HTML.
- QCM Questionnaire: ajout des réponses possibles (nombre variable) à la création/édition/import/export et utilisation en saisie des passages.
