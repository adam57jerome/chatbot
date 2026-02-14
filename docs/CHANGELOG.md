# Historique des modifications

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

