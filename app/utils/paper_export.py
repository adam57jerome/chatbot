from __future__ import annotations

from html import escape
from typing import Iterable, Mapping


def build_questionnaire_paper_html(questionnaire_title: str, questions: Iterable[Mapping[str, object]]) -> str:
    """Generate a printable HTML questionnaire with checkbox answers."""
    safe_title = escape((questionnaire_title or "Questionnaire").strip())
    blocks: list[str] = []

    for idx, row in enumerate(questions, start=1):
        numero = row.get("numero") or idx
        chapitre = escape(str(row.get("chapitre") or "Général"))
        sous_chapitre = escape(str(row.get("sous_chapitre") or "Sans sous-chapitre"))
        enonce = escape(str(row.get("enonce") or ""))
        possible_answers = row.get("possible_answers") or []

        answers_html = "".join(
            f'<label class="choice"><input type="checkbox" /> {escape(str(answer))}</label>'
            for answer in possible_answers
        )
        if not answers_html:
            answers_html = '<div class="choice">☐ Réponse libre</div>'

        blocks.append(
            f"""
            <section class="question-block">
              <div class="meta">Q{numero} — {chapitre} / {sous_chapitre}</div>
              <div class="enonce">{enonce or '........................................................'}</div>
              <div class="choices">{answers_html}</div>
            </section>
            """
        )

    content = "\n".join(blocks) if blocks else "<p>Aucune question disponible.</p>"

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>{safe_title} - version papier</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; color: #111; }}
  h1 {{ margin-bottom: 6px; }}
  .subtitle {{ margin-bottom: 14px; color: #444; }}
  .identity {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 18px; }}
  .field {{ border-bottom: 1px solid #111; min-height: 26px; }}
  .question-block {{ break-inside: avoid; border: 1px solid #ddd; border-radius: 8px; padding: 10px; margin-bottom: 10px; }}
  .meta {{ font-size: 12px; color: #666; margin-bottom: 6px; }}
  .enonce {{ font-weight: 600; margin-bottom: 8px; }}
  .choices {{ display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; }}
  .choice {{ font-size: 14px; }}
  @media print {{
    body {{ margin: 12mm; }}
    .question-block {{ border-color: #aaa; }}
  }}
</style>
</head>
<body>
  <h1>{safe_title}</h1>
  <div class="subtitle">Version papier (cocher les réponses à la main)</div>
  <div class="identity">
    <div>Nom / Prénom : <div class="field"></div></div>
    <div>Date : <div class="field"></div></div>
  </div>
  {content}
</body>
</html>
"""
