from __future__ import annotations

from html import escape
from typing import Iterable, Mapping

from fpdf import FPDF


def _normalize_questions(questions: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for idx, row in enumerate(questions, start=1):
        normalized.append(
            {
                "numero": row.get("numero") or idx,
                "chapitre": str(row.get("chapitre") or "Général"),
                "sous_chapitre": str(row.get("sous_chapitre") or "Sans sous-chapitre"),
                "enonce": str(row.get("enonce") or ""),
                "possible_answers": list(row.get("possible_answers") or []),
            }
        )
    return normalized


def build_questionnaire_paper_html(questionnaire_title: str, questions: Iterable[Mapping[str, object]]) -> str:
    """Generate a printable HTML questionnaire with checkbox answers."""
    safe_title = escape((questionnaire_title or "Questionnaire").strip())
    blocks: list[str] = []

    for row in _normalize_questions(questions):
        numero = row["numero"]
        chapitre = escape(str(row["chapitre"]))
        sous_chapitre = escape(str(row["sous_chapitre"]))
        enonce = escape(str(row["enonce"]))
        possible_answers = row["possible_answers"]

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


def build_attempt_review_html(
    *,
    attempt_id: int,
    trainee_name: str,
    questionnaire_title: str,
    note_sur_20: float,
    score_brut: int,
    total_possible_points: int,
    rows: Iterable[Mapping[str, object]],
) -> str:
    safe_trainee = escape(trainee_name.strip() or "Stagiaire")
    safe_title = escape(questionnaire_title.strip() or "Questionnaire")
    table_rows: list[str] = []
    for row in rows:
        ok = bool(row.get("correct"))
        table_rows.append(
            "<tr>"
            f"<td>{escape(str(row.get('numero') or '-'))}</td>"
            f"<td>{escape(str(row.get('chapitre') or '-'))}</td>"
            f"<td>{escape(str(row.get('enonce') or '-'))}</td>"
            f"<td>{escape(str(row.get('attendu') or '-'))}</td>"
            f"<td>{escape(str(row.get('reponse_stagiaire') or '-'))}</td>"
            f"<td>{'OK' if ok else 'KO'}</td>"
            f"<td>{escape(str(row.get('points_obtenus') or 0))}/{escape(str(row.get('points_max') or 0))}</td>"
            "</tr>"
        )

    table_html = "".join(table_rows) if table_rows else '<tr><td colspan="7">Aucune réponse enregistrée.</td></tr>'

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>Résultat QCM #{attempt_id}</title>
<style>
  body {{ font-family: Arial, sans-serif; margin: 20px; color: #111; }}
  h1 {{ margin-bottom: 6px; }}
  .meta {{ margin-bottom: 14px; color: #444; }}
  .score {{ font-weight: 700; margin-bottom: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; vertical-align: top; }}
  th {{ background: #f7f7f7; }}
  @media print {{
    body {{ margin: 10mm; }}
  }}
</style>
</head>
<body>
  <h1>Résultat QCM - tentative #{attempt_id}</h1>
  <div class="meta">Stagiaire: <strong>{safe_trainee}</strong> — Questionnaire: <strong>{safe_title}</strong></div>
  <div class="score">Score: {score_brut}/{total_possible_points} points — Note: {note_sur_20}/20</div>
  <table>
    <thead>
      <tr>
        <th>Q#</th><th>Chapitre</th><th>Énoncé</th><th>Attendu</th><th>Réponse stagiaire</th><th>Résultat</th><th>Points</th>
      </tr>
    </thead>
    <tbody>{table_html}</tbody>
  </table>
</body>
</html>"""


def build_attempt_review_pdf_bytes(
    *,
    attempt_id: int,
    trainee_name: str,
    questionnaire_title: str,
    note_sur_20: float,
    score_brut: int,
    total_possible_points: int,
    rows: Iterable[Mapping[str, object]],
) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"Resultat QCM - tentative #{attempt_id}", ln=1)

    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 7, f"Stagiaire: {trainee_name}\nQuestionnaire: {questionnaire_title}")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, f"Score: {score_brut}/{total_possible_points} points - Note: {note_sur_20}/20", ln=1)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    headers = ["Q", "Chapitre", "Attendu", "Reponse", "Res.", "Pts"]
    widths = [10, 35, 38, 50, 14, 16]
    for h, w in zip(headers, widths):
        pdf.cell(w, 8, h, border=1)
    pdf.ln(8)

    pdf.set_font("Helvetica", size=9)
    for row in rows:
        q = str(row.get("numero") or "-")
        chapitre = str(row.get("chapitre") or "-")[:28]
        attendu = str(row.get("attendu") or "-")[:30]
        reponse = str(row.get("reponse_stagiaire") or "-")[:40]
        res = "OK" if bool(row.get("correct")) else "KO"
        pts = f"{int(row.get('points_obtenus') or 0)}/{int(row.get('points_max') or 0)}"

        values = [q, chapitre, attendu, reponse, res, pts]
        for value, w in zip(values, widths):
            pdf.cell(w, 7, value, border=1)
        pdf.ln(7)

        enonce = str(row.get("enonce") or "").strip()
        if enonce:
            pdf.set_font("Helvetica", "I", 8)
            pdf.multi_cell(0, 5, f"Enonce: {enonce}", border=1)
            pdf.set_font("Helvetica", size=9)

    return bytes(pdf.output(dest="S"))


def build_questionnaire_scan_html(questionnaire_title: str, questions: Iterable[Mapping[str, object]]) -> str:
    """Generate an A4 scan-optimized sheet to simplify OCR/LLM extraction."""
    safe_title = escape((questionnaire_title or "Questionnaire").strip())
    markers = '<div class="marker tl"></div><div class="marker tr"></div><div class="marker bl"></div><div class="marker br"></div>'

    blocks: list[str] = []
    for row in _normalize_questions(questions):
        numero = row["numero"]
        chapitre = escape(str(row["chapitre"]))
        sous_chapitre = escape(str(row["sous_chapitre"]))
        enonce = escape(str(row["enonce"]))
        possible_answers = row["possible_answers"]

        choices: list[str] = []
        if possible_answers:
            for choice_index, answer in enumerate(possible_answers):
                code = chr(65 + (choice_index % 26))
                choices.append(
                    f'<div class="scan-choice"><span class="scan-box"></span><span class="choice-code">{code}</span><span class="choice-label">{escape(str(answer))}</span></div>'
                )
        else:
            choices.append('<div class="scan-choice"><span class="scan-box"></span><span class="choice-code">L</span><span class="choice-label">Réponse libre</span></div>')

        blocks.append(
            f"""
            <section class="scan-question">
              <div class="scan-meta">Q{numero} | {chapitre} | {sous_chapitre}</div>
              <div class="scan-enonce">{enonce or '........................................................'}</div>
              <div class="scan-choices">{''.join(choices)}</div>
            </section>
            """
        )

    content = "\n".join(blocks) if blocks else "<p>Aucune question disponible.</p>"

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<title>{safe_title} - version scan</title>
<style>
  @page {{ size: A4; margin: 10mm; }}
  body {{ font-family: Arial, sans-serif; margin: 0; color: #111; }}
  .page {{ position: relative; padding: 8mm; border: 1px solid #222; min-height: 260mm; }}
  .marker {{ position: absolute; width: 9mm; height: 9mm; border: 2px solid #000; background: #fff; }}
  .tl {{ top: 4mm; left: 4mm; }}
  .tr {{ top: 4mm; right: 4mm; }}
  .bl {{ bottom: 4mm; left: 4mm; }}
  .br {{ bottom: 4mm; right: 4mm; }}
  h1 {{ margin: 0 0 2mm 0; font-size: 18px; }}
  .subtitle {{ margin: 0 0 3mm 0; font-size: 12px; }}
  .identity {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; margin-bottom: 4mm; font-size: 12px; }}
  .line {{ border-bottom: 1px solid #111; height: 7mm; }}
  .scan-question {{ border: 1px solid #999; margin-bottom: 3mm; padding: 2.5mm; break-inside: avoid; }}
  .scan-meta {{ font-size: 11px; font-weight: 700; margin-bottom: 1mm; }}
  .scan-enonce {{ font-size: 12px; margin-bottom: 2mm; }}
  .scan-choices {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5mm 3mm; }}
  .scan-choice {{ display: flex; align-items: center; gap: 1.6mm; font-size: 12px; }}
  .scan-box {{ display: inline-block; width: 5.2mm; height: 5.2mm; border: 1.8px solid #000; }}
  .choice-code {{ width: 4mm; font-weight: 700; text-align: center; }}
  .instruction {{ margin-top: 2mm; font-size: 11px; }}
</style>
</head>
<body>
  <div class="page">
    {markers}
    <h1>{safe_title}</h1>
    <p class="subtitle">Version scan optimisée (cocher nettement au stylo noir)</p>
    <div class="identity">
      <div>Nom / Prénom<div class="line"></div></div>
      <div>Date<div class="line"></div></div>
      <div>Identifiant<div class="line"></div></div>
    </div>
    {content}
    <div class="instruction">Conseil import: scanner en 300 dpi, contraste élevé, pages bien à plat.</div>
  </div>
</body>
</html>
"""
