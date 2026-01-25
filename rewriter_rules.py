import re

import utils_text


PRO_REPLACEMENTS_VOUS = {
    "je te recontacte": "je reviens vers vous",
    "je te contacte": "je vous contacte",
    "je te remercie": "je vous remercie",
    "tu peux": "vous pouvez",
    "tu peux me": "vous pouvez me",
    "je t'envoie": "je vous envoie",
    "merci d'avance": "merci par avance",
    "au plus vite": "dès que possible",
}

PRO_REPLACEMENTS_TU = {
    "je te recontacte": "je reviens vers toi",
    "je te contacte": "je te contacte",
    "je te remercie": "je te remercie",
    "tu peux": "tu peux",
    "tu peux me": "tu peux me",
    "je t'envoie": "je t'envoie",
    "merci d'avance": "merci par avance",
    "au plus vite": "dès que possible",
}

SHORT_REPLACEMENTS_VOUS = {
    "je vous prie de bien vouloir": "merci de",
    "pourriez-vous": "pouvez-vous",
    "je reviens vers vous": "je reviens vers vous",
    "merci par avance": "merci",
}

SHORT_REPLACEMENTS_TU = {
    "je te prie de bien vouloir": "merci de",
    "pourrais-tu": "peux-tu",
    "merci par avance": "merci",
}


def rewrite_text(text: str, style: str, formality: str) -> str:
    paragraphs = text.split("\n")
    output: list[str] = []
    for paragraph in paragraphs:
        if not paragraph.strip():
            output.append("")
            continue
        processed = _rewrite_paragraph(paragraph, style=style, formality=formality)
        output.append(processed)
    return "\n".join(output)


def _rewrite_paragraph(text: str, style: str, formality: str) -> str:
    cleaned = utils_text.normalize_spaces(text)
    cleaned = utils_text.capitalize_sentences(cleaned)
    cleaned = utils_text.reduce_repetitions(cleaned)
    cleaned = utils_text.split_long_sentences(cleaned)

    if style == "pro":
        cleaned = _apply_replacements(cleaned, _get_pro_replacements(formality))
    if style == "short":
        cleaned = _apply_replacements(cleaned, _get_short_replacements(formality))
        cleaned = _shorten_phrases(cleaned)

    return cleaned


def _apply_replacements(text: str, replacements: dict[str, str]) -> str:
    for source, target in replacements.items():
        pattern = re.compile(re.escape(source), re.I)
        text = pattern.sub(lambda m: _match_case(target, m.group(0)), text)
    return text


def _match_case(replacement: str, matched: str) -> str:
    if matched and matched[0].isupper():
        return replacement[0].upper() + replacement[1:]
    return replacement


def _get_pro_replacements(formality: str) -> dict[str, str]:
    return PRO_REPLACEMENTS_VOUS if formality == "vous" else PRO_REPLACEMENTS_TU


def _get_short_replacements(formality: str) -> dict[str, str]:
    return SHORT_REPLACEMENTS_VOUS if formality == "vous" else SHORT_REPLACEMENTS_TU


def _shorten_phrases(text: str) -> str:
    text = re.sub(r"\b(s'il vous plaît|s'il te plaît)\b", "", text, flags=re.I)
    text = re.sub(r"\b(je voulais vous informer que|je voulais te dire que)\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text)
    return text.strip()
