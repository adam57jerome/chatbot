# 📝 QCM Moodle (sans API)

Créez, éditez et exportez des questions Moodle en local avec Streamlit. Aucun appel réseau, tout reste sur votre machine.

## ✅ Fonctionnalités

- Import par copier/coller de JSON avec validation détaillée.
- Édition inline complète de chaque question.
- Duplication, suppression, réorganisation (monter/descendre).
- Export GIFT (.txt) et Moodle XML (.xml).
- Sauvegarde/chargement d'un set de questions en JSON.

## 🚀 Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## ▶️ Lancement

```bash
streamlit run streamlit_app.py
```

## 🧩 Format JSON attendu

Chaque question est un objet avec les champs suivants :

```json
{
  "category": "Maths/Algèbre",
  "type": "mcq",
  "title": "Équation",
  "question": "Quelle est la solution de x + 2 = 4 ?",
  "choices": ["1", "2", "3"],
  "correct_index": 1,
  "feedback_correct": "Bonne réponse !",
  "feedback_incorrect": "Mauvaise réponse."
}
```

- `type` : `mcq` (choix multiples) ou `tf` (vrai/faux).
- `correct_index` est **0-based**.

## 📦 Importer dans Moodle

### GIFT
1. Exportez le fichier `.txt` via l'application.
2. Dans Moodle : **Banque de questions → Importer → Format GIFT**.
3. Chargez le fichier `.txt`.

### Moodle XML
1. Exportez le fichier `.xml` via l'application.
2. Dans Moodle : **Banque de questions → Importer → Format Moodle XML**.
3. Chargez le fichier `.xml`.

## 📁 Exemples fournis

- `examples/questions.json`
- `examples/questions.gift.txt`
- `examples/questions.xml`
