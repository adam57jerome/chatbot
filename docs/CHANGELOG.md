# Historique des modifications

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
