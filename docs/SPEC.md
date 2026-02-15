# Cahier des charges — Application de gestion des stagiaires

## 1) Contexte et objectifs
Application locale (Streamlit + FastAPI + SQLAlchemy + SQLite) pour gérer des stagiaires, des sections, des formations, des QCM et des synthèses pédagogiques. Objectif: centraliser l’administration et l’évaluation sans dépendance cloud obligatoire.

## 2) Périmètre / hors périmètre
### Périmètre
- Gestion stagiaires, sections, formations.
- Module QCM (questionnaires, questions, passages, correction).
- Synthèse stagiaire avec indicateurs et graphiques.
- Import CSV.
- Sauvegarde / restauration SQLite.

### Hors périmètre
- Authentification avancée multi-rôle.
- Déploiement cloud managé.
- LMS complet.

## 3) Profils utilisateurs et cas d’usage
- **Administrateur pédagogique**: crée/modifie stagiaires, sections, formations.
- **Formateur**: crée des questionnaires, structure les questions, corrige les passages.
- **Référent**: consulte les synthèses et recommandations.

## 4) Fonctionnalités par module
### Stagiaires
- Création / édition / recherche.
- Affectation section et formation souhaitée.

### Sections
- CRUD complet.
- Affectation / désaffectation de stagiaires.

### Formations
- CRUD complet + statut actif/inactif.

### QCM
- CRUD questionnaires.
- Questions avec hiérarchie:
  - **chapitre obligatoire**
  - **sous-chapitre optionnel**
  - **réponses possibles à nombre variable** (optionnel, 0..n)
- Import rapide des questions (`numero;resultat_attendu;chapitre;sous_chapitre;enonce`).
- Import CSV de questionnaire(s) multi-lignes avec création automatique des questionnaires (`questionnaire;numero;resultat_attendu;chapitre;sous_chapitre;enonce;reponses_possibles;points`).
- Export CSV des questions d'un questionnaire (`questionnaire;numero;resultat_attendu;chapitre;sous_chapitre;enonce;reponses_possibles;points`).
- Export **questionnaire papier (.html)** avec cases à cocher pour passation manuelle (impression crayon/papier).
- Édition de question: navigation combinée **liste déroulante + boutons Précédent/Suivant**.
- Ordre d'import conservé pour l'affichage des questions (pas de tri alphabétique forcé).
- Passages et correction automatique.

### Synthèse
- Indicateurs globaux, top/bottom questionnaires.
- UI en accordéons pour améliorer la lisibilité (vue d'ensemble, radars, historique).
- Visualisation centrée sur les **radars**:
  - Radar des compétences par chapitre (/20).
  - Radar des compétences par sous-chapitre (/20) avec filtre de chapitre.
- Tableau récapitulatif chapitre/sous-chapitre (filtrable).
- Export radar chapitre en PNG/HTML.

### Import CSV
- Mapping colonnes, validation, stratégies doublons.

### Aide & documentation
- Aide fonctionnelle intégrée.
- Affichage de ce cahier des charges + historique des changements.

## 5) Règles métier
- Un stagiaire peut appartenir à 0..1 section.
- Suppression section/formation: références stagiaires remises à NULL.
- Email stagiaire unique (si renseigné).
- Notation QCM sur 20.
- **Question QCM: chapitre obligatoire (non vide), sous-chapitre facultatif**.
- Sous-chapitre null/vide agrégé comme **"Sans sous-chapitre"**.

## 6) Modèle de données (résumé)
- `stagiaires` -> FK `sections`, FK `formations`.
- `questionnaires` -> `qcm_questions`.
- `qcm_attempts` relie stagiaire + questionnaire.
- `qcm_answers` relie tentative + question.
- `qcm_questions`: `chapitre` (NOT NULL), `sous_chapitre` (NULL).

## 7) Parcours écran
- Navigation: Gestion / Synthèse / Outils / Paramètres.
- QCM - Questionnaires: création questionnaire, ajout/édition/suppression question, filtres chapitre/sous-chapitre, import rapide, export CSV et export papier (.html).
- Synthèse stagiaire: sélection stagiaire, KPI, accordéons, radars chapitre/sous-chapitre, tableau d’analyse.

## 8) Exigences non fonctionnelles
- Exécution locale Windows/Linux.
- Python 3.13 compatible.
- Performance correcte sur volumes pédagogiques usuels.
- Sauvegardes SQLite téléchargeables/restaurables.
- Sécurité minimale: validation entrées, contraintes SQL, erreurs explicites.

## 9) Contraintes techniques
- Streamlit pour UI opérateur.
- FastAPI pour API/serveur web.
- SQLAlchemy ORM + Alembic migrations.
- SQLite par défaut.

## 10) Roadmap
- Edition avancée des questions en lot.
- Export PDF des synthèses.
- Gestion droits utilisateurs.
- API statistiques avancées.
