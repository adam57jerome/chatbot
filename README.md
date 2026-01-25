# Outlook - Corriger / Reformuler (100% local)

Application Windows locale pour corriger et reformuler des e-mails Outlook **sans aucune API Internet**.

## Fonctionnalités

- Récupération du texte (Body/HTMLBody) de l’e-mail Outlook actif.
- 3 sorties :
  1. **Correction** (orthographe, grammaire, ponctuation) via LanguageTool local.
  2. **Reformulation pro** (style professionnel, clair).
  3. **Reformulation courte** (plus direct, phrases plus courtes).
- Préservation de la signature (option).
- Option de conserver le HTML (réinjection HTML simple).
- Copie ou remplacement dans Outlook **sans jamais envoyer l’e-mail**.

## Prérequis

- Windows 10/11
- Python 3.11+
- Outlook installé et ouvert
- Java (pour LanguageTool local)

## Installation

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Installation de LanguageTool (local)

1. Installer Java (JDK ou JRE récent).
2. Télécharger LanguageTool : https://languagetool.org/fr/download/
3. Décompresser l’archive.
4. Lancer le serveur local :

```bash
java -cp languagetool-server.jar org.languagetool.server.HTTPServer --port 8081
```

> Vous pouvez changer le port, mais il doit rester local (localhost).

## Lancer l’application

```bash
python app.py
```

## Dépannage

- **Outlook non détecté** :
  - Vérifiez qu’une fenêtre de rédaction est ouverte.
  - Relancez Outlook en mode normal.
- **Erreurs COM / droits Windows** :
  - Lancez l’application avec les mêmes droits qu’Outlook.
- **LanguageTool manquant** :
  - Vérifiez que Java est installé et que le serveur local est démarré.
  - Vérifiez l’URL dans l’application (ex: `http://localhost:8081`).
- **pywin32** :
  - Si besoin : `pip install pywin32` puis relancez l’app.

## Fichiers

- `app.py` : interface Tkinter.
- `outlook_bridge.py` : lecture/écriture Outlook via COM.
- `local_corrector.py` : correction LanguageTool local.
- `rewriter_rules.py` : reformulation par règles.
- `utils_text.py` : détection tu/vous, signature, HTML.
- `log.txt` : journal en cas d’erreur.
