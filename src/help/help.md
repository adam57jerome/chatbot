# Aide intégrée — Questionnaire AC

## 1) Créer un questionnaire
1. Ouvrir l’onglet **Admin**.
2. Saisir le **nom** et la **note de référence /20**.
3. Cliquer sur **Créer questionnaire**.

## 2) Ajouter sections et questions
- Les sections du questionnaire seed sont créées au premier lancement.
- Pour ajouter des questions rapidement dans la section sélectionnée:

```text
1=a
2=c
3=d
```

Le système valide la lettre de réponse (`a/b/c/d`) sans tenir compte de la casse.

## 3) Saisie manuelle des réponses
Dans l’onglet **Section**:
1. Choisir session, questionnaire, section, stagiaire.
2. Saisir les réponses dans la grille.
3. Cliquer **Enregistrer** pour calculer les scores.
4. Utiliser **Effacer réponses** si nécessaire.

## 4) Analyses
- **Stagiaire**: notes par section + graphique.
- **Synthèse groupe**: moyenne globale par stagiaire + export CSV.
- **Comparatifs sections**: classement des sections et écart à la référence.

## 5) Export et partage
- **Exporter synthèse groupe (CSV)**
- **Exporter notes par section (CSV)**
- **Copier données pour ChatGPT**: copie un JSON compact dans le presse-papiers.

## 6) Raccourci F1
Le raccourci **F1** ouvre cette aide contextuelle à tout moment.

---

## Process recommandé : Sections -> Stagiaires -> Rattacher questionnaire

### <a name="wizard-etape-1"></a>Étape 1 — Sections et Questions
- Créer un nouveau questionnaire **ou** utiliser un questionnaire existant.
- Ajouter au moins une section et une question (possible via bloc `1=a`).

### <a name="wizard-etape-2"></a>Étape 2 — Session et Stagiaires
- Choisir/créer une session.
- Ajouter les stagiaires (unitaire ou import texte).

### <a name="wizard-etape-3"></a>Étape 3 — Rattacher le questionnaire
- Vérifier le résumé.
- Cliquer **Rattacher** pour créer/mettre à jour l’affectation de session.
- Cliquer **Commencer la saisie**.
